"""What rules may import: the Rule contract, plus v3.api.dv (Clifford+Rz ops), v3.api.pauli
(Pauli frames / commutation), v3.api.cvdv (CV-DV JSON circuits). Small-unitary sim, refit and phase-polynomial
helpers are added when the agent needs them (P2).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

DOMAINS = ("dv", "cvdv")
KINDS = ("rewrite", "procedure", "reconstruction", "resource")
CONTRACTS = ("exact", "approx", "relaxed")


@dataclass(frozen=True)
class Rule:
    name: str
    domain: str
    kind: str
    contract: str
    source: str
    idea: str
    trigger: Callable[[Any], list]          # (circuit) -> list[Match], pure and deterministic
    apply: Callable[[Any, Any], Any]        # (circuit, match) -> circuit, pure and deterministic

    def __post_init__(self):
        if self.domain not in DOMAINS or self.kind not in KINDS or self.contract not in CONTRACTS:
            raise ValueError(f"bad Rule fields: domain={self.domain!r} kind={self.kind!r} contract={self.contract!r}")
        if not (self.name.isidentifier() and callable(self.trigger) and callable(self.apply)):
            raise ValueError("Rule needs an identifier name and callable trigger / apply")
