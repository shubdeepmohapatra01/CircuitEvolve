"""The user-facing entry point (PLAN_P3 P3.2): optimize(source, eps, complete) — no domain named.

source: a stage-1 benchmark name ("qft_8"), a QASM path/text, or a Hamiltonian term input.
The tier-0 router returns the method CASCADE (ordered MethodBindings); optimize() executes the
stages in order, threading each stage's verified output into the next, and emits per-stage
sections in the summary. Single-stage cascades keep the pre-/1 summary shape bit-exact
(gates: tests/engine/test_optimize_b0.py, test_p2_dryrun.py, golden fixture). An empty cascade
(pure-Clifford input) returns the input unchanged with an explanatory summary — not an error.
Contracts never mix (PLAN_P3 §1.5): each stage record names its contract; the angle stage
after reconstruction is unitary-preserving RELATIVE to the reconstructed circuit.
"""
from __future__ import annotations

import re
from pathlib import Path

from .router import MethodBinding, features_of, route

_STAGE1_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def _named_t(ops) -> int:
    """Named-T count of an op list (t/tdg gates; routing-level attribution metric only)."""
    return sum(1 for g, _, _ in ops if g in ("t", "tdg"))


def _stage_record(b: MethodBinding, summ: dict) -> dict:
    return dict(method=b.method, family=b.family, contract=b.contract, status=b.status,
                t_before=summ.get("t_before"), t_after=summ.get("t_after"),
                verified=bool((summ.get("final_check_vs_original") or {}).get("ok")),
                reason=b.reason)


def optimize(source, eps: float, complete, *, manifest: dict | None = None, tag: str | None = None,
             playbook_path=None, runs_dir=None, tket: str = "auto", **kw) -> dict:
    """Route, cascade, run. Returns the LAST stage's summary (pre-/1 shape preserved for
    single-stage runs) with `routing` (incl. the cascade) and `stages` sections added."""
    routed_source = source
    is_stage1 = bool(isinstance(source, str) and _STAGE1_NAME.match(source)
                     and not str(source).endswith(".qasm"))
    if is_stage1:
        from ..core.circuit import load_input
        routed_source = list(load_input(source).ops)       # route on the actual TKET-pre-optimized ops
    bindings = route(routed_source, manifest)
    if not bindings:
        feats = features_of(routed_source)
        return dict(status="unchanged", t_before=0, t_after=0, features=feats, stages=[],
                    reason="no method applicable: no non-Clifford content — pure-Clifford "
                           "input returned unchanged (T-count already 0)",
                    routing=dict(family=None, contract=None, playbook=None, cascade=[],
                                 reason="pure-Clifford input: no method predicate fires"))
    stages, current, summ = [], source, None
    for i, b in enumerate(bindings):
        if b.plugin == "dv_windows":
            summ = _run_dv_windows(current, eps, complete, b, tag=tag, playbook_path=playbook_path,
                                   runs_dir=runs_dir, tket=("off" if is_stage1 else tket),
                                   staged=(i > 0), **kw)
        elif b.plugin == "cvdv":
            summ = _run_cvdv(current, eps, complete, b, tag=tag, **kw)
        elif b.plugin == "reconstruction":
            summ = _run_reconstruction(current, eps, complete, b, tag=tag,
                                       playbook_path=playbook_path, runs_dir=runs_dir,
                                       manifest=manifest, **kw)
        elif b.plugin is None:
            raise NotImplementedError(
                f"method '{b.method}' routed (status {b.status!r}) but its plugin is not "
                "available yet — the reconstruction plugin lands in PLAN_P3 P3.3")
        else:  # pragma: no cover - the router only returns known plugins
            raise RuntimeError(f"router returned unknown plugin {b.plugin!r}")
        stages.append(_stage_record(b, summ))
        current = summ.pop("_out_payload", current)   # threading seam: verified stage output
    last = bindings[-1]
    summ["routing"] = dict(family=last.family, contract=last.contract, reason=last.reason,
                           playbook=last.playbook,
                           cascade=[dict(method=b.method, family=b.family, rank=b.rank,
                                         status=b.status, reason=b.reason) for b in bindings])
    summ["stages"] = stages
    return summ


