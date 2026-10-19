"""LLM backends: plain callables `complete(list[str]) -> list[str | Exception]`.

Shared by the window core (circuitevolve/core) and the legacy stacks. Moved verbatim from
circuitevolve/search/llm.py on 2026-10-13 (see docs/LLM_BACKENDS.md):
  * make_api_backend()  - wraps a batch LLM callable with the `host.llm` signature
                          (`llm(list[dict], max_concurrency=...) -> list[dict]`); thinking disabled by
                          default; error dicts and empty text are errors; bounded retries with backoff.
                          The callable is passed in: this module never imports `host`.
  * make_batch_merger() - merges concurrent requests from several threads into one batch call.
  * make_cli_backend()  - `claude -p` subprocess in an EMPTY temp dir.
A backend carries a `stats` Counter (calls/ok/errors/retries/tokens).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import time
from collections import Counter


_TRANSIENT = ("connection", "connect", "timed out", "timeout", "overloaded", "529", "503", "502", "500 ",
              "rate limit", "rate_limit", "429", "temporarily", "try again", "reset by peer", "eof", "empty text")
_FATAL = ("ceiling", "invalid_request", "authentication", "permission", "not logged in", "usage limit",
          "credit balance")


def is_transient(msg: str) -> bool:
    m = str(msg).lower()
    return not any(w in m for w in _FATAL) and any(w in m for w in _TRANSIENT)


def make_api_backend(llm, model=None, max_tokens: int = 8000, max_concurrency: int = 4, thinking: bool = False,
                     retries: int = 3, backoff: float = 5.0, sleep=time.sleep, system=None):
    """Backend over a batch LLM callable with the `host.llm` list signature.

    llm(list[dict], max_concurrency=int) -> list[dict]; each result has "text" (and "stop_reason",
    "usage") or "error". Pass e.g. `llm=host.llm, model=host.reasoning_model()` from a platform kernel.
    `model` may be a string or a zero-argument callable (resolved per batch).
    thinking=False sends {"type": "disabled"}: with thinking on, the model can spend the whole
    max_tokens budget thinking and return empty text.
    Failures (error dicts, empty text, exceptions raised by `llm`) are returned as RuntimeError;
    transient ones (see is_transient; empty text counts as transient) are re-issued up to `retries`
    times with exponential backoff. Counts in `complete.stats`.
    """
    stats = Counter()

    def _req(prompt):
        m = model() if callable(model) else model
        r = {"prompt": prompt, "max_tokens": max_tokens}
        if m:
            r["model"] = m
        if isinstance(thinking, dict):              # newest-gen models reject "disabled" and
            r["thinking"] = thinking                # require e.g. {"type": "adaptive"}
        elif not thinking:
            r["thinking"] = {"type": "disabled"}
        if system:
            r["system"] = system
        return r

    def complete(prompts):
        out = [None] * len(prompts)
        pending = list(range(len(prompts)))
        stats["calls"] += len(prompts)
        for attempt in range(retries + 1):
            try:
                res = llm([_req(prompts[i]) for i in pending], max_concurrency=max_concurrency)
                if not isinstance(res, list) or len(res) != len(pending):
                    raise RuntimeError(f"api: backend returned {type(res).__name__} of len "
                                       f"{len(res) if hasattr(res, '__len__') else '?'} for {len(pending)} requests")
            except Exception as e:          # whole-batch failure (connection, ceiling, ...)
                res = [{"error": f"{type(e).__name__}: {e}"}] * len(pending)
            retry = []
            for i, r in zip(pending, res):
                r = r if isinstance(r, dict) else {"error": f"non-dict result {type(r).__name__}"}
                u = r.get("usage") or {}
                stats["input_tokens"] += int(u.get("input_tokens", 0) or 0)
                stats["output_tokens"] += int(u.get("output_tokens", 0) or 0)
                if r.get("error"):
                    msg = f"api: {str(r['error'])[:300]}"
                    kind = "error"
                elif not (r.get("text") or "").strip():
                    msg = f"api: empty text (stop_reason={r.get('stop_reason')})"
                    kind = "empty"
                else:
                    if r.get("stop_reason") == "max_tokens":
                        stats["truncated"] += 1
                    out[i] = r["text"]
                    stats["ok"] += 1
                    continue
                stats[kind] += 1
                out[i] = RuntimeError(msg)
                if attempt < retries and (kind == "empty" or is_transient(msg)):
                    retry.append(i)
            if not retry:
                break
            stats["retries"] += len(retry)
            sleep(backoff * 2 ** attempt)
            pending = retry
        stats["failed"] += sum(isinstance(o, Exception) for o in out)
        return out

    complete.stats = stats
    return complete


def make_batch_merger(llm, window: float = 1.0, max_concurrency: int = 12):
    """Thread-safe wrapper around a batch LLM callable (`host.llm` list form) that merges requests
    issued concurrently by several search threads into one batch call, so N concurrent runs share one
    host round-trip instead of serialising. One caller at a time acts as dispatcher; the others wait.
    The returned callable has the same signature: merged(list[dict], max_concurrency=...) -> list[dict].
    """
    import threading
    lock = threading.Lock()
    queue, state = [], {"busy": False}

    def merged(reqs, max_concurrency_=None, **_ignored):
        slot = {"reqs": list(reqs), "ev": threading.Event(), "res": None}
        with lock:
            queue.append(slot)
        while True:
            with lock:
                if slot["res"] is not None:
                    return slot["res"]
                lead = not state["busy"]
                if lead:
                    state["busy"] = True
            if not lead:
                slot["ev"].wait(0.25)
                continue
            try:
                time.sleep(window)                       # let concurrent callers join this batch
                with lock:
                    batch = queue[:]
                    queue.clear()
                flat = [r for s in batch for r in s["reqs"]]
                try:
                    res = llm(flat, max_concurrency=max_concurrency)
                    if not isinstance(res, list) or len(res) != len(flat):
                        raise RuntimeError(f"merged batch returned {type(res).__name__}")
                except Exception as e:
                    res = [{"error": f"{type(e).__name__}: {e}"}] * len(flat)
                j = 0
                for s in batch:
                    s["res"] = res[j:j + len(s["reqs"])]
                    j += len(s["reqs"])
                    s["ev"].set()
            finally:
                with lock:
                    state["busy"] = False

    def call(reqs, max_concurrency=None, **kw):
        return merged(reqs, max_concurrency)
    return call


def make_cli_backend(model: str | None = None, timeout: int = 300, binary: str | None = None, workers: int = 4,
                     retries: int = 1, retry_timeouts: bool = False, backoff: float = 10.0, extra_args=(),
                     sleep=time.sleep, runner=subprocess.run):
    """`claude -p` backend. Runs in an empty temp dir; treats is_error / non-success as failures.

    Diagnostics: on exit != 0 the CLI usually writes its error to *stdout* (with --output-format json
    as a JSON object with is_error/subtype/result), not stderr; the message records subtype, result head
    and stdout/stderr heads. timeout is configurable; transient failures (is_transient) are retried up
    to `retries` times; timeouts only if retry_timeouts. extra_args are appended to the command (e.g.
    ("--max-turns", "1")). See docs/LLM_BACKENDS.md. Counts in `complete.stats`.
    """
    import os
    import shutil
    from concurrent.futures import ThreadPoolExecutor

    binary = binary or shutil.which("claude") or next(
        (p for p in ("/opt/homebrew/bin/claude", "/usr/local/bin/claude", os.path.expanduser("~/.claude/local/claude"))
         if os.path.exists(p)), "claude")
    stats = Counter()

    def _head(s, n=300):
        return (s or "").strip().replace("\n", " | ")[:n]

    def attempt(prompt: str):
        cmd = [binary, "-p", "--output-format", "json"] + (["--model", model] if model else []) + list(extra_args)
        t0 = time.time()
        with tempfile.TemporaryDirectory() as d:
            try:
                p = runner(cmd, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=d)
            except subprocess.TimeoutExpired:
                return "timeout", RuntimeError(f"cli: timeout after {timeout}s")
            except OSError as e:
                return "oserror", RuntimeError(f"cli: cannot run {binary}: {e}")
        dt = time.time() - t0
        js = None
        try:
            js = json.loads(p.stdout) if p.stdout and p.stdout.strip() else None
        except json.JSONDecodeError:
            js = None
        if p.returncode != 0:
            if isinstance(js, dict):
                detail = (f"subtype={js.get('subtype')} is_error={js.get('is_error')} "
                          f"result={_head(str(js.get('result')), 200)}")
            else:
                detail = f"stdout={_head(p.stdout)!r}"
            return "exit", RuntimeError(f"cli: exit {p.returncode} after {dt:.0f}s: {detail} stderr={_head(p.stderr, 200)!r}")
        if not isinstance(js, dict):
            return "bad_json", RuntimeError(f"cli: stdout is not a JSON object: {_head(p.stdout, 200)!r}")
        if js.get("is_error") or js.get("subtype") != "success" or not js.get("result"):
            return "is_error", RuntimeError(f"cli: is_error={js.get('is_error')} subtype={js.get('subtype')} "
                                            f"result={_head(str(js.get('result')), 160)}")
        return "ok", js["result"]

    def one(prompt: str):
        for k in range(retries + 1):
            kind, res = attempt(prompt)
            stats[kind] += 1
            if kind == "ok":
                return res
            retryable = (kind == "timeout" and retry_timeouts) or (kind != "timeout" and is_transient(str(res)))
            if k == retries or not retryable:
                return res
            stats["retries"] += 1
            sleep(backoff * 2 ** k)
        return res

    def complete(prompts):
        stats["calls"] += len(prompts)
        with ThreadPoolExecutor(workers) as ex:
            out = list(ex.map(one, prompts))
        stats["failed"] += sum(isinstance(o, Exception) for o in out)
        return out

    complete.stats = stats
    return complete
