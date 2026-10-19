# dv.windows (angle) 3-arm campaign — operational runbook

SELF-CONTAINED: written for a supervising agent with NO prior context. The scientific contract
is docs/P2_CAMPAIGN.md and is FROZEN — this file only records how to run it without rediscovering
operational details. Read CLAUDE.md first, then P2_CAMPAIGN.md, then this.

## What is already decided (do not re-litigate)
- Contract: 3 arms (A seeded playbook | B placebo | C none), >= 40 proposer calls/circuit/arm.
  DEV (learning): qft_8, heisenberg_6, hubbard_8, qml_13, hhl_8 @ 1e-3.
  HELD-OUT (frozen, reflector off, sha recorded): qpe_8, qae_13, tfim_6 @ 1e-3 + secondary @ 1e-5.
  Bars: B0 (TKET+gridsynth floor) + per-circuit best of {B1 pyzx, B2, B3g}; external reference =
  committed BQSKit-FT DPF stage-1 numbers (results/bqskit_baselines/stage1/).
- Model pins (user-approved 2026-10-19, recorded in results/CHANGELOG.md): proposer
  claude-opus-5, reflector claude-sonnet-5-5, BOTH with thinking={"type": "adaptive"} and
  max_tokens 16000 via circuitevolve.llm_backends.make_api_backend(thinking=<dict>).
  (5-5 generation models REJECT thinking=disabled; opus-5 accepts either.)
- Stop condition: the contract's half-budget futility stop applies per arm.

## Operational facts (hard-won; respect them)
1. Kernel: environment "circuitevolve-dev" (registered repo venv; has pytket/pyzx + host.llm).
   FIRST cell before ANY circuitevolve/pytket import, or the kernel dies irrecoverably:
       import os, pathlib; cfg = pathlib.Path.cwd()/".config"; cfg.mkdir(exist_ok=True)
       os.environ["XDG_CONFIG_HOME"] = str(cfg)
2. Per-conversation host.llm ceiling is 2.0M tokens (~200 calls). A full campaign MUST be run
   as a CHAIN of delegated sub-sessions (each has its own ceiling), SEQUENTIAL ONLY — the
   mutable playbook has exactly one writer. ~150 calls per sub-session is a safe chunk.
3. Budget-ceiling signature = every call errors INSTANTLY (0s). Stop the chunk, report the
   remaining list, resume in the next sub-session (drivers must be resumable via append-only
   JSONL, skip-done — copy the pattern in experiments/engine_recon_campaign.py run_sweep).
4. Tagged cascade/loop runs: one log per stage/tag, append-only — a reused tag REFUSES. Give
   reruns a fresh phase suffix (see run_circuit(phase=...) precedent).
5. Arm B (placebo) and arm C (none) semantics are defined in P2_CAMPAIGN.md — playbook files
   must be loaded frozen for B and C; only arm A's playbook mutates, and only on DEV.
6. Children do NOT git commit; the supervisor commits per phase with CHANGELOG entries, full
   suite green (376+2 as of bed24b6) and frozen digests unchanged (bc3eac23..., cvdv OK).
7. Progress: have each run print the newline-per-call ASCII bar (Progress class in
   engine_recon_campaign.py) so logs are peekable mid-run.

## Not yet built (first task of the campaign chat)
experiments/engine_angle_campaign.py — the 3-arm driver (mirror engine_recon_campaign.py:
run_circuit with arm/eps/frozen params, per-arm playbook handling, resumable JSONL, report
assembly per the contract's five columns).
