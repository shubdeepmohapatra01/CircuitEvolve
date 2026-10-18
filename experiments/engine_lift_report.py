"""P3.4 — lifting recovery report over the reconstruction benchmark suite.

Deterministic, no LLM. Two lift targets per suite circuit:

  stress  the committed P3.1 twins (results/engine/recon_bench/decomposed/*.qasm,
          blocks/classical.tket_optimise = FullPeepholeOptimise + rebase): recovery measured
          honestly — the exhaustive exact matcher finds whatever survives global peephole
          optimization (finding: typically NOTHING; see the note in the report).
  base    macro-expanded forms written here once to recon_bench/decomposed_plain/*.qasm
          (standard qelib 7-T splice of every ccx/ccz in the RAW suite circuit — what a
          toolchain emits when it expands macros without re-optimizing): the realistic
          lift target; recovery measured against the raw Toffoli count.

Writes results/engine/recon_bench/lifting_report.json (+ the decomposed_plain twins with
sha256s). Append-only: refuses to overwrite existing outputs. No minimum recovery is imposed
(PLAN_P3 P3.4); the numbers are recorded as found, and the zero-false-structure property is
re-verified by tests/engine/test_lift.py (every substitution is exactly verified in D[omega]
by construction).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from circuitevolve.engine.lift import expand_toffolis, pre_recognize  # noqa: E402
from circuitevolve.engine.tketpass import _emit_qasm, read_qasm_ops  # noqa: E402

RB = ROOT / "results" / "engine" / "recon_bench"
PLAIN = RB / "decomposed_plain"
OUT = RB / "lifting_report.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    if OUT.exists() or PLAIN.exists():
        raise SystemExit("lifting outputs already exist (results/ is append-only); refusing")
    PLAIN.mkdir(parents=True)
    manifest = json.loads((RB / "MANIFEST.json").read_text())
    rows = []
    for e in manifest["circuits"]:
        if not e["kept"]:
            continue
        name, tofs = e["name"], e["features"]["toffolis"]
        naive_t = 7 * tofs + e["features"]["t_like"]

        def row(rep, lifted_text):
            r = dict(recovered_ccx=rep.get("ccx", 0), rccx_spotted=rep.get("rccx_spotted", 0),
                     toffolis_original=tofs, naive_t=naive_t,
                     t_absorbed=rep.get("t_absorbed", 0),
                     recovery_rate=round(rep.get("ccx", 0) / tofs, 4) if tofs else None,
                     t_share_lifted=round(rep.get("t_absorbed", 0) / naive_t, 4) if naive_t else None,
                     skipped=rep.get("skipped"))
            if lifted_text is not None:
                _n2, lops = read_qasm_ops(lifted_text)
                r["t_left"] = sum(1 for g, _q, _a in lops if g in ("t", "tdg"))
            return r

        # ---- stress target: the committed FullPeepholeOptimise twin
        lifted, rep = pre_recognize(ROOT / e["twin"]["path"])
        stress = row(rep, lifted)
        # ---- base target: macro-expanded raw form (written once, sha256 recorded)
        n, raw_ops = read_qasm_ops((ROOT / e["source"]).read_text())
        expanded = expand_toffolis(raw_ops)
        p = PLAIN / f"{name}.qasm"
        p.write_text(_emit_qasm(expanded, n))
        lifted2, rep2 = pre_recognize(p)
        base = row(rep2, lifted2)
        base["plain_twin"] = dict(path=str(p.relative_to(ROOT)), sha256=sha(p),
                                  gates=len(expanded))
        if lifted2 is not None:                 # naive-T conservation vs the RAW source
            n3, lops = read_qasm_ops(lifted2)
            t_left = sum(1 for g, _q, _a in lops if g in ("t", "tdg"))
            ccx_l = sum(1 for g, _q, _a in lops if g == "ccx")
            base["t_conserved"] = bool(7 * ccx_l + t_left == naive_t)
        rows.append(dict(circuit=name, split=e["split"], stress=stress, base=base))
        print(f"{name}: stress {stress['recovered_ccx']}/{tofs}, base {base['recovered_ccx']}/{tofs}")
    report = dict(
        format="circuitevolve.lifting_report/1",
        provenance="P3.4 (docs/PLAN_P3.md): exact D[omega] span matcher (engine/lift.py) over "
                   "two decomposed targets per suite circuit; every substitution exactly "
                   "verified; no minimum recovery imposed.",
        finding="FullPeepholeOptimise twins (the P3.1 stress set) carry NO exact CCX/RCCX "
                "projected spans: global peephole optimization absorbs Toffoli-local Cliffords "
                "into neighbours and cancels T across construction boundaries, so span-exact "
                "lifting recovers nothing there — recorded honestly rather than relaxed. The "
                "macro-expanded base set (decomposed_plain/, standard qelib splice) is the "
                "realistic lift target and recovery there is per-circuit below.",
        circuits=rows)
    OUT.write_text(json.dumps(report, indent=1))
    print(f"\nwrote {OUT.relative_to(ROOT)} ({len(rows)} circuits)")


if __name__ == "__main__":
    main()
