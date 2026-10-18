"""Stage-1 window loop — now a thin shim over the generic engine (PLAN_P1 phase P1.2).

Behavior, log formats, stats keys and ledger arithmetic are unchanged (gates:
tests/engine/test_golden_dv.py golden equivalence; tests/test_core_*.py unchanged). The control
flow lives in circuitevolve/engine/loop.py; the DV specifics live in
circuitevolve/domains/dv_windows/plugin.py. This module keeps the historical public surface:
WindowLoop (same constructor), run(), TASK_TEXT, RUNS, and module-level verify_window /
check_circuit (late-bound into the plugin so tests can monkeypatch them here, as before).
"""
from __future__ import annotations

from pathlib import Path

from ..blocks import REPO
from ..domains.dv_windows.plugin import DvWindowsPlugin, _digest, _fmt_target, _wkey  # noqa: F401
from ..engine.loop import EvolveLoop
from ..engine.plugin import Member  # noqa: F401
from ..search.playbook import Playbook
from .circuit import Circuit
from .ledger import Ledger
from .metric import BqskitTMetric
from .verifier import check_circuit, verify_window  # module-level: monkeypatch surface

RUNS = REPO / "results" / "window_runs"
TASK_TEXT = ("The proposer rewrites windows (<= 4 qubits, <= 40 gates) of a Clifford+Rz circuit to lower its "
             "T-count under gridsynth synthesis at eps_rz = eps_synth / N_Rz; an exact (Clifford+T) or "
             "operator-norm verifier with an error allowance decides acceptance. Gates: h s sdg x z t tdg cx cz "
             "rz(angle) on local qubits q0..q3.")


def _late_verify(*a, **k):
    return verify_window(*a, **k)       # resolves THIS module's global at call time (monkeypatchable)


def _late_check(*a, **k):
    return check_circuit(*a, **k)


class WindowLoop(EvolveLoop):
    def __init__(self, circ: Circuit, original_ops, eps: float, complete, *, reflect_complete=None,
                 playbook: Playbook | None = None, tag: str | None = None, n_calls: int = 20, batch: int = 4,
                 reflect_every: int = 8, archive_size: int = 4, p_best: float = 0.7, seed: int = 0,
                 feedback_len: int = 6, runs_dir: Path | None = None, check_whole: bool = True,
                 window_fraction: float = 0.5, per_rewrite_fraction: float = 0.25, max_tokens_note: str = "",
                 ledger_rule: str = "v1", pool_fraction: float = 0.25, refit_multistarts: int = 8,
                 seeded_ties: bool = False):
        self.circ, self.n, self.original = circ, circ.n, original_ops
        # acceptance and reported T use eps_rz = ledger.eps_synth / N_Rz of the circuit's OWN ledger (v1: unspent
        # window budget returns to synthesis; v0: fixed eps/2)
        self.metric = BqskitTMetric(eps)
        plugin = DvWindowsPlugin(circ, original_ops, self.metric, check_whole=check_whole,
                                 refit_multistarts=refit_multistarts, seeded_ties=seeded_ties, seed=seed,
                                 verify_fn=_late_verify, check_fn=_late_check)
        ledger0 = Ledger(eps, rule=ledger_rule, window_fraction=window_fraction, pool_fraction=pool_fraction,
                         per_rewrite_fraction=per_rewrite_fraction)
        super().__init__(plugin, eps, complete, ledger0, reflect_complete=reflect_complete, playbook=playbook,
                         tag=tag, n_calls=n_calls, batch=batch, reflect_every=reflect_every,
                         archive_size=archive_size, p_best=p_best, seed=seed, feedback_len=feedback_len,
                         runs_dir=Path(runs_dir) if runs_dir else RUNS, task_text=TASK_TEXT)
        self.check_whole, self.seeded_ties, self.seed = check_whole, seeded_ties, seed

    # historical surface used by the ablation harness (tests/test_core_ablation.py)
    def _choose_windows(self, m: Member, k: int) -> list:
        return self.plugin.choose_windows(m, k)


def run(name: str, eps: float, complete, tag: str | None = None, playbook_path=None, **kw) -> dict:
    """Convenience entry: load the stage-1 input and original, run the loop, persist the playbook."""
    from .circuit import load_input, original_ops
    circ = load_input(name)
    orig, n = original_ops(name)
    assert n == circ.n
    pb = None
    if playbook_path is not None:
        p = Path(playbook_path)
        pb = Playbook.load(p) if p.exists() else Playbook(evidence="improvement")
    loop = WindowLoop(circ, orig, eps, complete, playbook=pb, tag=tag, **kw)
    out = loop.run()
    if pb is not None and not pb.frozen:
        pb.save(playbook_path)
    return out
