"""What a rule may import, and the Rule contract (V4_README sections 2 and 9).

A rule is one Python file exporting `RULE = Rule(...)`:

    Rule(name, domain, kind, source, idea, trigger, apply,
         error_class='exact'|'approx', resource_class='unitary'|'ancilla'|'measured',
         precondition=Precondition(...), certificate='auto'|...)

`contract=` (v3's single word) is still accepted and translated, so the six v3 rules load unchanged.

What is new in v4:

* **two contract tags** instead of one (`v4.contracts`): error and resources are independent, so an
  angle-snapping rule is ('approx', 'unitary') and Gidney's temporary AND is ('exact', 'measured');
* **a declared `precondition`**, checked against a cheap circuit descriptor BEFORE the trigger runs. A
  precondition that excludes a circuit is not a rejection and costs no compute (V4_README 5.3);
* **modules a rule may import**: stdlib, numpy, scipy, sympy and `v4.api.*` - never pyzx, pytket, bqskit,
  qiskit or `circuitevolve`. `v4.api` carries the machinery (`phasepoly`, `pauli`, `blocks`, `sim`, `refit`,
  `angles`, `budget`, `fermion`) so the implementer does not re-derive it per rule.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable

from ..contracts import check as _check_tags, from_legacy, to_legacy

DOMAINS = ("dv", "cvdv")
KINDS = ("rewrite", "procedure", "reconstruction", "resource")
CONTRACTS = ("exact", "approx", "relaxed")
CERTIFICATES = ("auto", "algebraic", "exact_ring", "numeric_block", "branch_kraus")
NEEDS = ("rotations", "nonclifford_rz", "toffoli", "hadamard", "two_qubit", "measurement_free", "ancilla_room")


# ------------------------------------------------------------------------------------------ descriptor
@dataclass(frozen=True)
class Descriptor:
    """Everything a precondition may look at: computed once per circuit, in O(ops), no matrices."""
    family: str                      # 'dv_angle' (Clifford+Rz op list) | 'dv_recon' (Toffoli-level IRCircuit)
    qubits: int
    n_ops: int
    counts: dict                     # gate name -> count
    nonclifford_rz: int              # rz gates off the pi/4 grid (these are what gridsynth pays for)
    rotations: int                   # t, tdg and every rz
    toffoli: int                     # ccx + ccz
    hadamard: int
    two_qubit: int
    measurement_free: bool

    def has(self, need: str) -> bool:
        if need == "measurement_free":
            return self.measurement_free
        if need == "ancilla_room":
            return True              # v4 always allows appended ancillas; the cost shows up in the metric
        return bool(getattr(self, need, 0))


def describe(c) -> Descriptor:
    """Cheap descriptor of a circuit (both families). Pure, O(ops)."""
    from . import dv
    if dv.is_ir_circuit(c):
        counts = Counter(g.name for g in c.gates)
        return Descriptor(family="dv_recon", qubits=c.n_qubits, n_ops=len(c.gates), counts=dict(counts),
                          nonclifford_rz=0, rotations=counts.get("t", 0) + counts.get("tdg", 0),
                          toffoli=counts.get("ccx", 0) + counts.get("ccz", 0), hadamard=counts.get("h", 0),
                          two_qubit=counts.get("cx", 0) + counts.get("cz", 0),
                          measurement_free=not counts.get("measure", 0))
    if dv.is_angle_circuit(c):
        counts = Counter(g for g, _, _ in c.ops)
        off = sum(1 for g, _, a in c.ops if g == "rz" and not dv.on_grid(a))
        return Descriptor(family="dv_angle", qubits=c.n, n_ops=len(c.ops), counts=dict(counts),
                          nonclifford_rz=off, rotations=counts.get("t", 0) + counts.get("tdg", 0) +
                          counts.get("rz", 0), toffoli=0, hadamard=counts.get("h", 0),
                          two_qubit=counts.get("cx", 0) + counts.get("cz", 0), measurement_free=True)
    raise TypeError(f"not a v4 circuit: {type(c).__name__}")


# ------------------------------------------------------------------------------------------ precondition
@dataclass(frozen=True)
class Precondition:
    """A declared, deterministic statement of where the rule can possibly apply.

    `excludes(descriptor)` returns '' (may apply) or a one-line reason. A rule excluded on a circuit is
    skipped for free and is NOT counted as a rejection (V4_README 5.3, row 1).
    """
    families: tuple = ()
    needs: tuple = ()
    forbids: tuple = ()
    min_qubits: int | None = None
    max_qubits: int | None = None
    note: str = ""

    def __post_init__(self):
        for n in tuple(self.needs) + tuple(self.forbids):
            if n not in NEEDS:
                raise ValueError(f"precondition need {n!r} not in {NEEDS}")

    def excludes(self, d: Descriptor) -> str:
        if self.families and d.family not in self.families:
            return f"family {d.family} not in {self.families}"
        if self.min_qubits is not None and d.qubits < self.min_qubits:
            return f"{d.qubits} qubits < min {self.min_qubits}"
        if self.max_qubits is not None and d.qubits > self.max_qubits:
            return f"{d.qubits} qubits > max {self.max_qubits}"
        for n in self.needs:
            if not d.has(n):
                return f"circuit has no {n}"
        for n in self.forbids:
            if d.has(n):
                return f"circuit has {n}, which the rule forbids"
        return ""


ANY = Precondition()


# ------------------------------------------------------------------------------------------ rule
@dataclass(frozen=True)
class Rule:
    name: str
    domain: str
    kind: str
    source: str
    idea: str
    trigger: Callable[[Any], list]          # (circuit) -> list[Match], pure and deterministic
    apply: Callable[[Any, Any], Any]        # (circuit, match) -> circuit, pure and deterministic
    contract: str = ""                      # v3 legacy word; derived from the tags when omitted
    error_class: str = ""
    resource_class: str = ""
    precondition: Precondition = ANY
    certificate: str = "auto"
    tier: str = "accepted"                  # 'floor' (never retired) | 'accepted'
    evidence: dict = field(default_factory=dict)

    def __post_init__(self):
        object.__setattr__(self, "contract", self.contract or "")
        if self.error_class or self.resource_class:
            e = self.error_class or "exact"
            r = self.resource_class or "unitary"
            _check_tags(e, r)
            object.__setattr__(self, "error_class", e)
            object.__setattr__(self, "resource_class", r)
            object.__setattr__(self, "contract", self.contract or to_legacy(e, r))
        elif self.contract:
            e, r = from_legacy(self.contract)
            object.__setattr__(self, "error_class", e)
            object.__setattr__(self, "resource_class", r)
        else:
            raise ValueError("Rule needs error_class/resource_class or a legacy contract=")
        if self.domain not in DOMAINS or self.kind not in KINDS:
            raise ValueError(f"bad Rule fields: domain={self.domain!r} kind={self.kind!r}")
        if self.certificate not in CERTIFICATES:
            raise ValueError(f"certificate must be one of {CERTIFICATES}")
        if self.tier not in ("floor", "accepted"):
            raise ValueError("tier must be 'floor' or 'accepted'")
        if not (self.name.isidentifier() and callable(self.trigger) and callable(self.apply)):
            raise ValueError("Rule needs an identifier name and callable trigger / apply")
        if not isinstance(self.precondition, Precondition):
            raise ValueError("precondition must be a Precondition")

    @property
    def charges_error(self) -> bool:
        return self.error_class == "approx"

    @property
    def unitary_preserving(self) -> bool:
        return self.resource_class == "unitary"

    def excluded_on(self, circuit_or_descriptor) -> str:
        d = circuit_or_descriptor if isinstance(circuit_or_descriptor, Descriptor) \
            else describe(circuit_or_descriptor)
        return self.precondition.excludes(d)

    def tags(self) -> dict:
        return dict(error_class=self.error_class, resource_class=self.resource_class, contract=self.contract,
                    kind=self.kind, tier=self.tier, certificate=self.certificate)


__all__ = ["Rule", "Precondition", "Descriptor", "describe", "ANY", "DOMAINS", "KINDS", "CONTRACTS",
           "CERTIFICATES", "NEEDS"]
