# smoke_heisenberg_6_e3 — notes (2026-10-13, added after the run; run files unchanged)

Live smoke of the window core: heisenberg_6, total eps = 1e-3, input
`results/bqskit_baselines/stage1/inputs/heisenberg_6_tket.qasm` (Baselines track TKET FullPeepholeOptimise),
backend make_api_backend(host.llm, reasoning model, thinking disabled, max_tokens 3000), 20 proposal calls in
batches of 4, playbook playbooks/window_v0.json (empty at start), reflect_every 8.

| quantity | value |
|---|---|
| T before (v0 ledger: eps_rz = (eps/2)/150 = 3.33e-6) | 8600 |
| T after | 8600 (nothing accepted) |
| T with unspent window budget returned to synthesis (eps_rz = eps/150) | 8200 — equals B0 (results/bqskit_baselines/stage1/runs/heisenberg_6_B0_e3.json: t_count 8200) |
| rotations / CNOT | 150 / 274 before and after |
| LLM calls / tokens | 20 / 23,654 in + 11,416 out |
| candidates parsed / rejected by verifier | 3 / 3 (operator distance 2.4e-2, 2.4e-2, 1.0 vs allowance 1.25e-4) |
| reflector calls | 0 (both reflection points skipped: no verifier outcome since the previous one) |
| wall time | 47.7 s |

Correction to the summary's `parse_errors: 19`: re-reading the logged responses with
`circuitevolve.core.mutator.is_declined` (added after this run), 19 of the 20 responses are the prompt's
legal "NONE" answer (18 as plain text, 1 inside a window block), not malformed output. Since this run the
loop counts them as `declined`.

Reading of the responses: the model correctly found no exact merge inside the windows (the Trotter ZZ terms
appear as cx–rz(0.04 / 0.02)–cx sandwiches on different wire pairs) and noted that every snap exceeds the allowance (it estimated ~5e-3; measured over all 150 rotations the
smallest snap distance 2|sin(Δ/4)| is 1.0e-2, i.e. 80× the allowance). The one window it changed (call 17)
snapped three rotations (Δ = 0.02 rad each), explicitly overriding the allowance after reading the "snap distance" column as
an invitation; the verifier rejected all three candidates. The prompt column was relabelled afterwards
("usable only if <= allowance").

Structural conclusion for this circuit at eps = 1e-3: the WHOLE window pool (5e-4) cannot pay for even one
snap of a heisenberg_6 rotation (each ≥ 1.0e-2; only two snap distances occur, 1e-2 and 2e-2), so approximate window rewrites cannot help here; gains can
only come from exact restructuring across window boundaries.
