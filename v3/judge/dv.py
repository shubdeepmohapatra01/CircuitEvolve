"""DV judge (FROZEN): thin wrappers over existing, tested code.

    load(label)                         -> circuit (core Circuit for dv_angle, ir.Circuit for dv_recon)
    verify(candidate, reference, mode, eps) -> circuitevolve/v2/verify.Verdict   (modes exact / approx / relaxed)
    verify_window(orig_ops, new_ops, k, allowance)  -> circuitevolve/core/verifier.verify_window (local checks)
    measure(circuit, eps_synth)         -> {t_count, rotations, cx, qubits, ...}

measure: exact circuits (Clifford+T / Toffoli level, incl. gadgets and measurement) via v2.metric (frozen
cost.py, ccx/ccz = 7 T); circuits with continuous Rz via core/metric.BqskitTMetric (BQSKit convention:
gridsynth at eps_rz = eps_synth / N_Rz, pi/4 multiples exact), with its gridsynth cache in v3/.cache so the
judge writes nothing outside v3/.
"""
from __future__ import annotations

import json

from circuitevolve.blocks.cost_model import canonical_angle  # noqa: F401  (re-export for api)
from circuitevolve.core import verifier as _core_verifier
from circuitevolve.core.circuit import Circuit as CoreCircuit, normalize
from circuitevolve.core.metric import BqskitTMetric
from circuitevolve.ir import Circuit as IRCircuit
from circuitevolve.sim import run as _sim_run
from circuitevolve.v2 import metric as _v2_metric, verify as _v2_verify

from ..paths import CACHE, MANIFEST, V3
from .frozen import check_frozen

GS_CACHE = CACHE / "gridsynth_bqskit_conv"
_METRICS: dict = {}


def manifest_entry(label: str) -> dict:
    m = json.loads(MANIFEST.read_text())
    return next(c for c in m["circuits"] if c["label"] == label)


def load(label: str):
    c = manifest_entry(label)
    if c["domain"] != "dv":
        raise ValueError(f"{label} is not a DV circuit")
    text = (V3 / c["input"]).read_text()
    if c["family"] == "dv_angle":
        return CoreCircuit.from_qasm(text, name=label)
    return parse_logical(text)


CCZ_DEF = "gate ccz a,b,c { h c; ccx a,b,c; h c; }"


def parse_logical(text: str):
    """Toffoli-level QASM -> ir.Circuit. The Nam logical files declare `gate ccz` as h-ccx-h (= CCZ, the ir's
    native ccz); that exact definition line is dropped, any other gate definition is an error."""
    lines = []
    for raw in text.splitlines():
        if raw.strip().startswith("gate "):
            if raw.strip() != CCZ_DEF:
                raise ValueError(f"unsupported gate definition {raw!r}")
            continue
        lines.append(raw)
    return _v2_verify.parse_qasm_ir("\n".join(lines))


def reference(ref):
    """ReferenceSpec for `ref`. An ir.Circuit with more than 2^14 basis inputs that v2 does not see as
    permutation-like as written (the Nam files spell Toffolis as h-ccz-h, and Barenco circuits interleave them)
    becomes ReferenceSpec.from_function(f) with f(x) = the frozen exact simulator's output state of `ref` on |x>
    (circuitevolve/sim.run, D[omega]): the reference's own action, evaluated exactly per input. v2 then samples
    basis inputs for it (method '*-sampled', certified False) instead of refusing."""
    spec = _v2_verify.ReferenceSpec.from_circuit(ref)
    if isinstance(ref, IRCircuit) and not spec.permutation_like and \
            spec.n_valid_inputs > _v2_verify.Limits().max_exhaustive_inputs:
        def f(x, c=ref):
            (state,) = _sim_run(c, x).values()
            return dict(state)
        return _v2_verify.ReferenceSpec.from_function(ref.n_qubits, f, registers=dict(ref.registers))
    return spec


def verify(candidate, ref, mode: str = "exact", eps: float = 0.0, **kw):
    """v2 verify. Verdict.certified = True only for a proof (all basis inputs / dense operator norm); above 2^14
    inputs the exact / relaxed check samples basis inputs (method '*-sampled', certified False)."""
    check_frozen()
    return _v2_verify.verify(candidate, reference(ref), mode=mode, eps=eps, **kw)


def verify_window(orig_ops, new_ops, k: int, allowance: float) -> dict:
    return _core_verifier.verify_window(orig_ops, new_ops, k, allowance)


def _metric(eps: float) -> BqskitTMetric:
    k = repr(float(eps))
    if k not in _METRICS:
        _METRICS[k] = BqskitTMetric(float(eps), cache_dir=GS_CACHE)
    return _METRICS[k]


def measure(circ, eps_synth: float | None = None, eps_rz: float | None = None) -> dict:
    """T-count (BQSKit convention), #rotations needing synthesis, #CNOT(+CZ), #qubits. eps_rz defaults to
    eps_synth / N_Rz; the runner passes the INPUT's eps_rz while optimizing (conservative: N_Rz only drops, so
    the synthesis bound N_Rz * eps_rz <= eps_synth still holds) and re-measures the result with the default."""
    if _v2_verify.is_exact(circ):
        m = _v2_metric.measure(circ)
        return dict(t_count=int(m["t_count"]), rotations=0, cx=int(m["cx"]), qubits=int(m["qubits"]),
                    t_depth=int(m["t_depth"]), measurements=int(m["measurements"]), eps_rz=None,
                    eps_synth=eps_synth, path="exact")
    if eps_synth is None or not eps_synth > 0:
        raise ValueError("circuit has rotations that need synthesis: pass eps_synth > 0")
    ops, n = _v2_verify._ops_and_n(circ)
    k = _metric(eps_synth).cost(normalize(ops), eps_rz=eps_rz)
    return dict(t_count=int(k["t"]), t_fixed=int(k["t_fixed"]), t_gs=int(k["t_gs"]), rotations=int(k["rz"]),
                cx=int(k["cx"]), qubits=int(n), measurements=0, eps_rz=k["eps_rz"], eps_synth=float(eps_synth),
                path="bqskit-convention")


def is_ir(c) -> bool:
    return isinstance(c, IRCircuit)
