# CircuitEvolve

Verifier-first harness for LLM-assisted discovery of fault-tolerant circuit constructions.
Standing rules and current experiment: [CLAUDE.md](CLAUDE.md). Plan: [docs/TEST_PLAN.md](docs/TEST_PLAN.md).

```
python -m venv --system-site-packages .venv && .venv/bin/pip install -e .[dev]
.venv/bin/python -m pytest -q                       # unit tests + verifier acceptance suite
.venv/bin/python experiments/acceptance.py          # -> results/acceptance.md
.venv/bin/python experiments/baselines.py           # -> results/baselines.csv
.venv/bin/python experiments/search_classical.py    # -> results/classical_search.csv
```

Status: P0 (IR, exact simulators), P1 (verifier, 21/21 acceptance), P2 (baselines 14n / 8n / 4n),
P3 (classical search, GO — see results/P3_go_no_go.md) done. Next: P4 LLM proposer.
