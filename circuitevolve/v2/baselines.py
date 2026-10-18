"""Reused classical baseline numbers (never recomputed here).

    table(new_path=..., include_new=True) -> pandas.DataFrame   one row per (circuit, source, arm, eps setting)
    best_classical(circuit, eps, arms="all") -> dict | None       best VALID, COMPARABLE T-count at that eps
    load_new(path) -> DataFrame                                   results/v2/baselines_new.csv (Benchmarks track)

Sources and column choices
--------------------------
1. results/bqskit_baselines/stage1/stage1_baselines_v2.csv  (source 'stage1_v2'; 8 qseed circuits x eps {1e-3, 1e-5}
   x 7 arms). T-count = `t_count_canon` (pygridsynth recount at the arm's own N_Rz and per-Rz eps; the stage-1
   README names it the comparison metric because rsgridsynth's as-run T is not a pure function of (theta, eps)).
   eps = `eps_total` (total algorithmic error, BQSKit convention). VALID iff `measured_within_eps` and
   `bound_over_eps <= 1` (code-accounted error bound within eps), with one documented exception: arm B2, whose
   bound 1.5 eps comes from a NOMINAL rounding term (realized ~1e-14, stage-1 README / bound_note) - B2 is the
   paper's Baseline and equals B0 in canonical T on every row. Consequences: B3 (bound 1.7 eps / 21.5 eps,
   stage-C fixed 1e-4 budget) and B2ft (2.0 eps, rounding count not bounded) are INVALID; B0, B1, B2, B3m, B3g
   are valid. arms="primary" restricts to B0-B3 (`primary_arm`); "all" (default) also admits the supplementary
   B3m/B3g, which gives the strongest valid classical bar (B3g wins on qpe_8 and hhl_8).
2. results/bqskit_baselines/reference_pipelines.csv  (source 'reference_pipelines'; add_17, hhl_6, mult_16, qft_32,
   shor_16 - the EVAL_FORBIDDEN held-out circuits of blocks/circuit_io). T-count = `t_count` (TKET / pyzx +
   gridsynth). These use the OLD convention eps_rz = 1e-9 PER ROTATION (total bound `eps_total_bound` = N_Rz x
   1e-9, different for every row), so they are keyed by the setting string LEGACY_RZ_1E9 = "eps_rz=1e-9", never
   by a total eps: best_classical(c, LEGACY_RZ_1E9) compares them only with each other. eps column = the row's
   own total bound. VALID iff status == 'ok'.
3. results/v2/reused/published_baselines.csv  (source 'published'; byte-identical copy of project artifact
   published_baselines.csv, sha256 in results/v2/README.md). Paper numbers at the papers' own settings
   (2409.00433: eps_block=1e-8, eps_RZ=1e-9; 2510.18000: eps^2=1e-6 ensemble means; 2603.25101: RZ counts, not T).
   Each paper row is expanded into one row per method column (reference / theirs / alt). They are CONTEXT ONLY
   (comparable=False): none is at a {1e-3, 1e-5} total-eps budget, and skill bqskit-ft-reference-baseline forbids
   using the 2409.00433 numbers as "the BQSKit baseline". RZ-count rows carry `rz_count`, t_count = NaN.
4. results/v2/baselines_new.csv  (source 'v2_new', written by the Benchmarks track; schema NEW_COLUMNS =
   circuit, source, arm, eps, t_count, qubits, notes). `source` in that file is kept as `origin`; eps is the total
   eps (BQSKit convention); every row is valid and comparable unless `notes` starts with "INVALID".

Unified columns: circuit, circuit_label, source, origin, arm, eps, eps_setting, metric, t_count, rz_count, qubits,
valid, comparable, notes. `eps_setting` is the matching key: repr-free canonical "%g" of the total eps for
stage1 / new rows (e.g. "0.001"), LEGACY_RZ_1E9 for reference pipelines, the paper's own setting text for
published rows.
"""
from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

from ..blocks import REPO

