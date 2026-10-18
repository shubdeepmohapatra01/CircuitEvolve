"""P3.1 — reconstruction benchmark suite: curation + decomposed twins + baselines.

Deterministic, no LLM. Reads benchmarks/nam_arith (MANIFEST.csv; logical/ + generated/ raw
forms) and the stage-1 rotation inputs (results/bqskit_baselines/stage1/inputs). Writes, once
(append-only: refuses to overwrite):

  results/engine/recon_bench/MANIFEST.json      every candidate scanned, feature evidence,
                                                kept flag + reason, dev|held-out split,
                                                sha256 of source and (kept) decomposed twin
  results/engine/recon_bench/decomposed/*.qasm  TKET-decomposed twin of every kept circuit
                                                (the lifting stress set, P3.4)
  results/engine/recon_bench/baselines.csv      per kept circuit: naive_T, B0 (TKET), B1
                                                (pyzx), v2 tier-1 deterministic control
                                                (exact + relaxed rows, relaxed separate)

Curation rule (PLAN_P3 §P3.1 + §5.1): keep iff >=1 Toffoli pair OR >=1 MCX cascade OR
naive-T share in Toffolis >= 20%, restricted to the plan-named suite (dev: cuccaro_4,
cuccaro_8, barenco_tof_5, tof_5, rc_adder_6; held-out: cuccaro_16, adder_8, qcla_adder_10,
barenco_tof_10, mod_adder_1024, gf2^4_mult). Other firing circuits are recorded with
kept=false reason="curation cap" — evidence preserved for later extension.

Baseline provenance: B0/B1/control rows are copied from the verified v2 records
(results/v2/tier1/dev_results.csv, results/v2/eval/eval_results.csv) — recorded, not re-run;
naive_T and the twin T-count are computed here. Twin generation follows the exact TKET pass
sequence of circuitevolve.blocks.classical.tket_optimise / experiments.v2_bench_common.tket_arm
(FullPeepholeOptimise -> replace_implicit_wire_swaps -> AutoRebase{CX,H,Rz} ->
RemoveRedundancies), with rz pi/4-multiples lowered to named Clifford+T gates (emit_rz) and a
sparse 24-trial equivalence check against the raw form recorded per twin.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments"))

from circuitevolve.v2.tier1.recognize import load_logical, summarize  # noqa: E402

BENCH = ROOT / "benchmarks" / "nam_arith"
STAGE1 = ROOT / "results" / "bqskit_baselines" / "stage1" / "inputs"
OUT = ROOT / "results" / "engine" / "recon_bench"

DEV = ["cuccaro_4", "cuccaro_8", "barenco_tof_5", "tof_5", "rc_adder_6"]
HELD = ["cuccaro_16", "adder_8", "qcla_adder_10", "barenco_tof_10", "mod_adder_1024", "gf2^4_mult"]
SUITE = {**{c: "dev" for c in DEV}, **{c: "held-out" for c in HELD}}

DEV_CSV = ROOT / "results" / "v2" / "tier1" / "dev_results.csv"
EVAL_CSV = ROOT / "results" / "v2" / "eval" / "eval_results.csv"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def features_from_summary(s) -> dict:
    naive_tof = 7 * len(s.toffolis)
    denom = naive_tof + s.rotations["t_like"]
    share = (naive_tof / denom) if denom else 0.0
    pairs_by_cls = {}
    for p in s.pairs:
        pairs_by_cls[p["cls"]] = pairs_by_cls.get(p["cls"], 0) + 1
    return dict(
        n=s.n, n_gates=s.n_gates, gate_counts=s.gate_counts, classical=s.classical,
        toffolis=len(s.toffolis), pairs=len(s.pairs), pairs_by_class=pairs_by_cls,
        mcx=len(s.mcx), unpaired=len(s.unpaired), t_like=s.rotations["t_like"],
        naive_t_share=round(share, 4), declared_zero=list(s.declared_zero),
        clean_ancillas=sum(1 for q in s.qubits if q["role"] == "ancilla(clean)"),
        digest=s.digest,
    )


def fires(f: dict) -> bool:
    return f["pairs"] >= 1 or f["mcx"] >= 1 or f["naive_t_share"] >= 0.2


def scan_stage1(path: Path) -> dict:
    """Rotation inputs carry arbitrary rz angles (outside the exact-IR parser's pi/4 grid):
    scan with the angle-tolerant reader; the predicate inputs (toffoli/pair/mcx counts) are
    all zero whenever no ccx/ccz is present, which is what decides kept=false here."""
    from v2_bench_common import counts, read_qasm
    n, ops = read_qasm(str(path))
    cnt = counts(ops)
    tof = cnt.get("ccx", 0) + cnt.get("ccz", 0)
    t_like = cnt.get("t", 0) + cnt.get("tdg", 0)
    share = (7 * tof / (7 * tof + t_like)) if (tof or t_like) else 0.0
    return dict(n=n, n_gates=len(ops), gate_counts=dict(cnt), classical=False,
                toffolis=tof, pairs=0, pairs_by_class={}, mcx=0, unpaired=tof,
                t_like=t_like, naive_t_share=round(share, 4), declared_zero=[],
                clean_ancillas=0, digest=None,
                note="counts-only scan (general rz angles; recognizer needs the exact IR)")


def make_twin(raw_path: Path, name: str) -> tuple[list, int, dict]:
    """TKET decomposition of the raw circuit; returns (named ops, n, sparse check record)."""
    from v2_bench_common import read_qasm, sparse_pair_check, tket_arm
    from circuitevolve.blocks.circuit_io import emit_rz
    n, ops = read_qasm(str(raw_path))
    rec = tket_arm(ops, n)
    named = []
    for g, qs, a in rec["ops"]:
        if g == "rz":
            emit_rz(named, qs[0], a)
        else:
            named.append((g, qs, a))
    bad = [op for op in named if op[0] == "rz"]
    if bad:
        raise ValueError(f"{name}: twin kept {len(bad)} non-pi/4 rz after lowering")
    check = sparse_pair_check(ops, named, n)
    if check.get("ok") is None:  # sparse support cap hit: indeterminate -> ZX identity instead
        from v2_bench_common import zx_identity
        check = dict(method="zx_identity (sparse support > cap)", ok=bool(zx_identity(ops, named, n)))
    if check.get("ok") is not True:
        raise ValueError(f"{name}: twin equivalence check failed: {check}")
    return named, n, check


def main() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"{OUT} already populated (results/ is append-only); refusing to overwrite")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "decomposed").mkdir(exist_ok=True)
    from v2_bench_common import counts as op_counts, write_qasm

    # ---------------------------------------------------------------- scan candidates
    rows = list(csv.DictReader(open(BENCH / "MANIFEST.csv")))
    entries = []
    for row in rows:
        name = row["name"]
        rel = row["logical_path"]
        if not rel:
            continue
        src = BENCH / rel
        dz = [int(x) for x in str(row.get("zero_init_qubits") or "").split()]
        try:
            orig, lc = load_logical(src, name=name)
        except ValueError as err:
            f = scan_stage1(src)
            f["note"] = f"counts-only scan (exact-IR parse failed: {err})"
            entries.append(dict(name=name, source=str(src.relative_to(ROOT)), source_sha256=sha(src),
                                source_kind="nam_arith/logical", v2_split=row.get("split"),
                                features=f, fires=fires(f), kept=False,
                                reason="raw form outside the exact-IR gate set (general-angle "
                                       "u1/rz); recognizer not applicable", split=None))
            continue
        s = summarize(lc, declared_zero=dz, name=name)
        f = features_from_summary(s)
        fire = fires(f)
        kept = fire and name in SUITE
        reason = ("kept" if kept else
                  ("curation cap: features fire but circuit is outside the plan-named suite "
                   "(evidence preserved for later extension)" if fire else
                   "no structural features (no pair, no MCX, naive-T share < 20%)"))
        entries.append(dict(name=name, source=str(src.relative_to(ROOT)), source_sha256=sha(src),
                            source_kind="nam_arith/" + ("generated" if "generated/" in rel else "logical"),
                            v2_split=row.get("split"), features=f, fires=fire, kept=kept,
                            reason=reason, split=SUITE.get(name)))
    for p in sorted(STAGE1.glob("*_tket.qasm")):
        f = scan_stage1(p)
        entries.append(dict(name=p.stem, source=str(p.relative_to(ROOT)), source_sha256=sha(p),
                            source_kind="stage1/inputs", v2_split=None, features=f, fires=fires(f),
                            kept=False, reason="no Toffoli structure (rotation circuit; the angle "
                            "method's domain, not reconstruction's)", split=None))

    missing = [c for c in SUITE if not any(e["name"] == c and e["fires"] for e in entries)]
    if missing:
        raise SystemExit(f"plan-named suite circuits do not fire features: {missing}")

    # ---------------------------------------------------------------- decomposed twins
    for e in entries:
        if not e["kept"]:
            continue
        named, n, check = make_twin(ROOT / e["source"], e["name"])
        qasm = write_qasm(named, n)
        tw = OUT / "decomposed" / f"{e['name']}.qasm"
        tw.write_text(qasm)
        cnt = op_counts(named)
        e["twin"] = dict(path=str(tw.relative_to(ROOT)), sha256=sha(tw), n=n, gates=len(named),
                         t_count=cnt.get("t", 0) + cnt.get("tdg", 0), counts=dict(cnt),
                         sparse_check_ok=bool(check.get("ok")),
                         method="tket_arm (FullPeepholeOptimise->AutoRebase{CX,H,Rz}->"
                                "RemoveRedundancies) + emit_rz lowering")
        print(f"twin {e['name']}: {e['twin']['t_count']} T, {e['twin']['gates']} gates, "
              f"sparse ok={e['twin']['sparse_check_ok']}")

    # ---------------------------------------------------------------- baselines from v2 records
    dev_rows = list(csv.DictReader(open(DEV_CSV)))
    eval_rows = list(csv.DictReader(open(EVAL_CSV)))

    def controls(name):
        out = []
        for r in dev_rows:
            if r["circuit"] == name and r["arm"] == "control" and r.get("ok") == "True":
                out.append((r, "results/v2/tier1/dev_results.csv"))
        for r in eval_rows:
            if r["circuit"] == name and r["arm"] == "tier1_control" and r.get("ok") == "True":
                out.append((r, "results/v2/eval/eval_results.csv"))
        return out

    def bench_T(name, arm):
        for run in ("run2", "run1", "run3_large"):
            p = ROOT / "results" / "v2" / "bench_runs" / run / f"{name}.json"
            if p.exists():
                rec = json.load(open(p)).get("arms", {}).get(arm)
                if isinstance(rec, dict) and "t_count" in rec:
                    return float(rec["t_count"]), f"results/v2/bench_runs/{run}/{name}.json"
        return None, None

    def ref_T(name, col):
        for rs, src in ((dev_rows, "results/v2/tier1/dev_results.csv"),
                        (eval_rows, "results/v2/eval/eval_results.csv")):
            for r in rs:
                if r["circuit"] == name and r.get(col):
                    return float(r[col]), src
        return None, None

    brows = []
    for e in entries:
        if not e["kept"]:
            continue
        name, f = e["name"], e["features"]
        naive = 7 * f["toffolis"] + f["t_like"]
        brows.append(dict(circuit=name, split=e["split"], arm="naive_T", contract="exact",
                          t_count=naive, qubits=f["n"], ancillas=0,
                          source="computed here: 7*toffolis + t_like on the raw form", notes=""))
        xref, xsrc = ref_T(name, "tket_fpo_logical_T")
        brows.append(dict(circuit=name, split=e["split"], arm="B0_tket", contract="exact",
                          t_count=e["twin"]["t_count"], qubits=f["n"], ancillas=0,
                          source="computed here: decomposed twin (same pass sequence as the "
                                 "v2 tket_fpo_logical arm, raw form)",
                          notes=(f"v2 cross-ref tket_fpo_logical_T={int(xref)} ({xsrc})"
                                 if xref is not None else "no v2 tket_fpo_logical record")))
        v, src = ref_T(name, "pyzx_fr_T")
        if v is None:
            v, src = bench_T(name, "pyzx_fr")
        if v is None:
            raise SystemExit(f"{name}: no pyzx_fr record in v2 results")
        brows.append(dict(circuit=name, split=e["split"], arm="B1_pyzx", contract="exact",
                          t_count=int(v), qubits=f["n"], ancillas=0, source=src,
                          notes="recorded v2 pyzx full_reduce arm"))
        ctl = controls(name)
        if not ctl:
            blocked = [r for r in eval_rows if r["circuit"] == name and r["arm"] == "blocked"]
            if not blocked:
                raise SystemExit(f"{name}: no v2 control rows and no blocked record")
            brows.append(dict(circuit=name, split=e["split"], arm="control_blocked",
                              contract="", t_count="", qubits="", ancillas="",
                              source="results/v2/eval/eval_results.csv",
                              notes=(blocked[0].get("notes") or "")[:200]))
            continue
        for mode in ("exact", "relaxed"):
            cand = [(r, s) for r, s in ctl if r.get("mode") == mode]
            if not cand:
                continue
            r, src = min(cand, key=lambda t: float(t[0]["t_count"]))
            brows.append(dict(circuit=name, split=e["split"], arm=f"control_{mode}",
                              contract=mode, t_count=int(float(r["t_count"])),
                              qubits=int(float(r["qubits"])),
                              ancillas=int(float(r["ancillas"] or 0)), source=src,
                              notes=f"v2 deterministic control variant {r.get('variant')}, "
                                    f"global_pass {r.get('global_pass')}"))
    with open(OUT / "baselines.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["circuit", "split", "arm", "contract", "t_count",
                                           "qubits", "ancillas", "source", "notes"])
        w.writeheader()
        w.writerows(brows)

    manifest = dict(
        format="circuitevolve.recon_bench/1",
        provenance="P3.1 (docs/PLAN_P3.md): v2 recognizer evidence on RAW forms; suite = "
                   "plan-named circuits whose features fire; twins = TKET decomposition "
                   "(lifting stress set); baselines copied from verified v2 records.",
        predicate="pairs>=1 OR mcx>=1 OR naive_t_share>=0.2 (naive_t_share = 7*toffolis / "
                  "(7*toffolis + t_like) on the raw form)",
        dev=DEV, held_out=HELD, circuits=entries)
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    kept = [e for e in entries if e["kept"]]
    print(f"\nscanned {len(entries)} candidates; kept {len(kept)} "
          f"({sum(e['fires'] for e in entries)} fire); baselines rows {len(brows)}")


if __name__ == "__main__":
    main()
