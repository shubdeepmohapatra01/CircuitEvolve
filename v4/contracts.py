"""Two orthogonal contract tags (V4_README section 6.1), replacing v3's single `contract` field.

    error_class    in {'exact', 'approx'}                 # exact = 0 error; approx = charged to the ledger
    resource_class in {'unitary', 'ancilla', 'measured'}  # no extra qubits | clean ancillas |0>->|0>
                                                          # | ancillas + mid-circuit measurement + feed-forward

v3's single field conflated the two, which mislabelled unitary DPF results (K* = 3, 0 ancillas) as relaxed.
`from_legacy` / `to_legacy` translate so the six v3 rules load unchanged:

    exact   -> ('exact',  'unitary')
    approx  -> ('approx', 'unitary')
    relaxed -> ('exact',  'measured')

Figures hatch on `resource_class != 'unitary'`; the ledger charges only `error_class == 'approx'`.
"""
from __future__ import annotations

ERROR_CLASSES = ("exact", "approx")
RESOURCE_CLASSES = ("unitary", "ancilla", "measured")

_FROM_LEGACY = {"exact": ("exact", "unitary"), "approx": ("approx", "unitary"),
                "relaxed": ("exact", "measured")}


def from_legacy(contract: str) -> tuple[str, str]:
    if contract not in _FROM_LEGACY:
        raise ValueError(f"unknown legacy contract {contract!r}")
    return _FROM_LEGACY[contract]


def to_legacy(error_class: str, resource_class: str) -> str:
    """The v3 contract word that best describes the pair (for reports and for v3 tooling)."""
    check(error_class, resource_class)
    if resource_class != "unitary":
        return "relaxed"
    return "approx" if error_class == "approx" else "exact"


def check(error_class: str, resource_class: str) -> None:
    if error_class not in ERROR_CLASSES:
        raise ValueError(f"error_class must be one of {ERROR_CLASSES}, got {error_class!r}")
    if resource_class not in RESOURCE_CLASSES:
        raise ValueError(f"resource_class must be one of {RESOURCE_CLASSES}, got {resource_class!r}")


def unitary_preserving(resource_class: str) -> bool:
    return resource_class == "unitary"


def hatched(resource_class: str) -> bool:
    """Figures hatch anything that is not a plain unitary result."""
    return resource_class != "unitary"
