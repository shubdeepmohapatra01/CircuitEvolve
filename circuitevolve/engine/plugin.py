"""Domain plugin contract for the generic engine loop (PLAN_P1 §3).

A domain supplies the four components (select / mutate / verify / measure) plus the glue the
loop needs to stay domain-blind. The ENGINE owns acceptance semantics, the error-ledger
protocol, the archive, playbook credit, logging and integrity checks (CLAUDE.md invariants
3-5, 7); a plugin can only shape proposals and measurements, never acceptance.

Tasks are opaque to the engine except for four attributes:
    key    - content hash; marks the task as tried on its member (round-robin)
    order  - in-batch evaluation order (descending), so earlier applications never shift
             a task still to be evaluated (DV: window start position)
    index  - stable id recorded in ledger charges
    log    - small dict for the `propose` log record (via record_fields)

verify() MUST route through FROZEN machinery only (invariant 4); the engine checks the
plugin's frozen_digest() at run start and end.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Member:
    """Archive member: an optimization state with its own error ledger."""
    state: Any
    ledger: Any
    cost: dict
    digest: str
    born: int = 0
    tried: set = field(default_factory=set)
    cache: dict = field(default_factory=dict)


class DomainPlugin(ABC):
    """One optimization domain/family behind the engine loop. See module docstring."""

    name: str = "domain"
    actions: tuple[str, ...] = ("window",)   # candidate kinds parse() may emit
    primary: str = "t"                        # cost key the loop reports as t_before/t_after
    n: int = 0                                # problem size (qubits); 0 if not applicable
    meta: dict = {}                           # input metadata for the start record / summary

    # ------------------------------------------------------------------ state
    @abstractmethod
    def start_state(self) -> Any:
        """The (pre-optimized) input state the loop starts from."""

    @abstractmethod
    def flat_state(self, member: Member) -> Any:
        """The member's state in the representation apply() splices into (may cache on member)."""

    @abstractmethod
    def digest(self, state) -> str:
        """Short content digest for archive dedup."""

    # ------------------------------------------------------------------ select
    @abstractmethod
    def select_tasks(self, member: Member, k: int, rng) -> list:
        """Up to k untried tasks on this member, highest headroom first; clear member.tried
        and start over when everything was tried (round-robin)."""

    # ------------------------------------------------------------------ mutate
    @abstractmethod
    def build_prompt(self, task, rules: list[str], feedback: list[str], allowance: float) -> str:
        """One literal prompt for one task."""

    @abstractmethod
    def parse(self, text: str) -> tuple[list, list, bool]:
        """-> (proposals [(action, payload)], parse_errors, declined). Regex/JSON only —
        never exec/eval (tested with eval/exec monkeypatched to raise)."""

    @abstractmethod
    def materialize(self, task, action: str, payload, call_id: int) -> dict:
        """Turn a parsed proposal into a candidate. Returns
        dict(ok, cand, crec, label[, fail_stat, fail_reason]) — crec is the log record seed;
        on ok=False, fail_stat names the stats counter to bump (e.g. 'refit_failed')."""

    # ------------------------------------------------------------------ verify (FROZEN)
    @abstractmethod
    def verify(self, task, cand, allowance: float) -> dict:
        """-> dict(ok, mode, dist, charge, reason) via frozen machinery only."""

    @abstractmethod
    def global_check(self, state, bound: float) -> dict | None:
        """Whole-problem check against the ORIGINAL on every accept; None if not applicable."""

    def input_check(self, pool: float) -> float:
        """Distance of the pre-optimized input to the original (charged to the ledger);
        raise ValueError if the input is not equivalent. Default: 0.0 (no check)."""
        return 0.0

    @abstractmethod
    def frozen_digest(self) -> str: ...

    def check_unchanged(self, digest_at_start: str) -> None:
        """Raise if the frozen machinery changed during the run (invariant 4)."""
        if self.frozen_digest() != digest_at_start:
            raise RuntimeError("frozen verifier files changed during the run; results are invalid")

    # ------------------------------------------------------------------ apply / measure
    @abstractmethod
    def apply(self, cur_state, task, cand) -> Any:
        """Substitute the candidate into the current state (pure)."""

    @abstractmethod
    def cost(self, state, ledger) -> dict: ...

    @abstractmethod
    def cost_key(self, cost: dict) -> tuple:
        """Total order for archive ranking (ties broken by ledger spend in the engine)."""

    @abstractmethod
    def improves(self, new: dict, old: dict) -> bool:
        """Strict improvement; must never allow the primary component to worsen."""

    def cost_subset(self, cost: dict) -> dict:
        """The cost fields worth logging (default: everything)."""
        return dict(cost)

    def cand_text(self, cand) -> str:
        """Literal rendering of a candidate for failure feedback."""
        return repr(cand)

    def reject_metric_text(self, old: dict, new: dict) -> str:
        return (f"rejected: no improvement ({self.primary} "
                f"{old[self.primary]} -> {new[self.primary]})")

    # ------------------------------------------------------------------ reporting hooks
    def record_fields(self, task) -> dict:
        """Extra fields for the `propose` log record (e.g. window=..., eps_rz=...)."""
        return {}

    def accept_record(self, old: dict, new: dict) -> dict:
        return {f"{self.primary}_before": old[self.primary], f"{self.primary}_after": new[self.primary]}

    def accept_feedback(self, label, verdict, old, new) -> str:
        return (f"ACCEPTED {label or 'rewrite'} ({verdict['mode']}, distance {verdict['dist']:.2e}): "
                f"{self.primary} {old[self.primary]} -> {new[self.primary]}")

    def improvement_entry(self, task, cand, label, old, new) -> tuple:
        return (old[self.primary], new[self.primary], "", label or "")

    def accept_anatomy(self, task, cand, label, verdict, old, new, rules_shown):
        """Structured record of WHAT an accept did, for the reflector (P2.1). Override with
        domain detail (Pauli frames of merged rotations, term kinds, ...); the default carries
        the metric-level facts only."""
        from .reflector import AcceptAnatomy
        return AcceptAnatomy(call=0, family=self.name, action="", rules_shown=list(rules_shown),
                             mode=verdict["mode"], distance=float(verdict["dist"]),
                             charge=float(verdict["charge"]),
                             primary_before=old[self.primary], primary_after=new[self.primary])

    def stats_template(self) -> dict:
        """Domain counters merged into the engine's base stats (per-action counters
        are added by the engine from self.actions)."""
        return {}

    def on_accept_stats(self, stats: dict, action: str, old: dict, new: dict) -> None:
        """Bump domain counters on accept (e.g. rotations_removed_<action>)."""

    def ledger_summary(self, ledger, cost: dict) -> dict:
        return ledger.summary(0)

    def archive_entry(self, member: Member) -> dict:
        return {self.primary: member.cost[self.primary], "spent": member.ledger.spent,
                "digest": member.digest}

    def reclaimed(self, member: Member):
        """Reported metric with unspent budget returned (None if not applicable)."""
        return None

    def final_check(self, member: Member) -> dict | None:
        """Summary-time check of the best state vs the original (None if not applicable)."""
        return None

    def output_files(self, member: Member) -> dict:
        """suffix -> text content, written next to the run log (e.g. {'_best.qasm': ...})."""
        return {}
