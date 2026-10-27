"""The playbook: tiers, loading, credit, retirement (V4_README sections 4 and 5).

Two tiers:

    floor/      pretrained reimplementations of the BASELINES, admitted before the loop sees a circuit and
                NEVER retired. The design contract (V4_README section 4) is that the floor alone reaches
                the best of every baseline on every circuit, using only Python over `v4.api` - no bqskit,
                pyzx, pytket or qiskit. So the LLM's worst case is "ties the best baseline".
    accepted/   original discoveries. Retireable: a rule with no accepted application in two consecutive
                global loops leaves the book, so it never silently accumulates.

Only baseline reimplementations are permanent. `rules/rejected/`, `never_fires/`, `retired/` and
`candidates/` are holding areas, not part of the book.

    book()                     floor + accepted, as Rule objects
    load_rule(path)            import one rule file (checks the import allow-list first)
    digest(book)               stable hash of a book state, for `optimize_memo`
    credit(name, result)       record that a rule had accepted applications in this global loop
    retire(book, loops=2)      -> (kept, retired) by the two-global-loop rule; floor rules never retire
    write_book_md()            regenerate rules/BOOK.md (what the scout reads - V4_README 4.4)
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

from .api import Rule
from .paths import ACCEPTED, BOOK_MD, CANDIDATES, FLOOR, RESULTS, RULES

ALLOWED_ROOTS = {"numpy", "scipy", "sympy"}
FORBIDDEN_ROOTS = {"pyzx", "pytket", "bqskit", "qiskit", "circuitevolve", "cvdv", "src", "v3"}
CREDIT_FILE = RESULTS / "credit.json"


# ------------------------------------------------------------------------------------------ static check
def static_check(path: Path) -> str:
    """'' if the file imports only stdlib, numpy, scipy, sympy and v4.api; else the reason."""
    try:
        tree = ast.parse(Path(path).read_text())
    except SyntaxError as e:
        return f"syntax error: {e}"
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                return "relative import"
            names = [node.module or ""]
        for n in names:
            root = n.split(".")[0]
            if n == "v4.api" or n.startswith("v4.api."):
                continue
            if root in FORBIDDEN_ROOTS or root == "v4" or (root not in ALLOWED_ROOTS and
                                                           root not in sys.stdlib_module_names):
                return f"forbidden import {n!r}"
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in ("exec", "eval", "__import__", "open"):
            return f"forbidden call {node.func.id}()"
    return ""


# name -> the file it was loaded from. `Rule` is frozen and carries no path, and `v4.isolate` needs to
# rebuild a book in a child process, so the mapping is recorded here as rules load.
SRC: dict[str, Path] = {}


def load_rule(path, tier: str | None = None) -> Rule:
    path = Path(path)
    spec = importlib.util.spec_from_file_location(f"v4_rule_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    r = getattr(mod, "RULE", None)
    if not isinstance(r, Rule):
        raise TypeError(f"{path.name} does not define RULE = Rule(...)")
    if r.name != path.stem:
        raise ValueError(f"RULE.name {r.name!r} != file name {path.stem!r}")
    t = tier or ("floor" if path.parent.name == "floor" else "accepted")
    if r.tier != t:
        r = Rule(**{**{f: getattr(r, f) for f in r.__dataclass_fields__}, "tier": t})
    SRC[r.name] = path.resolve()
    return r


def floor_tier() -> list:
    return [load_rule(p, "floor") for p in sorted(FLOOR.glob("*.py")) if not p.name.startswith("_")]


def accepted_tier() -> list:
    return [load_rule(p, "accepted") for p in sorted(ACCEPTED.glob("*.py")) if not p.name.startswith("_")]


def book() -> list:
    """The live book: floor first (reconstruction kinds still sort ahead inside the runner), then accepted."""
    return floor_tier() + accepted_tier()


# ------------------------------------------------------------------------------------------ digest
def rule_digest(r: Rule) -> str:
    """Hash of what makes a rule behave: its source file plus its declared tags."""
    for d in (FLOOR, ACCEPTED, CANDIDATES, RULES / "retired"):
        p = d / f"{r.name}.py"
        if p.is_file():
            h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
            break
    else:
        h = "nofile"
    return f"{r.name}:{h}:{r.error_class}/{r.resource_class}:{r.kind}"


def digest(bk) -> str:
    """Stable hash of a BOOK STATE. `optimize_memo` is keyed on it, so a given (book, circuit, eps) is
    verified once, ever - not once per test_rule call and not once per attempt."""
    return hashlib.sha256("|".join(rule_digest(r) for r in bk).encode()).hexdigest()[:16]


# ------------------------------------------------------------------------------------------ credit
def _credit() -> dict:
    return json.loads(CREDIT_FILE.read_text()) if CREDIT_FILE.exists() else dict(loop=0, last_used={})


def credit(names, loop: int) -> dict:
    """Record that each rule in `names` had at least one accepted application in global loop `loop`."""
    c = _credit()
    c["loop"] = max(int(loop), c.get("loop", 0))
    for n in names:
        c["last_used"][n] = int(loop)
    CREDIT_FILE.write_text(json.dumps(c, indent=1) + "\n")
    return c


def joined(names, loop: int) -> dict:
    """Record that each rule in `names` entered the book at global loop `loop`, without crediting it.

    A rule that is already in the book when a run STARTS has no credit entry, and `retire` used to read
    that as "never used" and drop it at the first retirement check - ignoring the grace window entirely.
    Seeding the joining loop here is what gives such a rule its `loops` loops to earn its place."""
    c = _credit()
    for n in names:
        c.setdefault("joined", {}).setdefault(n, int(loop))
    CREDIT_FILE.write_text(json.dumps(c, indent=1) + "\n")
    return c


def retire(bk, loop: int, loops: int = 2, opportunities=None) -> tuple:
    """(kept, [(name, reason)]) - an `accepted` rule with no accepted application in `loops` consecutive
    global loops leaves the book. Floor rules never retire.

    `opportunities` is the set of rule names that COULD have fired in this window - a rule whose
    precondition admits no circuit in the run's `circuit_order` never had a chance, and retiring it is
    not evidence about the rule. Leaving this out once retired all seven accepted rules after a single
    loop of a six-circuit run, including the one behind the project's best result (tfim_6 -60.8%), purely
    because tfim_6 was not among the six; the book collapsed to the floor tier and adder_8 went 216 ->
    399 mid-run."""
    c = _credit()
    kept, gone = [], []
    for r in bk:
        if r.tier == "floor":
            kept.append(r)
            continue
        if opportunities is not None and r.name not in opportunities:
            kept.append(r)
            continue
        last = c["last_used"].get(r.name)
        if last is None:
            last = c.get("joined", {}).get(r.name)
        if last is not None and loop - last >= loops:
            gone.append((r.name, f"no accepted application since loop {last} (now {loop}, limit {loops})"))
        else:
            kept.append(r)
    return kept, gone


# ------------------------------------------------------------------------------------------ BOOK.md
HEAD = """# Rule book (generated by v4/book.py; do not edit by hand)