def _run_dv_windows(source, eps, complete, binding: MethodBinding, *, tag, playbook_path, runs_dir,
                    graduated: str = "on", tket: str = "auto", staged: bool = False, **kw):
    from ..core.circuit import Circuit, load_input, original_ops
    from ..core.loop import RUNS, WindowLoop
    from ..search.playbook import Playbook
    tket_entry_rec, staged_rec = None, None
    # a zero-accept earlier stage threads the ORIGINAL source onward: a str source is handled
    # by the raw-qasm branch below even when staged=True (tket auto fires on its Toffolis)
    if isinstance(source, dict):                            # verified output of a previous stage
        payload = source
        if not ("ops" in payload and "n" in payload):
            raise NotImplementedError(
                "angle stage after a cascade stage expects an {'ops', 'n', 'name'} payload "
                "(reconstruction's cascade_payload); got a different staged input")
        ops, n = list(payload["ops"]), payload["n"]
        name = payload.get("name", "staged")
        staged_rec = dict(segments=payload.get("segments"), segment=payload.get("segment"),
                          segment_t=payload.get("segment_t"), fixed_t=payload.get("fixed_t", 0),
                          total_t_before=payload.get("total_t_before",
                                                     payload.get("fixed_t", 0) + _named_t(ops)))
        if tket == "auto":                                  # entry pass: staged input is never pre-TKET'd
            from .tketpass import tket_entry
            before = _named_t(ops)
            ops = tket_entry(ops, n)
            tket_entry_rec = dict(fired=True, why="staged input", t_before=before, t_after=_named_t(ops))
        circ = Circuit(n, ops, dict(name=name, source="cascade_stage"))
        # §1.5: the angle stage is unitary-preserving RELATIVE to the reconstructed circuit
        orig = list(circ.ops)
    elif isinstance(source, str) and _STAGE1_NAME.match(source):
        circ = load_input(source)
        orig, n = original_ops(source)
        assert n == circ.n
    else:                                                   # standalone QASM: the input is its own original
        s = str(source)
        text = s if s.lstrip().startswith("OPENQASM") else Path(s).read_text()
        name = Path(s).stem if s.endswith(".qasm") else "qasm"
        feats = binding.features or {}
        has_tof = bool(feats.get("toffolis"))
        if tket == "auto" and has_tof:                      # window core takes CORE_GATES only:
            from .tketpass import read_qasm_ops, tket_entry  # decompose Toffolis at the angle door
            n, ops0 = read_qasm_ops(text)
            before = _named_t(ops0) + 7 * sum(1 for g, _, _ in ops0 if g in ("ccx", "ccz"))
            ops = tket_entry(ops0, n)
            tket_entry_rec = dict(fired=True, why="input contains Toffolis", t_before=before,
                                  t_after=_named_t(ops))
            circ = Circuit(n, ops, dict(name=name, source="qasm_input+tket_entry"))
        else:                                               # today's path, bit-exact (no entry pass)
            circ = Circuit.from_qasm(text, name=name, source="qasm_input")
        orig = list(circ.ops)
    pre_opt = None
    if graduated == "on":
        from .graduate import apply_graduated, load_graduated
        rules = load_graduated(binding.graduated_family)   # §2: frozen index key 'dv.windows'
        if rules:
            rz0 = sum(1 for g, _, _ in circ.ops if g == "rz")
            ops2, reports = apply_graduated(list(circ.ops), rules, n=circ.n)
            pre_opt = dict(rules=[r.id for r in rules], reports=reports, rz_before=rz0,
                           rz_after=sum(1 for g, _, _ in ops2 if g == "rz"))
            circ = Circuit(circ.n, ops2, dict(circ.meta, graduated=[r.id for r in rules]))
            # the loop's standard input check measures the (original -> pre-opted) distance and
            # charges it to the ledger, so the pass spends no budget machinery of its own
    pb = None
    if playbook_path is not None:
        p = Path(playbook_path)
        pb = Playbook.load(p) if p.exists() else Playbook(evidence="improvement")
    loop = WindowLoop(circ, orig, eps, complete, playbook=pb, tag=tag,
                      runs_dir=Path(runs_dir) if runs_dir else RUNS, **kw)
    out = loop.run()
    if staged_rec is not None:                     # whole-stage attribution: loop numbers are the
        out["segment_loop"] = dict(t_before=out["t_before"], t_after=out["t_after"])
        out["staged"] = dict(staged_rec)           # optimized segment's; totals add the fixed T
        out["t_before"] = staged_rec["total_t_before"]
        out["t_after"] = staged_rec["fixed_t"] + out["segment_loop"]["t_after"]
    if tket_entry_rec is not None:                 # deterministic entry-pass gains: own section
        out["tket_entry"] = tket_entry_rec
    out["pre_opt"] = pre_opt                       # deterministic pass gains: SEPARATE column,
    if pb is not None and not pb.frozen and playbook_path is not None:   # never sold as LLM gains
        pb.save(playbook_path)
    return out