STAGE1_CSV = REPO / "results" / "bqskit_baselines" / "stage1" / "stage1_baselines_v2.csv"
REFERENCE_CSV = REPO / "results" / "bqskit_baselines" / "reference_pipelines.csv"
PUBLISHED_CSV = REPO / "results" / "v2" / "reused" / "published_baselines.csv"
NEW_CSV = REPO / "results" / "v2" / "baselines_new.csv"
# sha256 of the reused files at the time v2 was set up (checked in tests/v2; a change means the inputs moved)
SHA256 = {
    "stage1_v2": "6a6897bd3bcd4a00fd0fef2bd919630f97710d20d087338d9388ecb21481c27b",
    "reference_pipelines": "33252f88e227268330f63f98fc6ecbcea00fbbacd642cf804cf1c6a39a8b6073",
    "published": "6f44a3456110f0fa8a9af8fdada2a507b5b1817b717fdefb734288c673198aa9",
}
NEW_COLUMNS = ("circuit", "source", "arm", "eps", "t_count", "qubits", "notes")
LEGACY_RZ_1E9 = "eps_rz=1e-9"
COLUMNS = ["circuit", "circuit_label", "source", "origin", "arm", "eps", "eps_setting", "metric", "t_count",
           "rz_count", "qubits", "valid", "comparable", "notes"]
B2_NOMINAL_ROUNDING = "B2"


def eps_key(eps) -> str:
    """Matching key for a total eps (float) or a setting string."""
    if isinstance(eps, str):
        return eps
    return f"{float(eps):g}"


def canonical_name(label: str) -> str:
    """'Add-17' -> 'add_17', 'Heisenberg-7q' -> 'heisenberg_7', 'QFTAdd8 (16q)' -> 'qftadd8'; qseed names unchanged."""
    s = re.sub(r"\s*\(.*?\)\s*", "", str(label)).strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"(\d+)q$", r"\1", s)
    return s


# ------------------------------------------------------------------------------------------------ loaders
def load_stage1(path: Path = STAGE1_CSV) -> pd.DataFrame:
    s = pd.read_csv(path)
    within = s["measured_within_eps"].astype(bool)
    budget = s["bound_over_eps"] <= 1.0 + 1e-9
    valid = within & (budget | (s["arm"] == B2_NOMINAL_ROUNDING))
    notes = s["arm_desc"].astype(str) + " | bound/eps=" + s["bound_over_eps"].map("{:g}".format) + \
        " | " + s["bound_note"].astype(str)
    notes = notes.where(~((s["arm"] == B2_NOMINAL_ROUNDING) & ~budget),
                        notes + " | valid: rounding term nominal (realized ~1e-14, stage-1 README)")
    return pd.DataFrame(dict(
        circuit=s["circuit"], circuit_label=s["circuit"], source="stage1_v2", origin=str(path.relative_to(REPO)),
        arm=s["arm"], eps=s["eps_total"].astype(float), eps_setting=s["eps_total"].map(eps_key),
        metric="T-count (t_count_canon)", t_count=s["t_count_canon"].astype(float), rz_count=s["nonclifford_rotations"],
        qubits=s["qubits"], valid=valid.astype(bool), comparable=True, primary_arm=s["primary_arm"].astype(bool),
        notes=notes))


def load_reference(path: Path = REFERENCE_CSV) -> pd.DataFrame:
    r = pd.read_csv(path)
    return pd.DataFrame(dict(
        circuit=r["circuit"], circuit_label=r["circuit"], source="reference_pipelines",
        origin=str(path.relative_to(REPO)), arm=r["pipeline"], eps=r["eps_total_bound"].astype(float),
        eps_setting=LEGACY_RZ_1E9, metric="T-count (gridsynth eps_rz=1e-9 per rotation)",
        t_count=r["t_count"].astype(float), rz_count=r["rz_count"], qubits=r["qubits"],
        valid=(r["status"] == "ok"), comparable=True, primary_arm=True,
        notes="old per-rotation convention; eps = N_Rz x 1e-9 total bound; held-out (EVAL_FORBIDDEN) circuit"))