The runner loads `rules/floor/` + `rules/accepted/`.

**floor tier** - reimplementations of the BASELINES, in Python over `v4.api`, never retired. The floor
alone is meant to reach the best of every baseline on every circuit, so a new idea is scored against the
best baseline, not against zero. Do not propose a floor rule's idea again.

**accepted tier** - original discoveries. Retired after two global loops with no accepted application.

| tier | name | kind | error | resources | idea | measured |
|---|---|---|---|---|---|---|
"""


def floor_table() -> str:
    """The floor's own measured T next to the best baseline, from the last floor_gate run.

    V4_README 4.4, "the trap": a floor tier silently changes what the scout sees. If the floor contains
    pyzx-class fusion and DPF-class fixing but BOOK.md does not SAY what the floor already reaches, the
    scout keeps proposing both and they come back as "no improvement beyond the book"."""
    import json as _json
    rows = []
    for p in sorted(RESULTS.glob("floor_gate_*.json")):
        rows = _json.loads(p.read_text())["rows"]
        src = p.name
    if not rows:
        return "_No floor_gate run recorded yet._\n"
    out = ["", f"## What the floor tier ALONE already reaches (eps 1e-3, from `results/{src}`)", "",
           "Do not propose an idea whose whole effect is to reach a number in the 'floor' column.", "",
           "| circuit | floor T | best baseline | its T | gap |", "|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['label']} | **{r['floor_t']}** | {r['best_baseline']} | {r['best_baseline_t']} | "
                   f"{r['gap']:+d} |")
    return "\n".join(out) + "\n"


def write_book_md(bk=None, path=None) -> Path:
    bk = book() if bk is None else bk
    path = Path(path or BOOK_MD)
    rows = []
    for r in bk:
        idea = r.idea.replace("|", "/").replace("\n", " ")
        ev = r.evidence.get("helped") or r.evidence.get("measured") or ""
        if isinstance(ev, dict):
            ev = "; ".join(f"{k}: {v}" for k, v in ev.items())
        rows.append(f"| {r.tier} | {r.name} | {r.kind} | {r.error_class} | {r.resource_class} | {idea} | "
                    f"{ev} |")
    path.write_text(HEAD + "\n".join(rows) + "\n" + floor_table())
    return path
