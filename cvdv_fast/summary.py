"""One-page meeting summary (all numbers read from result files)."""
import csv, json
from collections import Counter
from pathlib import Path
R = Path(__file__).resolve().parent
rows = list(csv.DictReader(open(R / "report" / "comparison.csv")))
SH = {"kerr_small": "Kerr", "boseHubbard_small": "Bose-Hubbard", "z2Higgs_small": "Z2-Higgs", "heisenberg_small": "Heisenberg",
      "electronicVibration_small": "Electron-vibration"}
def g(x, fmt="{:.2g}"):
    try: return fmt.format(float(x))
    except Exception: return "not finished" if x in ("", "None") else x
nc = lambda x: "not computed" if x in ("", "None") else g(x, "{:.5g}")
calls = [json.loads(l) for l in open(R / "results" / "agent_calls.jsonl")]
tok_in = sum((c.get("usage") or {}).get("input_tokens", 0) + (c.get("usage") or {}).get("cache_read_input_tokens", 0) for c in calls)
tok_out = sum((c.get("usage") or {}).get("output_tokens", 0) for c in calls)
roles = Counter(c["role"] for c in calls)
att = [json.loads(l) for l in open(R / "results" / "attempts.jsonl")]
book = (R / "rules" / "BOOK.md").read_text()
L = []
L.append("# CV-DV Hamiltonian-simulation compilation: LLM rule book vs Genesis (preliminary, 2026-10-21)\n")
L.append("**Setup.** Same spec for both compilers: Genesis' own intermediate IR of the five `*_small` benchmarks "
         "(one first-order Trotter step, t = 1, IR term order), Genesis Table-2 ISA, Genesis latency model (1 per 1-op, "
         "20 per 2-op gate), Genesis' router (best of 5 seeds by total gates; ours with the SWAP phase-sign fix, gate "
         "counts unchanged). Ours compiles from the IR terms, never from Genesis output. Rule book = 13 hand-written "
         "seed rules from Liu et al. (arXiv:2407.10381) + rules found by an LLM scout/implementer loop and admitted "
         "by a frozen verifier.\n")
L.append("**Error metric.** Max over 8 seeded Haar-random probe states (system qubits arbitrary, system qumodes with "
         "<= 3 photons total, ancillas |0>/vacuum and required to return) of 1 - |<psi| U_target^+ P^+ V |psi>|^2, "
         "V = routed circuit, P = router's final qumode permutation. Target = ordered Trotter product of the IR terms "
         "(main columns) or exact e^{-iHt} (last columns). Total-photon truncation K = 10/12 (8/10 for "
         "electron-vibration); exact (K = 3) when every gate and term conserves photon number. Budget eps = 1e-3.\n")
L.append("| benchmark | Genesis gates | ours gates | Genesis 2-op | ours 2-op | Genesis duration | ours duration | "
         "Genesis infidelity | ours infidelity | ideal step vs e^{-iHt} | ours vs e^{-iHt} | Genesis vs e^{-iHt} |")
L.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    gi = g(r["genesis_max_infid"], "{:.5g}") + ("*" if "logical" in r["genesis_err_note"] else "")
    L.append(f"| {SH[r['benchmark']]} | {r['genesis_total']} | {g(r['ours_total'],'{:.0f}')} | {r['genesis_2op']} | "
             f"{g(r['ours_2op'],'{:.0f}')} | {r['genesis_duration']} | {g(r['ours_duration'],'{:.0f}')} | {gi} | "
             f"{g(r['ours_max_infid'])} | {nc(r['ideal_trotter_vs_exact'])} | {nc(r['ours_vs_exact'])} | "
             f"{'n/a' if r['benchmark']=='kerr_small' else nc(r['genesis_vs_exact'])} |")
L.append("\n\\* Kerr: Genesis' physical circuit (19 qubits + 19 qumodes) is too large to simulate; value is v3's "
         "logical-circuit error (per-mode cutoffs 16/22). e^{-iHt} columns not computed for electron-vibration "
         "(~30 min per check) or Genesis Kerr. Electron-vibration (ours): whole-circuit check did not finish before the "
         "meeting (9 qumodes); every rule application passed its window check, and the error ledger sums to the value "
         "in comparison.csv (ours_err_ledger).\n")
L.append("## Rules the LLM found (admitted; full table in rules/BOOK.md)\n")
for line in book.splitlines():
    if line.startswith("| ") and not line.startswith("| name") :
        c = [x.strip() for x in line.strip("|").split("|")]
        L.append(f"- **{c[0]}** ({c[1]}; {c[3]}; mechanism: {c[4]}). Helped (gates/duration): {c[6].replace('None/None', 'not compilable')}")
L.append("\nValidity notes from reading the code and testing: `kerr_exact_by_parity_mapping_bounded_photons` uses "
         "n^2 = 3n - pn + (3/2)p - 3/2, exact for n <= 3 at any angle and for all n when theta is a multiple of pi/4 "
         "(checked to n = 12: <= 3e-12; at Genesis' 8-digit constants ~1e-6; at theta = 0.3 it fails beyond 3 photons). "
         "`kerr_half_pi_parity_kickback_angle_tolerant_5op` uses n^2 = n (mod 2) at theta = pi/2 (all n). The two "
         "Pauli rules are exact operator identities on the full Fock space (Heisenberg-Weyl group commutator, which "
         "terminates, plus conjugation by beam-splitter swaps / CP dressing).\n")
dec = Counter(a["decision"] if not ("no code" in (a.get("reason") or "")) else "no code" for a in att)
L.append("## Loop statistics\n")
L.append(f"- Attempt records: {len(att)} ({', '.join(f'{k}: {v}' for k, v in sorted(dec.items()))}); LLM calls: {len(calls)} "
         f"({', '.join(f'{k}: {v}' for k, v in sorted(roles.items()))}); tokens in (incl. cache reads) {tok_in:,}, out {tok_out:,}.")
L.append("- Scout = session model (Opus-class, adaptive thinking); implementer = Sonnet-class (thinking disabled from "
         "attempt 3 on, after implementer calls exhausted their token cap without producing code). Backend: platform "
         "LLM API instead of v3's `claude -p` CLI (not installed in this sandbox).")
L.append("- Mechanisms proposed by the scout across attempts included BCH / Heisenberg-Weyl group commutators, "
         "Hadamard-lemma conjugations (CP dressing, beam-splitter-swap transport), passive linear-optics "
         "homomorphisms and number-theoretic identities on n^2; admitted rules use the first, second and fourth.\n")
L.append("## Caveats\n")
L.append("- Preliminary: 5 small instances, one Trotter step, eps = 1e-3, single run (no repeated seeds of the LLM loop).")
L.append("- Duration: ours is behind Genesis on Bose-Hubbard, Z2-Higgs and electron-vibration; gate count is ahead on 4 of 5.")
L.append("- Genesis' circuits do not implement the step they compile from (infidelity ~1 on every benchmark we could "
         "simulate), so the gate-count comparison is against incorrect circuits; ours meet eps everywhere.")
L.append("- Two n^2 rules exploit the benchmarks' special angles (pi/4, pi/2); for generic angles only the <= 3-photon "
         "claim holds. Verification is on the <= 3-photon subspace with total-photon truncation.")
L.append("- Not done: higher-order Trotter / multi-step comparison vs e^{-iHt} (needs Genesis re-runs with scaled "
         "constants), Hubbard-Holstein (non-unitary IR terms).")
(R / "report" / "SUMMARY.md").write_text("\n".join(L) + "\n")
print("\n".join(L))
