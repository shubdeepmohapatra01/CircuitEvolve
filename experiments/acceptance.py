"""Write results/acceptance.md: verifier acceptance report (P1 gate)."""
import datetime, pathlib, time

from circuitevolve.acceptance import cases
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify

rows, n_ok = [], 0
for c in cases():
    t = time.time()
    r = verify(c.construct, AdderSpec(), c.n_values, c.vocab)
    ok = r.ok == c.expect_ok and r.level == c.expect_level
    n_ok += ok
    rows.append(f"| {c.name} | {c.what} | {'accept' if c.expect_ok else 'reject @ ' + c.expect_level} | "
                f"{'accept' if r.ok else 'reject @ ' + r.level + f' (n={r.n})'} | {'yes' if ok else '**NO**'} | {time.time() - t:.1f} |")
out = pathlib.Path(__file__).resolve().parents[1] / "results" / "acceptance.md"
out.write_text(
    f"# Verifier acceptance report\n\nGenerated {datetime.datetime.now():%Y-%m-%d %H:%M}. "
    f"Correct: **{n_ok}/{len(rows)}** (gate: all).\n\n"
    "| case | planted behaviour | expected | verifier | correct | s |\n|---|---|---|---|---|---|\n"
    + "\n".join(rows) + "\n")
print(f"{n_ok}/{len(rows)} -> {out}")
