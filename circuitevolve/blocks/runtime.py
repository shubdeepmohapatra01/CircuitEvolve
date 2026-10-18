"""In-process serial stand-in for the BQSKit runtime (copied from experiments/bqskit_baselines/serial_runtime.py).

`bqskit.compiler.Compiler` starts an attached server that binds a localhost TCP
socket; the sandbox forbids that (PermissionError on bind). BQSKit passes only
reach the runtime through `bqskit.runtime.get_runtime()`, which returns the
module-global `bqskit.runtime.worker._worker`. A grep of bqskit 1.2.1 + bqskit-ft
shows pass code calling only `map`, `submit` and `get_cache`; we install an object
implementing those (plus defensive `next`/`cancel` stubs that no pass we run calls)
that executes everything serially in this process. Semantics are identical to a
1-worker runtime except for scheduling order (irrelevant: map results are
returned positionally).
"""
from __future__ import annotations

import asyncio
import inspect
from typing import Any

import bqskit.runtime.worker as _bw
from bqskit.compiler.passdata import PassData
from bqskit.compiler.workflow import Workflow
from bqskit.ir.circuit import Circuit


class SerialRuntime:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    async def _call(self, fn, *a, **kw):
        r = fn(*a, **kw)
        if inspect.isawaitable(r):
            r = await r
        return r

    def map(self, fn, *args, task_name=None, log_context=None, **kwargs):
        async def _run():
            return [await self._call(fn, *a, **kwargs) for a in zip(*args)]
        return _run()

    def submit(self, fn, *args, task_name=None, log_context=None, **kwargs):
        return self._call(fn, *args, **kwargs)

    async def next(self, future):  # pragma: no cover - not used by our passes
        r = await future
        return [(i, x) for i, x in enumerate(r)] if isinstance(r, list) else [(0, r)]

    def cancel(self, future) -> None:  # pragma: no cover
        try:
            future.close()
        except Exception:
            pass

    def get_cache(self) -> dict[str, Any]:
        return self._cache


def install() -> SerialRuntime:
    rt = SerialRuntime()
    _bw._worker = rt  # type: ignore[assignment]
    return rt


def run_passes(circuit: Circuit, passes, model=None, seed: int | None = None) -> tuple[Circuit, PassData]:
    """Run a list of passes / Workflow on `circuit` in-process. Returns (circuit, data)."""
    install()
    data = PassData(circuit)
    if model is not None:
        data.model = model
    if seed is not None:
        data['seed'] = seed
    wf = passes if isinstance(passes, Workflow) else Workflow(passes)
    _run_coro(wf.run(circuit, data))
    return circuit, data


def _run_coro(coro) -> None:
    """asyncio.run, but also usable where an event loop is already running (Jupyter/IPython kernels).

    asyncio.run refuses to start inside a running loop, so in that case the coroutine runs to completion on a
    short-lived worker thread with its own loop. The call still blocks the caller; exceptions are re-raised.
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return
    import threading
    box: dict = {}

    def target():
        try:
            asyncio.run(coro)
        except BaseException as e:  # re-raised in the caller's thread
            box["err"] = e

    t = threading.Thread(target=target, name="bqskit-passes")
    t.start()
    t.join()
    if "err" in box:
        raise box["err"]
