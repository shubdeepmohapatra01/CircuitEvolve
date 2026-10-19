"""Tier 1 NO-LLM CONTROL: deterministic plans from the recognizer output, evaluated at the same budget as the LLM arm.

Variants (route sets):
  V1 'spec'         the heuristic named in the task: every 'clean' compute/uncompute pair -> temporary_and (direct);
                    every other Toffoli -> toffoli_7T.
  V2 'max_relaxed'  cheapest relaxed route everywhere it is allowed: clean pairs -> temporary_and; other ccx pairs
                    (mirror / controls_fixed) -> temporary_and via a fresh ancilla; unpaired ccx whose target is a
                    declared zero-init qubit that is |0> at that point -> clean_and; every other Toffoli ->
                    jones_toffoli.
  V3 'max_exact'    unitary-preserving: every ccx pair whose target is not written in between (clean or mirror) ->
                    relative_phase_toffoli; others toffoli_7T.
  V4 'plain'        all toffoli_7T (= the global pass on the logical circuit).
Evaluation order (truncated to the budget): every variant with pyzx first, then the other passes.
"""
from __future__ import annotations

from .plan import Decision, Plan
from .recognize import LogicalCircuit, Summary, first_toffoli_on_clean

ORDER = [("V1", "pyzx"), ("V2", "pyzx"), ("V3", "pyzx"), ("V4", "pyzx"),
         ("V2", "none"), ("V1", "none"), ("V3", "none"),
         ("V2", "pyzx_then_tket"), ("V3", "pyzx_then_tket"),
         ("V2", "tket"), ("V3", "tket"), ("V1", "tket"), ("V1", "pyzx_then_tket"),
         ("V4", "none"), ("V4", "tket"), ("V4", "pyzx_then_tket")]
NAMES = {"V1": "spec", "V2": "max_relaxed", "V3": "max_exact", "V4": "plain"}


def variant_decisions(lc: LogicalCircuit, s: Summary, v: str) -> list:
    d = []
    if v == "V1":
        d = [Decision(p["id"], "temporary_and") for p in s.pairs if p["cls"] == "clean"]
    elif v == "V2":
        paired = set()
        for p in s.pairs:
            if p["cls"] == "clean":
                d.append(Decision(p["id"], "temporary_and"))
            else:
                d.append(Decision(p["id"], "temporary_and", via_ancilla=True))
            paired.update((p["first"], p["second"]))
        clean = first_toffoli_on_clean(lc, s)
        for t in s.toffolis:
            if t["id"] in paired:
                continue
            d.append(Decision(t["id"], "clean_and" if clean.get(t["id"]) else "jones_toffoli"))
    elif v == "V3":
        d = [Decision(p["id"], "relative_phase_toffoli") for p in s.pairs
             if p["kind"] == "ccx" and not p["target_written_between"]
             and p["cls"] != "and_preserving"]   # G2 pairs: control VALUES differ at the two
             # members, so RCCX phases would not cancel — relaxed routes only
    elif v == "V4":
        d = []
    else:
        raise ValueError(v)
    return d


def control_plans(lc: LogicalCircuit, s: Summary, budget: int) -> list:
    """[(variant, pass, Plan)] in evaluation order, len = min(budget, len(ORDER))."""
    out = []
    for v, gp in ORDER[:max(0, budget)]:
        out.append((v, gp, Plan(variant_decisions(lc, s, v), gp, target="relaxed" if v in ("V1", "V2") else "exact",
                                rationale=f"control {v} ({NAMES[v]}) + {gp}")))
    return out
