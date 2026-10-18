"""The user-facing entry point (PLAN_P1 P1.4): optimize(source, eps, complete) — no domain named.

source: a stage-1 benchmark name ("qft_8"), a QASM path/text, or a Hamiltonian term input.
The tier-0 router picks the family binding; the binding picks the plugin, contract and playbook.
Zero accepted rewrites reproduce the input's baseline exactly (B0 for the DV window family —
gate: tests/engine/test_optimize_b0.py).
"""
from __future__ import annotations

import re
from pathlib import Path

from .router import FamilyBinding, route

_STAGE1_NAME = re.compile(r"^[A-Za-z0-9_]+$")


def optimize(source, eps: float, complete, *, manifest: dict | None = None, tag: str | None = None,
             playbook_path=None, runs_dir=None, **kw) -> dict:
    """Route, bind, run. Returns the run summary with a `routing` section added."""
    routed_source = source
    if isinstance(source, str) and _STAGE1_NAME.match(source) and not str(source).endswith(".qasm"):
        from ..core.circuit import load_input
        routed_source = list(load_input(source).ops)       # route on the actual TKET-pre-optimized ops
    binding = route(routed_source, manifest)
    if binding.plugin == "dv_windows":
        summ = _run_dv_windows(source, eps, complete, binding, tag=tag, playbook_path=playbook_path,
                               runs_dir=runs_dir, **kw)
    elif binding.plugin == "cvdv":
        summ = _run_cvdv(source, eps, complete, binding, tag=tag, **kw)
    else:  # pragma: no cover - the router only returns known plugins
        raise RuntimeError(f"router returned unknown plugin {binding.plugin!r}")
    summ["routing"] = dict(family=binding.family, contract=binding.contract, reason=binding.reason,
                           playbook=binding.playbook)
    return summ


def _run_dv_windows(source, eps, complete, binding: FamilyBinding, *, tag, playbook_path, runs_dir, **kw):
    from ..core.circuit import Circuit, load_input, original_ops
    from ..core.loop import RUNS, WindowLoop
    from ..search.playbook import Playbook
    if isinstance(source, str) and _STAGE1_NAME.match(source):
        circ = load_input(source)
        orig, n = original_ops(source)
        assert n == circ.n
    else:                                                   # standalone QASM: the input is its own original
        s = str(source)
        text = s if s.lstrip().startswith("OPENQASM") else Path(s).read_text()
        name = Path(s).stem if s.endswith(".qasm") else "qasm"
        circ = Circuit.from_qasm(text, name=name, source="qasm_input")
        orig = list(circ.ops)
    pb = None
    if playbook_path is not None:
        p = Path(playbook_path)
        pb = Playbook.load(p) if p.exists() else Playbook(evidence="improvement")
    loop = WindowLoop(circ, orig, eps, complete, playbook=pb, tag=tag,
                      runs_dir=Path(runs_dir) if runs_dir else RUNS, **kw)
    out = loop.run()
    if pb is not None and not pb.frozen and playbook_path is not None:
        pb.save(playbook_path)
    return out


def _run_cvdv(source, eps, complete, binding: FamilyBinding, *, tag, runs_dir=None, n_max: int = 3,
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
