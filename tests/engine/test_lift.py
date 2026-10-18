"""P3.4 gates: structure lifting (engine/lift.py).

(a) zero false structures — every substitution is exactly verified in D[omega] by
construction; re-verified here whole-circuit on a lifted base twin; (c) lift never fires
when ccx is present (raw path unchanged). The routing/e2e gate (b) lives in test_cascade.py.
"""
from __future__ import annotations

import json

from circuitevolve.blocks import REPO
from circuitevolve.engine.lift import expand_toffolis, lift_toffolis, pre_recognize
from circuitevolve.engine.router import route
from circuitevolve.engine.tketpass import read_qasm_ops

RB = REPO / "results" / "engine" / "recon_bench"

TOF7 = [("h", (2,)), ("cx", (1, 2)), ("tdg", (2,)), ("cx", (0, 2)), ("t", (2,)),
        ("cx", (1, 2)), ("tdg", (2,)), ("cx", (0, 2)), ("t", (1,)), ("t", (2,)),
        ("h", (2,)), ("cx", (0, 1)), ("t", (0,)), ("tdg", (1,)), ("cx", (0, 1))]
RCCX = [("h", (2,)), ("t", (2,)), ("cx", (1, 2)), ("tdg", (2,)), ("cx", (0, 2)),
        ("t", (2,)), ("cx", (1, 2)), ("tdg", (2,)), ("h", (2,))]


def _ops(pairs):
    return [(g, qs, None) for g, qs in pairs]


def test_canonical_7t_lifts_with_commuting_interleave():
    interleaved = _ops(TOF7[:3] + [("x", (4,)), ("cx", (3, 4))] + TOF7[3:])
    lifted, rep = lift_toffolis(interleaved, 5)
    assert rep["ccx"] == 1 and rep["t_absorbed"] == 7
    assert [op for op in lifted if op[0] == "ccx"] == [("ccx", (0, 1, 2), None)]
    assert ("x", (4,), None) in lifted and ("cx", (3, 4), None) in lifted


def test_rccx_is_spotted_but_not_substituted_by_default():
    lifted, rep = lift_toffolis(_ops(RCCX), 3)
    assert rep["rccx_spotted"] == 1 and rep["rccx_substituted"] == 0 and rep["ccx"] == 0
    assert lifted == _ops(RCCX)                     # untouched
    lifted2, rep2 = lift_toffolis(_ops(RCCX), 3, substitute_rccx=True)
    assert rep2["rccx_substituted"] == 1 and lifted2 == [("rccx", (0, 1, 2), None)]


def test_roundtrip_expand_then_lift_is_identity_cuccaro_4():
    n, raw = read_qasm_ops((REPO / "benchmarks/nam_arith/generated/cuccaro_4.qasm").read_text())
    lifted, rep = lift_toffolis(expand_toffolis(raw), n)
    assert rep["ccx"] == 8 and lifted == raw        # exact op-for-op recovery


def test_zero_false_structures_whole_circuit_exact():
    """Lift a nested-recursion circuit (macro claims) and compare the FULL circuit exactly
    in D[omega] on basis inputs — any false structure would break a column."""
    from circuitevolve.ir import Circuit as IRC
    from circuitevolve.sim import run
    n, raw = read_qasm_ops((REPO / "benchmarks/nam_arith/logical/barenco_tof_5.qasm").read_text())
    exp = expand_toffolis(raw)
    lifted, rep = lift_toffolis(exp, n)
    assert rep["ccx"] == 12

    def circ(ops):
        c = IRC(n)
        for g, qs, _a in ops:
            c.add(g, *qs)
        return c.expand("clifford_t")

    a, b = circ(exp), circ(lifted)
    for inp in (0, 1, 5, 21, 97, (1 << n) - 1):
        assert run(a, inp) == run(b, inp), inp


def test_lift_never_fires_when_ccx_present():
    text, rep = pre_recognize(str(REPO / "benchmarks/nam_arith/generated/cuccaro_4.qasm"))
    assert text is None and "already present" in rep["skipped"]
    # routing: a Toffoli-bearing input routes WITHOUT lift evidence
    c = route(str(REPO / "benchmarks/nam_arith/generated/cuccaro_4.qasm"), log=False)
    assert all("lift" not in b.evidence for b in c) and all(b.lifted_source is None for b in c)


def test_stress_twins_recorded_honestly():
    rep = json.loads((RB / "lifting_report.json").read_text())
    rows = {r["circuit"]: r for r in rep["circuits"]}
    assert len(rows) == 11
    for r in rows.values():
        assert r["stress"]["recovered_ccx"] == 0        # the documented finding
        assert r["base"]["recovery_rate"] == 1.0        # macro-expanded base: full recovery
        assert r["base"]["t_conserved"] is True
    assert "FullPeepholeOptimise" in rep["finding"]


def test_plain_twin_routes_reconstruction_then_angle():
    """P3.4 gate (b), routing half: decomposed_plain cuccaro_4 (Toffoli-free Clifford+T)
    lifts in pre-recognition and routes [reconstruction, angle] with lift evidence."""
    c = route(str(RB / "decomposed_plain" / "cuccaro_4.qasm"), log=False)
    assert [b.method for b in c] == ["reconstruction", "angle"]
    assert c[0].evidence["lift"]["ccx"] == 8
    assert c[0].lifted_source is not None and "ccx" in c[0].lifted_source
    assert c[0].evidence["pairs"] >= 1                  # recognizer sees the lifted structure
