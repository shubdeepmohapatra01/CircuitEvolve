"""Static checks and the sandboxed subprocess runner for optimizer programs.

Static check (ast, nothing is executed in the parent):
  * the module contains only function definitions, constant assignments and a docstring, and defines
    `optimize(circ, tools, budget)`;
  * no import, class, global/nonlocal, async, yield, with, del;
  * no name or attribute starting with '_' (no dunder access);
  * banned names: open, exec, eval, compile, getattr, setattr, delattr, globals, locals, vars, dir, type,
    object, super, __import__, input, print, breakpoint, help, memoryview, classmethod, staticmethod,
    property, exit, quit, id, hash, iter, next, format;
  * attribute access only as `tools.<public API name>` or a whitelisted container method
    (append, extend, insert, pop, get, items, keys, values, copy, index, count, sort, reverse);
    attribute assignment is refused;
  * size limits (source <= 20 000 chars, <= 3 000 AST nodes).
Restricted exec (child only): `__builtins__` replaced by a small whitelist of pure builtins.
Runner: one subprocess per (program, circuit) with a wall-time limit and an RSS cap enforced by a parent
watchdog (psutil; macOS does not enforce RLIMIT_AS), output via a JSON file.
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

from circuitevolve.blocks import REPO

# Process-wide lock held while a child is SPAWNED and while the parent verifies. On this macOS build,
# fork/exec of a subprocess from one thread while another thread runs numpy linear algebra corrupts the
# numpy results in the PARENT (30/30 wrong distances in .cache/evolve_opt/rep3.py, 0/30 without spawning;
# 2026-10-11). Spawning is fast, so holding the lock only around Popen costs nothing.
from circuitevolve.locks import NUMERIC_LOCK  # noqa: E402  (one lock for all stacks; was threading.RLock() here)

MAX_SOURCE = 20_000
MAX_NODES = 3_000
BANNED_NAMES = frozenset("""open exec eval compile getattr setattr delattr globals locals vars dir type object super
__import__ input print breakpoint help memoryview classmethod staticmethod property exit quit id hash iter next
format bytes bytearray issubclass""".split())
SAFE_BUILTINS = ("len range min max abs sum sorted enumerate zip list dict tuple set float int bool round any all "
                 "reversed str isinstance Exception ValueError").split()
METHOD_WHITELIST = frozenset("append extend insert pop get items keys values copy index count sort reverse".split())
REFUSED_NODES = (ast.Import, ast.ImportFrom, ast.ClassDef, ast.Global, ast.Nonlocal, ast.AsyncFunctionDef,
                 ast.AsyncFor, ast.AsyncWith, ast.Await, ast.Yield, ast.YieldFrom, ast.With, ast.Delete)


class StaticCheckError(ValueError):
    pass


def tool_api() -> frozenset:
    from .toolbox import Toolbox
    return frozenset(n for n in dir(Toolbox) if not n.startswith("_") and callable(getattr(Toolbox, n)))


def static_check(src: str) -> ast.Module:
    """Raise StaticCheckError if the program is not allowed. Returns the parsed module."""
    if not isinstance(src, str) or len(src) > MAX_SOURCE:
        raise StaticCheckError(f"source missing or longer than {MAX_SOURCE} characters")
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        raise StaticCheckError(f"syntax error: {e.msg} (line {e.lineno})") from None
    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_NODES:
        raise StaticCheckError(f"program too large ({len(nodes)} AST nodes > {MAX_NODES})")
    api = tool_api()
    for i, st in enumerate(tree.body):
        if isinstance(st, ast.FunctionDef):
            continue
        if isinstance(st, ast.Expr) and isinstance(st.value, ast.Constant) and i == 0:
            continue
        if isinstance(st, ast.Assign) and all(isinstance(t, ast.Name) for t in st.targets) and _is_literal(st.value):
            continue
        raise StaticCheckError(f"line {st.lineno}: only function definitions and literal constants at top level")
    fdefs = {st.name: st for st in tree.body if isinstance(st, ast.FunctionDef)}
    if "optimize" not in fdefs:
        raise StaticCheckError("no top-level function optimize(circ, tools, budget)")
    a = fdefs["optimize"].args
    if len(a.args) != 3 or a.vararg or a.kwarg or a.kwonlyargs:
        raise StaticCheckError("optimize must take exactly (circ, tools, budget)")
    tools_name = a.args[1].arg
    for node in nodes:
        ln = getattr(node, "lineno", "?")
        if isinstance(node, REFUSED_NODES):
            raise StaticCheckError(f"line {ln}: {type(node).__name__} is not allowed")
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                raise StaticCheckError(f"line {ln}: names starting with '_' are not allowed ({node.id})")
            if node.id in BANNED_NAMES:
                raise StaticCheckError(f"line {ln}: '{node.id}' is not allowed")
        if isinstance(node, ast.arg) and node.arg.startswith("_"):
            raise StaticCheckError(f"line {ln}: argument names starting with '_' are not allowed")
        if isinstance(node, (ast.FunctionDef, ast.Lambda)) and isinstance(node, ast.FunctionDef) and \
                node.name.startswith("_"):
            raise StaticCheckError(f"line {ln}: function names starting with '_' are not allowed")
        if isinstance(node, ast.FunctionDef) and node.decorator_list:
            raise StaticCheckError(f"line {ln}: decorators are not allowed")
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                raise StaticCheckError(f"line {ln}: attribute '{node.attr}' is not allowed")
            if not isinstance(node.ctx, ast.Load):
                raise StaticCheckError(f"line {ln}: attribute assignment is not allowed")
            if isinstance(node.value, ast.Name) and node.value.id == tools_name:
                if node.attr not in api:
                    raise StaticCheckError(f"line {ln}: tools.{node.attr} is not a toolbox function")
            elif node.attr not in METHOD_WHITELIST:
                raise StaticCheckError(f"line {ln}: attribute '.{node.attr}' is only allowed on tools")
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and "__" in node.value:
            raise StaticCheckError(f"line {ln}: string constants containing '__' are not allowed")
    # `tools` must not be rebound or passed under another name to hide attribute access
    for node in nodes:
        if isinstance(node, ast.Name) and node.id == tools_name and not isinstance(node.ctx, ast.Load):
            raise StaticCheckError(f"line {node.lineno}: '{tools_name}' may not be reassigned")
    return tree


def _is_literal(v) -> bool:
    try:
        ast.literal_eval(v)
        return True
    except Exception:
        return False


def restricted_exec(src: str) -> dict:
    """Child-side: static check, then exec with a whitelisted __builtins__. Returns the namespace."""
    import builtins
    tree = static_check(src)
    ns = {"__builtins__": {k: getattr(builtins, k) for k in SAFE_BUILTINS}}
    exec(compile(tree, "<program>", "exec"), ns)
    return ns


# ------------------------------------------------------------------------------ subprocess runner
def run_program(src: str, n: int, orig_ops_json: list, budget: dict, wall_s: float = 300.0,
                mem_mb: int = 4000, cache: bool = True, workdir: Path | None = None) -> dict:
    """Run one program on one circuit in a fresh interpreter. Returns the child's JSON result, or
    {'ok': False, 'error': ...} on timeout, memory cap, crash or bad output."""
    import psutil
    workdir = Path(workdir or tempfile.mkdtemp(prefix="evo_", dir=str(REPO / ".cache" / "evolve_opt")))
    workdir.mkdir(parents=True, exist_ok=True)
    job, out = workdir / "job.json", workdir / "out.json"
    job.write_text(json.dumps(dict(source=src, n=n, orig=orig_ops_json, budget=budget, cache=cache)))
    env = dict(os.environ)
    env.setdefault("XDG_CONFIG_HOME", str(REPO / ".venv" / "xdg"))
    env["PYTHONPATH"] = str(REPO) + os.pathsep + env.get("PYTHONPATH", "")
    t0 = time.time()
    with NUMERIC_LOCK:
        proc = subprocess.Popen([child_python(), "-m", "circuitevolve.legacy.evolve_opt.child", str(job), str(out)],
                                cwd=str(workdir), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                start_new_session=True)
    killed = {}

    def watchdog():
        try:
            p = psutil.Process(proc.pid)
        except Exception:
            p = None
        while proc.poll() is None:
            if p is not None:
                try:
                    rss = p.memory_info().rss          # the child only (listing children is not permitted here)
                    if rss > mem_mb * 2 ** 20:
                        killed["why"] = f"memory cap exceeded ({rss / 2**20:.0f} MB > {mem_mb} MB)"
                except Exception:
                    pass
            if not killed and time.time() - t0 > wall_s:
                killed["why"] = f"wall-time limit exceeded ({wall_s:.0f} s)"
            if killed:
                _kill(proc)
                return
            time.sleep(0.2)

    th = threading.Thread(target=watchdog, daemon=True)
    th.start()
    try:
        _, err = proc.communicate(timeout=wall_s + 30)
    except subprocess.TimeoutExpired:
        killed.setdefault("why", f"wall-time limit exceeded ({wall_s:.0f} s)")
        _kill(proc)
        _, err = proc.communicate()
    th.join(timeout=2)
    wall = time.time() - t0
    if killed:
        return dict(ok=False, error=killed["why"], wall_s=wall)
    if not out.exists():
        tail = (err or b"").decode(errors="replace")[-400:]
        return dict(ok=False, error=f"child exited {proc.returncode} without output: {tail}", wall_s=wall)
    try:
        res = json.loads(out.read_text())
    except ValueError:
        return dict(ok=False, error="child output is not JSON", wall_s=wall)
    res["wall_s"] = wall
    try:
        for f in (job, out):
            f.unlink()
        workdir.rmdir()
    except OSError:
        pass
    return res


def child_python() -> str:
    """The repo venv interpreter (has pyzx/pytket/bqskit/pygridsynth) when present, else this interpreter."""
    v = REPO / ".venv" / "bin" / "python"
    return str(v) if v.exists() else sys.executable


def _kill(proc) -> None:
    """Kill the child's whole session (it was started with start_new_session=True)."""
    import signal
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        try:
            proc.kill()
        except OSError:
            pass
