"""DV rotation-dominated family: the stage-1 window core as an engine plugin (PLAN_P1 P1.2).

Wraps core/{circuit,mutator,verifier,metric,refit} unchanged. verify/global-check callables are
injected by core/loop.py so they late-bind through that module's namespace (keeps the historical
monkeypatch surface and the frozen-file boundary in one place).
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Callable

from ...blocks.circuit_io import classify_angle
from ...blocks.cost_model import canonical_angle, cost_key, rz_angles
from ...integrity import check_unchanged, frozen_digest
from ...core.circuit import Circuit, splice, window_text, windows
from ...core.metric import BqskitTMetric, improves
from ...core.mutator import DECLINED, WindowTask, build_prompt, extract_proposals
from ...core.refit import refit
from ...engine.plugin import DomainPlugin, Member

COST_KEYS = ("t", "t_fixed", "t_gs", "rz", "cx", "gates", "eps_rz")


def _fmt_target(a: float) -> str:
    m = round(a / (math.pi / 8))
    return "0" if m == 0 else f"{m}*pi/8"


def _digest(ops) -> str:
    return hashlib.sha1(repr(ops).encode()).hexdigest()[:16]


def _wkey(w) -> str:
    return hashlib.sha1((repr(w.qubits) + window_text(w.ops)).encode()).hexdigest()[:12]


@dataclass
class WindowRef:
    """Engine task for one window (key/order/index are the engine-visible attributes)."""
    w: Any
    t_win: float
    t_rot: list
    t_fixed: int
    eps_rz: float
    key: str = field(init=False)

    def __post_init__(self):
        self.key = _wkey(self.w)

    @property
    def order(self):
        return self.w.start

    @property
    def index(self):
        return self.w.index


class DvWindowsPlugin(DomainPlugin):
    name = "dv_windows"
    actions = ("window", "fix")
    primary = "t"

    def __init__(self, circ: Circuit, original_ops, metric: BqskitTMetric, *, check_whole: bool = True,
                 refit_multistarts: int = 8, seeded_ties: bool = False, seed: int = 0,
                 verify_fn: Callable | None = None, check_fn: Callable | None = None):
        self.circ, self.n, self.original = circ, circ.n, original_ops
        self.meta = circ.meta
        self.metric = metric
        self.check_whole = check_whole
        self.refit_multistarts = refit_multistarts
        self.seed, self.seeded_ties = seed, seeded_ties
        self._verify = verify_fn
        self._check = check_fn
        if verify_fn is None or check_fn is None:
            from ...core.verifier import check_circuit as _cc, verify_window as _vw
            self._verify = self._verify or _vw
            self._check = self._check or _cc

    # ------------------------------------------------------------------ state
    def start_state(self):
        return list(self.circ.ops)

    def _windows(self, m: Member):
        if "win" not in m.cache:
            ws, flat = windows(Circuit(self.n, m.state))
            m.cache["win"] = (ws, flat)
        return m.cache["win"]

    def flat_state(self, m: Member):
        _, flat = self._windows(m)
        return list(flat)

    def digest(self, state) -> str:
        return _digest(state)

    # ------------------------------------------------------------------ select
    def _window_cost(self, w, eps_rz: float) -> tuple:
        angs = [canonical_angle(a) for g, _, a in w.ops if g == "rz" and classify_angle(a) is None]
        t_rot = self.metric.rotation_t(angs, eps_rz)
        t_fixed = sum(1 for g, _, _ in w.ops if g in ("t", "tdg")) + \
            sum(classify_angle(a) % 2 for g, _, a in w.ops if g == "rz" and classify_angle(a) is not None)
        return t_rot, t_fixed

    def choose_windows(self, m: Member, k: int) -> list:
        """Stage-1 scored shape: [(t_win, w, t_rot, t_fixed)] (kept for the ablation harness)."""
        ws, _ = self._windows(m)
        e = m.cost["eps_rz"]
        scored = []
        for w in ws:
            t_rot, t_fixed = self._window_cost(w, e)
            if t_fixed + sum(t_rot) > 0:
                scored.append((t_fixed + sum(t_rot), w, t_rot, t_fixed))
        if self.seeded_ties:
            scored.sort(key=lambda s: (-s[0], hashlib.sha1(f"{self.seed}:{_wkey(s[1])}".encode()).hexdigest()))
        else:
            scored.sort(key=lambda s: (-s[0], s[1].index))
        fresh = [s for s in scored if _wkey(s[1]) not in m.tried]
        if not fresh:                       # round-robin: start over on this member
            m.tried.clear()
            fresh = scored
        return fresh[:k]

    def select_tasks(self, m: Member, k: int, rng) -> list:
        e = m.cost["eps_rz"]
        return [WindowRef(w=w, t_win=t_win, t_rot=t_rot, t_fixed=t_fixed, eps_rz=e)
                for t_win, w, t_rot, t_fixed in self.choose_windows(m, k)]

    # ------------------------------------------------------------------ mutate
    def build_prompt(self, task: WindowRef, rules, feedback, allowance) -> str:
        t = WindowTask(local_ops=task.w.ops, k=task.w.k, eps_rz=task.eps_rz, allowance=allowance,
                       t_rot=task.t_rot, t_fixed=task.t_fixed, rules=rules, feedback=feedback)
        return build_prompt(t)

    def parse(self, text: str):
        props, perr = extract_proposals(text)
        declined = perr == [DECLINED]
        if declined:
            perr = []
        return props, perr, declined

    def materialize(self, task: WindowRef, action: str, payload, call_id: int) -> dict:
        if action == "fix":
            fx = {int(i): float(a) for i, a in payload.items()}
            label = "fix " + ", ".join(f"op {i}->{_fmt_target(a)}" for i, a in sorted(fx.items()))
            rf = refit(task.w.ops, task.w.k, fx, multistarts=self.refit_multistarts, seed=call_id)
            crec = dict(action="fix", fixes={str(i): a for i, a in fx.items()},
                        refit={kk: rf[kk] for kk in ("ok", "dist", "n_free", "reason")})
            if not rf["ok"]:
                return dict(ok=False, cand=None, crec=crec, label=label, fail_stat="refit_failed",
                            fail_reason=f"rejected: refit ({rf['reason']})")
            crec["window"] = window_text(rf["ops"])
            return dict(ok=True, cand=rf["ops"], crec=crec, label=label)
        c = payload
        return dict(ok=True, cand=c, crec=dict(action="window", window=window_text(c)), label=None)

    # ------------------------------------------------------------------ verify (FROZEN)
    def verify(self, task: WindowRef, cand, allowance: float) -> dict:
        return self._verify(task.w.ops, cand, task.w.k, allowance)

    def global_check(self, state, bound: float):
        if self.check_whole and self.n <= 20:
            return self._check(self.original, state, self.n, bound=bound)
        return None

    def input_check(self, pool: float) -> float:
        if self.check_whole and self.n <= 20:
            r = self._check(self.original, self.circ.ops, self.n, bound=pool)
            if not r["ok"]:
                raise ValueError(f"input circuit is not equivalent to the original: {r}")
            return float(r["dist"])
        return 0.0

    def frozen_digest(self) -> str:
        return frozen_digest()

    def check_unchanged(self, digest_at_start: str) -> None:
        check_unchanged(digest_at_start)

    # ------------------------------------------------------------------ apply / measure
    def apply(self, cur_state, task: WindowRef, cand):
        return splice(cur_state, task.w, cand)

    def cost(self, state, ledger) -> dict:
        n_rz = len(rz_angles(state))
        c = self.metric.cost(state, eps_rz=ledger.eps_synth / n_rz if n_rz else ledger.eps_synth)
        c["eps_synth"] = ledger.eps_synth
        return c

    def cost_key(self, cost: dict) -> tuple:
        return cost_key(cost)

    def improves(self, new: dict, old: dict) -> bool:
        return improves(new, old)

    def cost_subset(self, cost: dict) -> dict:
        return {kk: cost[kk] for kk in COST_KEYS}

    def cand_text(self, cand) -> str:
        return window_text(cand)

    # ------------------------------------------------------------------ reporting
    def record_fields(self, task: WindowRef) -> dict:
        return dict(window=dict(index=task.w.index, qubits=list(task.w.qubits), n_ops=len(task.w.ops),
                                t_cost=task.t_win),
                    eps_rz=task.eps_rz)

    def reject_metric_text(self, old: dict, new: dict) -> str:
        return f"rejected: no improvement (T {old['t']} -> {new['t']}, rz {old['rz']} -> {new['rz']})"

    def accept_record(self, old: dict, new: dict) -> dict:
        return dict(t_before=old["t"], t_after=new["t"], rz_before=old["rz"], rz_after=new["rz"])

    def accept_feedback(self, label, v, old, new) -> str:
        return (f"ACCEPTED {label or 'window rewrite'} ({v['mode']}, distance {v['dist']:.2e}): "
                f"T {old['t']} -> {new['t']}, rotations {old['rz']} -> {new['rz']}")

    def improvement_entry(self, task: WindowRef, cand, label, old, new) -> tuple:
        return (old["t"], new["t"], window_text(task.w.ops),
                (label + "\n" if label else "") + window_text(cand))

    def stats_template(self) -> dict:
        return dict(refit_failed=0, rotations_removed_window=0, rotations_removed_fix=0)

    def on_accept_stats(self, stats: dict, action: str, old: dict, new: dict) -> None:
        stats[f"rotations_removed_{action}"] += old["rz"] - new["rz"]

    def ledger_summary(self, ledger, cost: dict) -> dict:
        return ledger.summary(cost["rz"])

    def archive_entry(self, m: Member) -> dict:
        return dict(t=m.cost["t"], rz=m.cost["rz"], spent=m.ledger.spent, digest=m.digest)

    def reclaimed(self, m: Member):
        n_rz = m.cost["rz"]
        if n_rz:
            return BqskitTMetric(m.ledger.reclaimed_eps_synth).cost(m.state)["t"]
        return None

    def final_check(self, m: Member):
        if self.check_whole and self.n <= 20:
            final = self._check(self.original, m.state, self.n,
                                bound=m.ledger.d_input + m.ledger.spent, seed=12345)
            return {kk: final.get(kk) for kk in ("ok", "verified", "method", "dist", "bound")}
        return None

    def output_files(self, m: Member) -> dict:
        return {"_best.qasm": Circuit(self.n, m.state).to_qasm()}
