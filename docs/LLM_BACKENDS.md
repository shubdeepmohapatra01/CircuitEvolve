# LLM backends for the proposer

> **2026-10-13.** The backend factories moved verbatim to `circuitevolve/llm_backends.py` (re-exported by
> `circuitevolve.search.llm`, now an alias of `circuitevolve.legacy.adder.llm`). The window core uses
> `make_api_backend(host.llm, model=host.reasoning_model())` via `experiments/window_run.py`.

`circuitevolve/search/llm.py` takes any callable `complete(list[str]) -> list[str | Exception]`.
Two factories are provided. Both return a callable with a `stats` Counter; `llm_search` stores the
change in that counter over a run as `stats["backend"]` in the run summary.

| Backend | Where it works | Factory |
|---|---|---|
| In-platform API | a Claude Science python kernel (`host` exists only there) | `make_api_backend(host.llm, model=host.reasoning_model())` |
| `claude -p` CLI | a terminal where `claude` is logged in | `make_cli_backend(...)` / `experiments/search_llm.py` |

## In-platform API backend

```python
from circuitevolve.search.llm import make_api_backend, make_batch_merger
from experiments.search_llm import run
be = make_api_backend(host.llm, model=host.reasoning_model(), max_tokens=8000, max_concurrency=4)
run("cuccaro_B", backend=be, backend_tag="api", calls=60, repair=300, seed=0)
```

* **Thinking is disabled** (`{"type": "disabled"}`) by default. With the server default (thinking on) the
  model twice spent its whole `max_tokens` budget thinking and returned empty text.
* Error dicts, exceptions raised by `llm`, and empty/whitespace text are all returned as `RuntimeError`
  (the loop counts them as `llm_error`); a response is never silently treated as "no proposals".
* Transient failures (connection errors, overload/429/5xx, timeouts, empty text) are re-issued up to
  `retries` times (default 3) with exponential backoff `backoff * 2**attempt` s (default 5 s). Fatal
  ones (token ceiling, invalid request, auth, usage limit) are not retried. Counted as `retries`,
  `error`, `empty`, `failed`, `truncated` (stop_reason = max_tokens), `input_tokens`, `output_tokens`.
* `make_batch_merger(host.llm, window=2.0, max_concurrency=12)` lets several search threads (e.g. three
  seeds) share host round-trips: concurrent requests are merged into one batch call. Give each run its
  own `make_api_backend(merger, ...)` so its stats stay separate.
* The module never imports `host`; the callable is injected.

## CLI backend (`claude -p`)

Each call runs `claude -p --output-format json [--model M] [extra args]` with the prompt on stdin, in an
empty temporary directory (so the agent cannot read this repository, which contains the reference
answer). A call succeeds only if the exit code is 0 and the JSON envelope has `is_error: false`,
`subtype: "success"` and a non-empty `result`.

Options (all exposed in `experiments/search_llm.py`): `--cli-timeout` (default 300 s),
`--cli-retries` (transient failures only, default 1), `--cli-retry-timeouts`, `--cli-workers`
(concurrent processes, default = batch), `--cli-max-turns N` (passes `--max-turns N`), `--cli-arg X`
(any extra flag, repeatable).

Diagnostics: on exit != 0 the error message now contains the elapsed time, the JSON envelope's
`subtype`/`is_error`/`result` head if stdout is JSON, otherwise the first 300 characters of stdout, and
the stderr head. (The previous version reported only stderr, which was empty in every failure.)

### What happened in `cuccaro_B_evo_repair300_120_cli` (119/120 calls failed)

The order of outcomes in `results/llm_runs/cuccaro_B_evo_repair300_120_cli.jsonl` is
`T T o` followed by 41 more `T`, then 76 `E` (T = timeout at 300 s, o = success, E = exit 1 with empty
stderr). The failures are not interleaved: the run first timed out on every call for ~43 calls, then
failed immediately on every remaining call. Likely causes, most likely first (not verified - the CLI
cannot be run from this platform):

1. **Exit 1 = account/session limit reached.** With `--output-format json`, the CLI reports errors in
   the JSON envelope on *stdout* (e.g. a usage-limit or rate-limit message), not on stderr, which is why
   stderr was empty. A wall of instant exit-1 failures after a long stretch of heavy use is the pattern
   of a usage limit. The new diagnostics will show the message.
2. **Timeouts = agentic sessions, not single completions.** `claude -p` is an agent: it can think at
   length and try tools (e.g. try to run Python to check a construction in the empty directory), using
   several turns. The one successful call returned a long, carefully reasoned answer. Four concurrent
   sessions of this kind can each exceed 300 s, and they consume the usage allowance quickly - which
   would also explain cause 1 following.
3. Concurrency of 4 CLI processes sharing one login can trigger rate limiting.

### How to test the CLI in your terminal

```bash
echo hi | claude -p --output-format json                  # must print {"type":"result","subtype":"success",...}
echo $?                                                   # 0
echo hi | claude -p --output-format json --max-turns 1 --tools ""     # text-only, one turn
claude auth status                                        # exit 0 if logged in (if your version has it)
# one real proposer prompt, timed, outside the repository:
cd "$(mktemp -d)" && .../.venv/bin/python -c "
from circuitevolve.search.llm import build_prompt; from circuitevolve.search.slice import CUCCARO
print(build_prompt(CUCCARO, (14.0, 112, 17, 1, 1), [], [], False, 'B', 4))" > p.txt
time claude -p --output-format json --max-turns 1 --tools "" < p.txt | head -c 600
```

(`--tools ""` removes the built-in tools in recent CLI versions; if yours rejects it, use
`--disallowedTools` or drop it. `--bare`, where available, skips CLAUDE.md/hooks/MCP discovery and
speeds start-up.)

### Recommended CLI settings for long runs

```bash
.venv/bin/python experiments/search_llm.py --row cuccaro_B --calls 60 --repair 300 \
    --cli-max-turns 1 --cli-arg=--tools --cli-arg="" --cli-timeout 600 --cli-workers 2 --cli-retries 2
```

and check the first batch's `.jsonl` lines for `error` before leaving it running. If every call fails
with a usage-limit message, wait for the limit to reset or use the in-platform backend.
