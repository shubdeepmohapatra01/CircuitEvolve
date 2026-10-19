"""recon_campaign1 — first real-LLM reconstruction campaign (PLAN approved 2026-10-19).

Driven FROM the platform kernel (needs host.llm): import this module and call
run_dev(host.llm) / run_held_out(host.llm). Models pinned by the user:

    PROPOSER  = claude-opus-5-5     ("opus for reasoning")
    REFLECTOR = claude-sonnet-5-5   ("sonnet for compiling rules")

Protocol (mirrors docs/P2_CAMPAIGN.md conventions, reconstruction family):
  - Single method stage: manifest {'method': 'reconstruction'} — this campaign trains the
    reconstruction playbook; the angle stage is out of scope (deferred P2 campaign).
  - DEV (learning ON, playbook mutable, reflector every 8 calls): cuccaro_4, cuccaro_8,
    barenco_tof_5, tof_5, rc_adder_6 — 20 proposer calls each, batch 1, seed 0.
  - HELD-OUT (playbook frozen=True, reflector OFF): cuccaro_16, adder_8, qcla_adder_10,
    barenco_tof_10, mod_adder_1024, gf2^4_mult — 12 calls each. SHA-256 of the playbook is
    recorded before held-out (freeze procedure).
  - Zero-LLM comparators per circuit (cost nothing, recorded in the report): deterministic
    control route, naive_T, committed B0/B1 from results/engine/recon_bench/baselines.csv.
  - Declared-zero contracts from benchmarks/nam_arith/MANIFEST.csv — never guessed.
  - Every run tagged; JSONL logs under results/engine/recon_campaign1/runs/ (append-only).

Progress: the LLM backend is wrapped in an ASCII progress bar printed per proposer call
(visible in background-cell peeks): [#####...............]  5/20 cuccaro_4 · 3.2m · NONE
"""
from __future__ import annotations

import csv
import hashlib
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROPOSER = "claude-opus-5-5"
REFLECTOR = "claude-sonnet-5-5"
DEV = ["cuccaro_4", "cuccaro_8", "barenco_tof_5", "tof_5", "rc_adder_6"]
HELD = ["cuccaro_16", "adder_8", "qcla_adder_10", "barenco_tof_10", "mod_adder_1024", "gf2^4_mult"]
EPS = 1e-3
OUT = ROOT / "results" / "engine" / "recon_campaign1"
PLAYBOOK = ROOT / "playbooks" / "families" / "reconstruction.json"


def _manifest_dz():
    rows = {r["name"]: r for r in csv.DictReader(open(ROOT / "benchmarks/nam_arith/MANIFEST.csv"))}
    return {n: [int(x) for x in str(rows[n].get("zero_init_qubits") or "").split()] for n in rows}, rows


class Progress:
    """tqdm-style bar over proposer calls, newline per update (peek-friendly)."""

    def __init__(self, total: int, label: str):
        self.total, self.label, self.done, self.t0 = total, label, 0, time.time()

    def wrap(self, complete):
        def wrapped(prompts):
            out = complete(prompts)
            self.done += len(prompts)
            k = min(self.done, self.total)
            fill = int(20 * k / self.total)
            mins = (time.time() - self.t0) / 60
            def kind(o):                            # backend returns RuntimeError objects on failure
                if not isinstance(o, str):
                    return "ERR"
                return "NONE" if o.strip().upper().startswith("NONE") else "plan"
            kinds = ",".join(kind(o) for o in out)
            print(f"[{'#' * fill}{'.' * (20 - fill)}] {k:>3}/{self.total} {self.label}"
                  f" · {mins:4.1f}m · {kinds}", flush=True)
            return out
        wrapped.stats = getattr(complete, "stats", None)
        return wrapped


def run_circuit(llm, name: str, calls: int, frozen: bool, seed: int = 0, phase: str = None) -> dict:
    from circuitevolve.engine.run import optimize
    from circuitevolve.llm_backends import make_api_backend
    dzmap, rows = _manifest_dz()
    src = str(ROOT / "benchmarks/nam_arith" / rows[name]["logical_path"])
    bar = Progress(calls, name)
    # 5-5 generation models reject thinking=disabled; adaptive is their native mode. Thinking
    # tokens count toward max_tokens, hence the raised cap (empty text retries as transient).
    complete = bar.wrap(make_api_backend(llm, model=PROPOSER,
                                         thinking={"type": "adaptive"}, max_tokens=16000))
    reflect = None if frozen else make_api_backend(llm, model=REFLECTOR,
                                                   thinking={"type": "adaptive"}, max_tokens=16000)
    if frozen:                                        # freeze procedure: active rules shown,
        kw = dict(playbook_path=str(PLAYBOOK), playbook_frozen=True)   # no mutation, no reflect,
    else:                                                              # never saved back
        kw = dict(playbook_path=str(PLAYBOOK))        # mutable: loop saves it back after the run
    phase = phase or ("held" if frozen else "dev")
    t0 = time.time()
    summ = optimize(src, EPS, complete,
                    manifest={"declared_zero": dzmap[name], "method": "reconstruction"},
                    runs_dir=OUT / "runs", tag=f"recon_c1_{phase}_{name}",
                    n_calls=calls, batch=1, seed=seed,
                    reflect_complete=reflect, **kw)
    keep = dict(circuit=name, phase=phase, t_before=summ["t_before"], t_after=summ["t_after"],
                qubits_after=summ["after"]["qubits"], mode_after=summ["after"]["mode"],
                stats=summ["stats"], ledger_bound=summ["ledger"]["bound"],
                verified=summ["final_check_vs_original"]["ok"],
                playbook=summ.get("playbook"), seconds=round(time.time() - t0, 1),
                archive=summ["archive"])
    print(f"== {name} DONE: T {keep['t_before']} -> {keep['t_after']} "
          f"({keep['mode_after']}), accepted {keep['stats']['accepted']}, "
          f"declined {keep['stats']['declined']}, {keep['seconds']}s", flush=True)
    return keep


