"""Baselines for v4 - V4_README section 3. The DPF column is REPLACED.

v3's `baselines.csv` stays frozen and is read unchanged for TKET, pyzx and BQSKit-FT. Its B3/B3g (k=3)
DPF arm is retired and replaced by **B4 = DPF Synth** (`b4_baseline.csv`, built this session from
`bqskit-ft` branch `greedy_ntro` @ c04a32245d88a0877277dccbcb8001cd85a7eef0, best over K in 3..10,
extended to 14 for qae_13, best of 5 seeds).

B4 is the lowest T on 4 of the 5 angle circuits. The caveats travel with it in every row:

* it is **stochastic** - the seed spread is reported per row (`t_min` / `t_max`), 2 T at K=3 and 104 T at
  K=8 on qft_8, so any "we beat DPF" claim must quote the range;
* K* comes from OUR sweep, not the paper's decision matrix;
* at K >= 4 it is a **measurement-based** result: the temporary-AND uncompute leaks ancilla population
  (1/sqrt(2) at k=4, ~1.0 at k=5, measured), so those rows are `resource_class='measured'`. The rows with
  0 ancillas are `'unitary'` - v3's single `contract` field conflated the two and hatched unitary DPF
  results as relaxed (V4_README 6.1).

    baselines(label, eps)       -> {method: row}
    best_baseline(label, eps)   -> the lowest-T row ("the target the floor must reach")
    PRIMARY_EPS = 1e-3          every v4 comparison. 1e-5 is a secondary sweep; never compare across eps.
"""
from __future__ import annotations

import csv
from functools import lru_cache

from .contracts import check as _check_tags
from .paths import B4_CSV, BASELINES_CSV

PRIMARY_EPS = 1e-3
RETIRED = ("BQSKit-DPF",)                 # the old B3/B3g arm: superseded by B4, never reported again


@lru_cache(maxsize=None)
def _v3_rows() -> tuple:
    with open(BASELINES_CSV) as f:
        return tuple(dict(r) for r in csv.DictReader(f))


@lru_cache(maxsize=None)
def _b4_rows() -> tuple:
    with open(B4_CSV) as f:
        return tuple(dict(r) for r in csv.DictReader(f))


def _tags_of_b4(row: dict) -> tuple:
    """DPF Synth snaps angles, so the error is always approx; the resources depend on the ancillas it
    actually used, not on the k it was run at."""
    anc = int(row["ancillas"])
    res = "unitary" if anc == 0 else "measured"
    _check_tags("approx", res)
    return "approx", res


def baselines(label: str, eps: float = PRIMARY_EPS) -> dict:
    """{method: {t_count, qubits, error_class, resource_class, ...}} for one circuit at one eps."""
    out = {}
    for r in _v3_rows():
        if r["label"] != label or r["method"] in RETIRED:
            continue
        if not r["eps"] or float(r["eps"]) not in (eps, 0.0):
            continue
        if not r["t_count"]:
            continue
        out[r["method"]] = dict(method=r["method"], arm=r["arm"], t_count=int(r["t_count"]),
                                qubits=int(r["qubits"]), err_bound=float(r["err_bound"] or 0.0),
                                error_class="approx" if r["method"] != "pyzx" else "exact",
                                resource_class="unitary", note=r["note"][:200], source="v3 baselines.csv")
    for r in _b4_rows():
        if r["label"] != label or abs(float(r["eps"]) - eps) > 1e-18:
            continue
        e, res = _tags_of_b4(r)
        out["DPF Synth"] = dict(method="DPF Synth", arm="B4", t_count=int(r["t_count"]),
                                qubits=int(r["qubits"]) + int(r["ancillas"]), ancillas=int(r["ancillas"]),
                                k_reg=int(r["k_reg"]), n_rz=int(r["n_rz"]),
                                err_bound=float(r["err_bound"]), error_class=e, resource_class=res,
                                t_min=int(r["seed_min"]), t_max=int(r["seed_max"]), seeds=int(r["seeds"]),
                                stochastic=True, source="b4_baseline.csv (greedy_ntro @ c04a3224)",
                                note="K* from our sweep, not the paper's decision matrix; k>=4 is "
                                     "measurement-based (ancilla leak measured)")
    return out


def best_baseline(label: str, eps: float = PRIMARY_EPS) -> dict:
    """The lowest-T baseline on this circuit: what the floor tier must reach (V4_README section 4)."""
    bs = baselines(label, eps)
    if not bs:
        raise KeyError(f"no baselines for {label} at eps {eps}")
    return min(bs.values(), key=lambda r: r["t_count"])


def table(labels=None, eps: float = PRIMARY_EPS) -> list:
    """One row per circuit: every baseline plus the best, for the report."""
    from .tools.evaluate import suite
    labels = labels or [c["label"] for c in suite("dv") if c["family"] == "dv_angle"]
    out = []
    for lab in labels:
        bs = baselines(lab, eps)
        out.append(dict(label=lab, eps=eps, **{m: r["t_count"] for m, r in sorted(bs.items())},
                        best=best_baseline(lab, eps)["method"],
                        best_t=best_baseline(lab, eps)["t_count"]))
    return out
