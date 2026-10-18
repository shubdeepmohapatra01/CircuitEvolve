"""Tier-0 router (PLAN_P1 P1.4): deterministic code over recognizer features — never prose.

route(source, manifest) -> FamilyBinding. v0 table:
    Hamiltonian term input                         -> cvdv.bosonic  (certified-subspace contract)
    QASM, 0 Toffolis, >=1 non-Clifford rz          -> dv.windows    (approx contract)
    anything else                                  -> NeedsTriage   (logged; the LLM triage
                                                      fallback and the arithmetic family land
                                                      in point 3 — the run refuses politely)
Every decision (including NeedsTriage) is appended to results/engine/routing_log.jsonl with the
feature vector and the table version, so routing is auditable and A/B-testable like any other
proposal-side component. A manifest {"family": ...} override is honored and logged as such.
"""
from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..blocks import REPO
from ..blocks.circuit_io import classify_angle

TABLE = REPO / "playbooks" / "router.json"
LOG = REPO / "results" / "engine" / "routing_log.jsonl"


class NeedsTriage(RuntimeError):
    """No family matched deterministically. Carries the feature vector for the (future) LLM
    triage fallback; in P1 the caller surfaces this to the user instead of guessing."""

    def __init__(self, reason: str, features: dict):
        super().__init__(reason)
        self.reason, self.features = reason, features


@dataclass
class FamilyBinding:
    family: str
    plugin: str
    contract: str
    playbook: str
    graduated: list
    reason: str
    features: dict = field(default_factory=dict)


def load_table(path: Path | None = None) -> dict:
    t = json.loads(Path(path or TABLE).read_text())
    assert t["format"].startswith("circuitevolve.engine.router/"), "unknown router table format"
    return t


# ------------------------------------------------------------------ features (deterministic)
def _is_terms(source, manifest) -> bool:
    if isinstance(source, dict) and ("terms" in source or "hamiltonian" in source):
        return True
    if isinstance(source, (str, Path)) and str(source).endswith((".terms.json", ".terms")):
        return True
    return False


_GATE = re.compile(r"^\s*([a-z][a-z0-9]*)\s*(?:\(([^)]*)\))?\s+q", re.I)
_QREG = re.compile(r"^\s*qreg\s+\w+\s*\[\s*(\d+)\s*\]", re.I | re.M)
_ANGLE = re.compile(r"^\s*([+-]?)\s*(\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)?\s*\*?\s*(pi)?\s*(?:/\s*(\d+(?:\.\d*)?))?\s*$")
_NOT_GATES = {"qreg", "creg", "include", "gate", "measure", "barrier", "reset", "if"}


def _parse_angle(expr: str) -> float | None:
    """Literal angle forms only (FLOAT, FLOAT*pi, pi/INT, ...); None if unparseable — no eval."""
    m = _ANGLE.match(expr.strip())
    if not m or (m.group(2) is None and m.group(3) is None):
        return None
    sign = -1.0 if m.group(1) == "-" else 1.0
    v = float(m.group(2)) if m.group(2) else 1.0
    if m.group(3):
        v *= math.pi
    if m.group(4):
        v /= float(m.group(4))
    return sign * v


def _scan_qasm(text: str) -> dict:
    """Literal line scan: gate counts + rz angles. Routing needs counts, not semantics."""
    counts: dict = {}
    rz_nc = 0
    for line in text.splitlines():
        m = _GATE.match(line.split("//")[0])
        if not m or m.group(1).lower() in _NOT_GATES:
            continue
        g = m.group(1).lower()
        counts[g] = counts.get(g, 0) + 1
        if g in ("rz", "rx", "ry", "u1", "p") and m.group(2) is not None:
            a = _parse_angle(m.group(2))
            if a is None or classify_angle(a) is None:
                rz_nc += 1              # unparseable counts as non-Clifford (conservative)
    n = sum(int(x) for x in _QREG.findall(text))
    return dict(n=n, gates=sum(counts.values()), counts=counts,
                toffolis=counts.get("ccx", 0) + counts.get("ccz", 0) + counts.get("mcx", 0),
                rz_nonclifford=rz_nc)


def features_of(source, manifest: dict | None = None) -> dict:
    if _is_terms(source, manifest):
        return dict(input_type="terms")
    if isinstance(source, list):                                   # core op tuples
        counts: dict = {}
        for g, _, _ in source:
            counts[g] = counts.get(g, 0) + 1
        rz_nc = sum(1 for g, _, a in source if g == "rz" and classify_angle(a) is None)
        n = 1 + max((max(qs) for _, qs, _ in source), default=0)
        return dict(input_type="qasm", n=n, gates=len(source), counts=counts,
                    toffolis=counts.get("ccx", 0) + counts.get("ccz", 0), rz_nonclifford=rz_nc)
    s = str(source)
    text = s if s.lstrip().startswith("OPENQASM") else Path(s).read_text()
    return dict(input_type="qasm", **_scan_qasm(text))


# ------------------------------------------------------------------ routing
def route(source, manifest: dict | None = None, table_path: Path | None = None, log: bool = True) -> FamilyBinding:
    table = load_table(table_path)
    feats = features_of(source, manifest)
    override = (manifest or {}).get("family")
    if override:
        fam, reason = override, "manifest override"
    elif feats["input_type"] == "terms":
        fam, reason = "cvdv.bosonic", "Hamiltonian term input"
    elif feats["toffolis"] == 0 and feats["rz_nonclifford"] > 0:
        fam, reason = "dv.windows", (f"QASM, 0 Toffolis, {feats['rz_nonclifford']} non-Clifford rz "
                                     "(rotation-dominated)")
    else:
        reason = (f"no deterministic family match (toffolis={feats.get('toffolis')}, "
                  f"rz_nonclifford={feats.get('rz_nonclifford')}); "
                  "arithmetic family + LLM triage land in point 3")
        _log_decision(dict(family=None, reason=reason, features=feats, table=table["format"]), log)
        raise NeedsTriage(reason, feats)
    row = table["families"].get(fam)
    if row is None or row.get("status") == "reserved" or row.get("plugin") is None:
        reason2 = f"family '{fam}' is not available yet ({(row or {}).get('status', 'missing')})"
        _log_decision(dict(family=fam, reason=reason2, features=feats, table=table["format"]), log)
        raise NeedsTriage(reason2, feats)
    b = FamilyBinding(family=fam, plugin=row["plugin"], contract=row["contract"], playbook=row["playbook"],
                      graduated=row.get("graduated", []), reason=reason, features=feats)
    _log_decision(dict(**{k: v for k, v in asdict(b).items() if k != "features"}, features=feats,
                       table=table["format"]), log)
    return b


def _log_decision(decision: dict, log: bool):
    if not log:
        return
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:                                       # append-only
        f.write(json.dumps(dict(ts=round(time.time(), 1), **decision)) + "\n")