def _playbook_sha() -> str:
    return hashlib.sha256(PLAYBOOK.read_bytes()).hexdigest()


def run_dev(llm, calls: int = 20) -> list:
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"DEV start · proposer {PROPOSER} · reflector {REFLECTOR} · "
          f"playbook sha {_playbook_sha()[:16]}", flush=True)
    results = [run_circuit(llm, n, calls, frozen=False) for n in DEV]
    p = OUT / "dev_results.json"
    if p.exists():
        raise SystemExit(f"{p} exists (append-only)")
    p.write_text(json.dumps(dict(proposer=PROPOSER, reflector=REFLECTOR, calls=calls,
                                 playbook_sha_after=_playbook_sha(), circuits=results), indent=1))
    print("DEV phase complete ->", p.relative_to(ROOT), flush=True)
    return results


# ---------------------------------------------------------------- overnight sweep (approved
# scope (a), 2026-10-19): learning ON over every structure-bearing, parseable, non-blocked
# benchmark circuit EXCEPT the at-floor campaign circuits and SWEEP_RESERVED (kept untouched
# as the FUTURE frozen held-out set — tonight's sweep converts everything it trains on into
# dev circuits forever). gf2^4_mult's missed frozen slot (token ceiling) is completed
# frozen-FIRST (phase='held2') before learning may touch it. Sequential execution only:
# the playbook is a single mutable file (one writer).
SWEEP_RESERVED = ["ham15-med", "gf2^6_mult", "hwb6", "mod_red_21"]
SWEEP = {  # name -> proposer calls (giants capped: per-plan verification is minutes there)
    "tof_3": 12, "barenco_tof_3": 12, "mod5_4": 12, "tof_4": 12, "mod_mult_55": 12,
    "barenco_tof_4": 12, "vbe_adder_3": 12, "csla_mux_3": 12, "gf2^4_mult": 16,
    "tof_10": 16, "ham15-low": 16, "gf2^5_mult": 16, "csum_mux_9": 16,
    "grover_5": 24, "gf2^7_mult": 24, "adder_8": 24, "gf2^8_mult": 24, "gf2^9_mult": 24,
    "gf2^10_mult": 24, "mod_adder_1024": 24, "ham15-high": 16, "gf2^16_mult": 12,
    "gf2^32_mult": 8,
}
SWEEP_CHUNKS = [
    ["tof_3", "barenco_tof_3", "mod5_4", "tof_4", "mod_mult_55", "barenco_tof_4",
     "vbe_adder_3", "csla_mux_3", "gf2^4_mult"],
    ["tof_10", "ham15-low", "gf2^5_mult", "csum_mux_9", "grover_5", "gf2^7_mult", "adder_8"],
    ["gf2^8_mult", "gf2^9_mult", "gf2^10_mult", "mod_adder_1024", "ham15-high",
     "gf2^16_mult", "gf2^32_mult"],
]


def run_sweep(llm, names: list, out_name: str = "sweep_results.jsonl") -> list:
    """Resumable learning sweep: one JSONL row appended per finished circuit; circuits already
    in the file are skipped on re-entry. STOP on first budget-ceiling signature (every call
    ERR, 0s) and report rather than burn the remaining list."""
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / out_name
    done = {json.loads(l)["circuit"] for l in open(p)} if p.exists() else set()
    results = []
    for n in names:
        assert n not in SWEEP_RESERVED, f"{n} is reserved as future held-out"
        if n in done:
            print(f"-- {n}: already in {out_name}, skipping", flush=True)
            continue
        r = run_circuit(llm, n, SWEEP[n], frozen=False, phase="sweep")
        with open(p, "a") as fh:
            fh.write(json.dumps(r) + "\n")
        results.append(r)
        st = r["stats"]
        if st["llm_errors"] >= SWEEP[n] and st["accepted"] == 0 and r["seconds"] < 5:
            print("!! budget-ceiling signature: stopping sweep", flush=True)
            break
    return results


def run_held_out(llm, calls: int = 12) -> list:
    sha = _playbook_sha()
    print(f"HELD-OUT start · playbook FROZEN sha256 {sha}", flush=True)
    results = [run_circuit(llm, n, calls, frozen=True) for n in HELD]
    p = OUT / "heldout_results.json"
    if p.exists():
        raise SystemExit(f"{p} exists (append-only)")
    p.write_text(json.dumps(dict(proposer=PROPOSER, calls=calls, playbook_sha_frozen=sha,
                                 circuits=results), indent=1))
    print("HELD-OUT phase complete ->", p.relative_to(ROOT), flush=True)
    return results
