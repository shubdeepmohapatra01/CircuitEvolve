"""Tier-0 router v1 (PLAN_P3 P3.2): method predicates + cascade — deterministic code over
recognizer features, never prose.

route(source, manifest) -> ordered list[MethodBinding] (the cascade). Methods are
METHOD-scoped, not circuit-class-scoped (PLAN_P3 §1.1): `reconstruction` (construction
substitution, relaxed contract), `angle` (rotation/window polish, approx contract — the
dv.windows stack), `cvdv` (certified subspace, term input, input-type-disjoint). ALL
applicable methods run, most-structural first; predicates (PLAN_P3 §5.1, settled):

    cvdv            Hamiltonian term input (disjoint single-stage cascade)
    reconstruction  toffolis >= 1 AND (>=1 Toffoli pair OR >=1 MCX cascade OR
                    toffoli-naive-T share >= 20%); pair/MCX evidence from the v2 recognizer
                    on the RAW input (counts-only fallback when the exact-IR parse fails)
    angle           >=1 non-Clifford rotation, where T gates and Toffolis count as
                    non-Clifford rotation content: rz_nonclifford + t_like + toffolis >= 1

Pure-Clifford input: NO method fires -> route() returns [] (optimize() returns the input
unchanged — not an error). Recognize/route on the RAW input; decompose late (§1.3): the TKET
entry pass lives inside the angle method, never before reconstruction. A manifest
{"family"|"method": ...} override picks a single-stage cascade and is logged as such.
Every decision is appended to results/engine/routing_log.jsonl with features + evidence
(auditable, A/B-testable like any proposal-side component). NO LLM in routing; no triage call.

Frozen names: the angle method keeps family label "dv.windows" (playbook path + graduated
index key, G1 frozen); cvdv keeps "cvdv.bosonic". FamilyBinding remains for pre-/1 consumers;
MethodBinding is the cascade row (open decision 3 settled: its own dataclass carrying the
FamilyBinding fields plus method/rank/status/evidence).
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
    if isinstance(source, dict) and ("terms" in source or "hamiltonian" in source or "benchmark" in source):
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


# ------------------------------------------------------------------ method evidence
def _t_like(feats: dict) -> int:
    c = feats.get("counts", {})
    return c.get("t", 0) + c.get("tdg", 0)


def _toffoli_share(feats: dict) -> float:
    naive = 7 * feats.get("toffolis", 0)
    denom = naive + _t_like(feats)
    return (naive / denom) if denom else 0.0


def recon_evidence(source, feats: dict) -> dict:
    """Deterministic structural evidence for the reconstruction predicate, computed on the
    RAW input (PLAN_P3 §1.3). Pair/MCX counts come from the v2 recognizer when the input is
    QASM text/path in the exact-IR gate set; otherwise counts-only (share criterion alone).
    Routing has no benchmark manifest, so pair CLASSES here ignore declared-zero contracts —
    the reconstruction method re-recognizes with the full contract before planning."""
    ev = dict(toffolis=feats.get("toffolis", 0), t_like=_t_like(feats),
              toffoli_naive_t_share=round(_toffoli_share(feats), 4), pairs=None, mcx=None)
    if ev["toffolis"] == 0:
        ev["fires"] = False
        return ev
    if isinstance(source, (str, Path)):
        try:
            from ..v2.tier1.recognize import load_logical, summarize
            _, lc = load_logical(str(source))
            s = summarize(lc)
            ev.update(pairs=len(s.pairs), mcx=len(s.mcx),
                      pairs_by_class={p["cls"]: sum(1 for q in s.pairs if q["cls"] == p["cls"])
                                      for p in s.pairs})
        except Exception as err:  # exact-IR parse failed: counts-only evidence
            ev["recognizer"] = f"unavailable ({type(err).__name__}: {err})"
    ev["fires"] = bool((ev["pairs"] or 0) >= 1 or (ev["mcx"] or 0) >= 1
                       or ev["toffoli_naive_t_share"] >= 0.2)
    return ev


@dataclass
class MethodBinding:
    """One cascade stage (open decision 3: FamilyBinding fields + method/rank/status/evidence).
    `family` keeps the FROZEN label recorded state references ('dv.windows', 'cvdv.bosonic');
    `graduated_family` is the graduated-index lookup alias (§2)."""
    method: str
    family: str
    plugin: str | None
    contract: str
    playbook: str
    graduated_family: str
    rank: int
    reason: str
    status: str = "active"
    features: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)
    lifted_source: str | None = None    # P3.4: lifted QASM text when pre-recognition fired


def _bind(method: str, row: dict, reason: str, feats: dict, evidence: dict | None = None) -> MethodBinding:
    return MethodBinding(method=method, family=row["family"], plugin=row.get("plugin"),
                         contract=row["contract"], playbook=row["playbook"],
                         graduated_family=row.get("graduated_family", row["family"]),
                         rank=row.get("rank", 0), reason=reason,
                         status=row.get("status", "active"), features=feats,
                         evidence=evidence or {})


# ------------------------------------------------------------------ routing
def route(source, manifest: dict | None = None, table_path: Path | None = None,
          log: bool = True) -> list[MethodBinding]:
    """Ordered cascade of applicable methods (may be empty: pure-Clifford input)."""
    table = load_table(table_path)
    methods = table["methods"]
    feats = features_of(source, manifest)
    override = (manifest or {}).get("method") or (manifest or {}).get("family")
    if override:
        key = {"dv.windows": "angle", "cvdv.bosonic": "cvdv"}.get(override, override)
        row = methods.get(key)
        if row is None:
            reason = f"manifest override '{override}' names no known method {sorted(methods)}"
            _log_decision(dict(cascade=[], reason=reason, features=feats, table=table["format"]), log)
            raise NeedsTriage(reason, feats)
        cascade = [_bind(key, row, "manifest override", feats)]
    elif feats["input_type"] == "terms":
        cascade = [_bind("cvdv", methods["cvdv"], "Hamiltonian term input", feats)]
    else:
        cascade = []
        lifted_text, lift_rec = None, None
        if (isinstance(source, (str, Path)) and feats.get("toffolis", 0) == 0
                and _t_like(feats) >= 7):               # P3.4 pre-recognition: fires ONLY here
            from .lift import pre_recognize
            lifted_text, lift_rec = pre_recognize(source)
            if lifted_text is not None:
                source = lifted_text                    # recognize/route on the lifted form
                feats = features_of(source, manifest)
                feats["lift"] = {k: v for k, v in lift_rec.items() if k != "claims"}
        ev = recon_evidence(source, feats)
        if lift_rec is not None and lifted_text is not None:
            ev["lift"] = feats["lift"]
        if ev["fires"]:
            cascade.append(_bind("reconstruction", methods["reconstruction"],
                                 f"structural: {ev['toffolis']} Toffolis, pairs={ev['pairs']}, "
                                 f"mcx={ev['mcx']}, naive-T share {ev['toffoli_naive_t_share']}",
                                 feats, ev))
        t_nc = feats["rz_nonclifford"] + _t_like(feats) + feats["toffolis"]
        if t_nc >= 1:
            cascade.append(_bind("angle", methods["angle"],
                                 f"{feats['rz_nonclifford']} non-Clifford rz, {_t_like(feats)} t/tdg, "
                                 f"{feats['toffolis']} Toffolis (non-Clifford content {t_nc})",
                                 feats))
        cascade.sort(key=lambda b: b.rank)
        if lifted_text is not None:
            for b in cascade:
                b.lifted_source = lifted_text           # optimize() executes on the lifted form
    _log_decision(dict(cascade=[{k: v for k, v in asdict(b).items()
                                 if k not in ("features", "evidence", "lifted_source")}
                                for b in cascade],
                       reason=(cascade[0].reason if cascade else
                               "no method applicable (pure-Clifford input): returned unchanged"),
                       features=feats,
                       evidence=(cascade[0].evidence if cascade and cascade[0].evidence else None),
                       table=table["format"]), log)
    return cascade


def _log_decision(decision: dict, log: bool):
    if not log:
        return
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:                                       # append-only
        f.write(json.dumps(dict(ts=round(time.time(), 1), **decision)) + "\n")