def _run_reconstruction(source, eps, complete, binding: MethodBinding, *, tag, playbook_path=None,
                        runs_dir=None, manifest=None, graduated: str = "on", **kw):
    """Reconstruction stage (PLAN_P3 P3.3): v2/tier1 plugin through the generic loop.
    RELAXED column; declared-zero qubits come from the caller's manifest
    ({'declared_zero': [...]}, the benchmark contract) — never guessed. `graduated` is
    accepted for cascade-kwarg compatibility; no graduated rules exist for this family yet."""
    from ..blocks import REPO
    from ..core.ledger import Ledger
    from ..domains.reconstruction import ReconstructionPlugin
    from ..search.playbook import Playbook
    from ..v2.tier1.recognize import load_logical, summarize
    from .loop import EvolveLoop
    s_in = str(source)
    text = s_in if s_in.lstrip().startswith("OPENQASM") else Path(s_in).read_text()
    name = Path(s_in).stem if s_in.endswith(".qasm") else "qasm"
    dz = list((manifest or {}).get("declared_zero", []))
    _, lc = load_logical(text, name=name)
    summary = summarize(lc, declared_zero=dz, name=name)
    plugin = ReconstructionPlugin(lc, summary)
    pb = None
    if playbook_path is not None:
        p = Path(playbook_path)
        pb = Playbook.load(p) if p.exists() else Playbook(evidence="improvement")
    loop = EvolveLoop(plugin, eps, complete, Ledger(eps), playbook=pb, tag=tag,
                      runs_dir=Path(runs_dir) if runs_dir else REPO / "results" / "engine" / "recon_runs",
                      **kw)
    out = loop.run()
    out["contract"] = "relaxed"                        # §1.5: relaxed column, never mixed
    best = loop.archive[0]
    payload = plugin.cascade_payload(best)
    if payload is not None:
        out["_out_payload"] = payload
    if pb is not None and not pb.frozen and playbook_path is not None:
        pb.save(playbook_path)
    return out


def _run_cvdv(source, eps, complete, binding: MethodBinding, *, tag, runs_dir=None, n_max: int = 3,
              r_max: int = 4096, isa=None, rules_path=None, **kw):
    try:
        from ..domains.cvdv import benchmark_plugin
    except ImportError as e:
        raise NotImplementedError(
            "cvdv family binding: the cvdv plugin (PLAN_P1 P1.3) is not importable in this "
            f"environment ({e}); run in an environment with the cvdv stack deps") from e
    from ..blocks import REPO
    from ..core.ledger import Ledger
    if isinstance(source, dict) and "benchmark" in source:
        plugin = benchmark_plugin(source["benchmark"], eps_total=eps, n_max=n_max, r_max=r_max,
                                  isa=isa, rules_path=rules_path)
    else:
        raise NotImplementedError(
            "cvdv family binding v0 takes {'benchmark': '<genesis benchmark name>'}; raw term "
            "lists need the cvdv Term constructors and land with the first unified campaign")
    from .loop import EvolveLoop
    loop = EvolveLoop(plugin, eps, complete, Ledger(eps), tag=tag,
                      runs_dir=Path(runs_dir) if runs_dir else REPO / "results" / "engine" / "cvdv_runs", **kw)
    return loop.run()
