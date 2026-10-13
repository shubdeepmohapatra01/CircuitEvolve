"""No-LLM block pipeline on dev circuits: per-block passes only vs whole-circuit fold first.
Run: .venv/bin/python experiments/blocks_deterministic.py TAG circuit ..."""
import csv
import sys

from circuitevolve.blocks import REPO
from circuitevolve.blocks.cost_model import Gridsynth
from circuitevolve.blocks.pipeline import run_pipeline
from circuitevolve.blocks.rules import RuleLibrary


def main():
    tag, names = sys.argv[1], sys.argv[2:]
    out = REPO / "results" / "blocks" / f"{tag}.csv"
    assert not out.exists(), f"{out} exists; results are append-only"
    gs, rows = Gridsynth(), []
    for nm in names:
        for gf in (False, True):
            r = run_pipeline(nm, None, gs, RuleLibrary(REPO / ".cache" / "blocks" / "no_rules.json"), global_fold=gf)
            rows.append(dict(circuit=nm, n=r["n"], global_fold=gf, input_pipeline=r["input_pipeline"],
                             pyzx_t=r["classical"]["pyzx"]["raw"]["t"], tket_t=r["classical"]["tket"]["raw"]["t"],
                             input_t=r["input_cost"]["t"], input_rz=r["input_cost"]["rz"],
                             output_t=r["output_cost"]["t"], output_rz=r["output_cost"]["rz"],
                             t_saved=r["t_saved"], classical_pass_blocks=r["classical_pass_blocks"],
                             n_blocks=r["n_blocks"], n_structures=r["n_structures"],
                             whole_check=r["whole_circuit_check"]["method"],
                             whole_dist=r["whole_circuit_check"].get("dist"), error_bound=r["error_bound"]))
            print(rows[-1], flush=True)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
