"""Execute a notebook top to bottom IN-PROCESS (IPython InteractiveShell) and store outputs in the .ipynb.

Used because this sandbox forbids binding any socket (TCP or unix/ipc), so no Jupyter kernel can start.
Semantics match a fresh ipykernel run: one namespace, cells in order, cwd = notebook directory, stop on error, and
every cell runs via `await shell.run_cell_async(...)` INSIDE a running asyncio event loop, as ipykernel does (so code
that calls asyncio.run() from a cell fails here exactly as it would in Jupyter).

    .venv/bin/python notebooks/demo_assets/run_inprocess.py notebooks/group_meeting_demo.ipynb
"""
import asyncio
import os
import sys
import time

import nbformat
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

path = os.path.abspath(sys.argv[1])
nb = nbformat.read(path, as_version=4)
os.chdir(os.path.dirname(path))
shell = InteractiveShell.instance()
t0 = time.time()


async def run_all() -> int:
    n = 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        n += 1
        with capture_output(stdout=True, stderr=True, display=True) as cap:
            res = await shell.run_cell_async(cell.source, store_history=True,
                                             transformed_cell=shell.transform_cell(cell.source))
        outs = []
        if cap.stdout:
            outs.append(nbformat.v4.new_output("stream", name="stdout", text=cap.stdout))
        if cap.stderr:
            outs.append(nbformat.v4.new_output("stream", name="stderr", text=cap.stderr))
        for o in cap.outputs:
            outs.append(nbformat.v4.new_output("display_data", data=o.data, metadata=o.metadata or {}))
        if res.result is not None:
            fmt, md = shell.display_formatter.format(res.result)
            outs.append(nbformat.v4.new_output("execute_result", data=fmt, metadata=md, execution_count=n))
        cell.outputs, cell.execution_count = outs, n
        if not res.success:
            err = res.error_in_exec or res.error_before_exec
            cell.outputs.append(nbformat.v4.new_output("error", ename=type(err).__name__, evalue=str(err), traceback=[]))
            nbformat.write(nb, path)
            print(f"FAILED in code cell {n}: {type(err).__name__}: {err}\n{cap.stdout[-2000:]}")
            sys.exit(1)
    return n


n = asyncio.run(run_all())
nb.metadata.setdefault("execution", {})["note"] = ("executed in-process (IPython InteractiveShell.run_cell_async inside a "
                                                   "running asyncio loop, as ipykernel); sandbox forbids kernel sockets")
nbformat.write(nb, path)
print(f"executed {n} code cells in {time.time() - t0:.1f} s")