def load_published(path: Path = PUBLISHED_CSV) -> pd.DataFrame:
    p = pd.read_csv(path)
    rows = []
    for _, r in p.iterrows():
        for mcol, vcol in (("reference_method", "reference"), ("their_method", "theirs"), ("alt_method", "alt")):
            meth, val = r.get(mcol), r.get(vcol)
            if not isinstance(meth, str) or val is None or (isinstance(val, float) and math.isnan(val)):
                continue
            is_t = str(r["metric"]).lower().startswith("t-count")
            rows.append(dict(
                circuit=canonical_name(r["circuit"]), circuit_label=r["circuit"], source="published",
                origin=f"{r['paper']} ({r['source_location']})", arm=meth, eps=float("nan"),
                eps_setting=str(r["setting"]), metric=str(r["metric"]),
                t_count=float(val) if is_t else float("nan"), rz_count=float("nan") if is_t else float(val),
                qubits=float("nan"), valid=True, comparable=False, primary_arm=False,
                notes=f"published context only (in_qseed={r.get('in_qseed')}); column {vcol}"))
    return pd.DataFrame(rows)


def load_new(path: Path = NEW_CSV) -> pd.DataFrame:
    """Rows written by the Benchmarks track. Missing file -> empty frame; wrong schema -> ValueError."""
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS + ["primary_arm"])
    n = pd.read_csv(path)
    missing = [c for c in NEW_COLUMNS if c not in n.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; schema is {NEW_COLUMNS}")
    notes = n["notes"].fillna("").astype(str)
    valid = ~notes.str.upper().str.startswith("INVALID")
    try:
        origin = str(path.resolve().relative_to(REPO))
    except ValueError:
        origin = str(path)
    return pd.DataFrame(dict(
        circuit=n["circuit"].astype(str), circuit_label=n["circuit"].astype(str), source="v2_new",
        origin=origin + " | " + n["source"].astype(str), arm=n["arm"].astype(str), eps=n["eps"].astype(float),
        eps_setting=n["eps"].map(eps_key), metric="T-count", t_count=n["t_count"].astype(float),
        rz_count=float("nan"), qubits=n["qubits"], valid=valid, comparable=True, primary_arm=True, notes=notes))


def table(new_path: Path | None = None, include_new: bool = True, include_published: bool = True) -> pd.DataFrame:
    parts = [load_stage1(), load_reference()]
    if include_published:
        parts.append(load_published())
    if include_new:
        nw = load_new(new_path or NEW_CSV)
        if len(nw):
            parts.append(nw)
    out = pd.concat(parts, ignore_index=True)
    return out[COLUMNS + ["primary_arm"]]


def best_classical(circuit: str, eps, arms: str = "all", tab: pd.DataFrame | None = None,
                   new_path: Path | None = None) -> dict | None:
    """Lowest valid, comparable T-count for `circuit` at total eps (float) or setting key (e.g. LEGACY_RZ_1E9).
    arms: 'all' | 'primary' (stage-1 B0-B3 only). Returns the row as a dict (plus 'ties': arms with the same T),
    or None when no row matches. Never mixes eps settings."""
    if arms not in ("all", "primary"):
        raise ValueError("arms must be 'all' or 'primary'")
    t = tab if tab is not None else table(new_path=new_path)
    sel = t[(t["circuit"] == circuit) & (t["eps_setting"] == eps_key(eps)) & t["valid"] & t["comparable"]
            & t["t_count"].notna()]
    if arms == "primary":
        sel = sel[sel["primary_arm"]]
    if sel.empty:
        return None
    sel = sel.sort_values(["t_count", "source", "arm"], kind="stable")
    best = sel.iloc[0].to_dict()
    best["ties"] = sorted(sel.loc[sel["t_count"] == best["t_count"], "arm"].astype(str).tolist())
    return best
