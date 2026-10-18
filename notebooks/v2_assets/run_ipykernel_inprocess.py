"""Execute a notebook top to bottom in an IPython kernel (ipykernel InProcessKernel) and store outputs in place,
then write an HTML export next to this script.

The sandbox forbids binding any socket (TCP and ipc), so neither nbclient nor `jupyter nbconvert --execute` can
start a kernel subprocess. ipykernel's InProcessKernel is the same IPythonKernel / InteractiveShell stack driven
through the Jupyter messaging protocol without sockets: every cell is sent as an execute_request, runs inside the
kernel's running asyncio event loop, and its iopub messages (stream, display_data, execute_result, error) are
converted to notebook outputs with nbformat.v4.output_from_msg, exactly as nbclient does. Stops at the first error.

    .venv/bin/python notebooks/v2_assets/run_ipykernel_inprocess.py notebooks/v2_group_meeting.ipynb
"""
import os
import queue
import sys
import time

import nbformat
from ipykernel.inprocess.manager import InProcessKernelManager
from nbconvert import HTMLExporter

path = os.path.abspath(sys.argv[1])
html_out = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        os.path.splitext(os.path.basename(path))[0] + ".html")
nb = nbformat.read(path, as_version=4)
os.chdir(os.path.dirname(path))                     # cwd = notebook directory, as Jupyter does

km = InProcessKernelManager()
km.start_kernel()
kc = km.client()
kc.start_channels()
t0 = time.time()


def run_cell(src):
    msg_id = kc.execute(src, store_history=True)
    reply = kc.get_shell_msg(timeout=900)
    km.kernel.stdout.flush()                           # trailing prints are buffered in the kernel's OutStream
    km.kernel.stderr.flush()
    outs, n = [], None
    while True:                                        # drain everything this request produced (incl. late streams)
        try:
            m = kc.get_iopub_msg(timeout=0.5)
        except queue.Empty:
            break
        # cells run strictly one at a time, so everything on iopub now belongs to this request; the in-process
        # OutStream does not stamp stream messages with the request's parent header, so do not filter on it
        t = m["msg_type"]
        if t == "execute_input":
            n = m["content"]["execution_count"]
        elif t in ("stream", "display_data", "execute_result", "error"):
            o = nbformat.v4.output_from_msg(m)
            if t == "stream" and outs and outs[-1].output_type == "stream" and outs[-1].name == o.name:
                outs[-1].text += o.text                # merge consecutive stream chunks
            else:
                outs.append(o)
        elif t == "clear_output":
            outs = []
    return reply["content"], outs, n


n_code, timings = 0, []
for i, cell in enumerate(nb.cells):
    if cell.cell_type != "code":
        continue
    n_code += 1
    t1 = time.time()
    content, outs, n = run_cell(cell.source)
    cell.outputs, cell.execution_count = outs, n
    timings.append(round(time.time() - t1, 2))
    if content["status"] != "ok":
        nbformat.write(nb, path)
        print(f"FAILED in code cell {n_code} (notebook cell {i}): {content.get('ename')}: {content.get('evalue')}")
        print("\n".join(content.get("traceback", []))[-3000:])
        sys.exit(1)

runtime = time.time() - t0
kc.stop_channels()
km.shutdown_kernel()
nb.metadata.setdefault("execution", {})["note"] = (
    "executed top to bottom in ipykernel InProcessKernel (IPythonKernel + Jupyter messaging, cells run inside the "
    "kernel's running asyncio loop); sandbox forbids kernel sockets, so nbclient could not spawn a kernel")
nb.metadata["execution"]["runtime_s"] = round(runtime, 1)
nb.metadata["execution"]["code_cells"] = n_code
nbformat.validate(nb)
nbformat.write(nb, path)
body, _ = HTMLExporter().from_notebook_node(nb)
with open(html_out, "w", encoding="utf-8") as f:
    f.write(body)
print(f"executed {n_code} code cells in {runtime:.1f} s; per-cell s: {timings}; html: {html_out}")
