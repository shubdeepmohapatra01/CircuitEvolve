"""Execute a notebook without a Jupyter kernel (for sandboxes where kernels cannot open sockets).

Runs code cells in one shared namespace, capturing stdout/stderr, `display(...)` calls (DataFrames as
HTML + text) and matplotlib figures (`plt.show()` -> PNG), and stores them as regular notebook
outputs with execution counts.  On a normal machine, `jupyter nbconvert --execute` gives the same result.

    python run_notebook.py demo_cvdv_rulebook.ipynb
"""
import base64
import contextlib
import io
import sys
import traceback

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import nbformat as nbf  # noqa: E402


def main(path):
    nb = nbf.read(path, as_version=4)
    outputs = []

    def display(*objs):
        for o in objs:
            if hasattr(o, "to_html"):
                outputs.append(nbf.v4.new_output("display_data", data={
                    "text/html": o.to_html(max_rows=40), "text/plain": o.to_string(max_rows=40)}))
            else:
                outputs.append(nbf.v4.new_output("display_data", data={"text/plain": repr(o)}))

    def show(*a, **k):
        for num in plt.get_fignums():
            fig = plt.figure(num)
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
            outputs.append(nbf.v4.new_output("display_data", data={
                "image/png": base64.b64encode(buf.getvalue()).decode(), "text/plain": "<Figure>"}))
        plt.close("all")

    plt.show = show
    ns = {"display": display, "__name__": "__main__"}
    count = 0
    for cell in nb.cells:
        if cell.cell_type != "code":
            continue
        count += 1
        outputs.clear()
        out, err = io.StringIO(), io.StringIO()
        ok = True
        import time as _t
        t0 = _t.time()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                exec(compile(cell.source, f"<cell {count}>", "exec"), ns)
            except Exception:  # noqa: BLE001
                ok = False
                tb = traceback.format_exc()
        if plt.get_fignums():
            show()
        cell_out = []
        if out.getvalue():
            cell_out.append(nbf.v4.new_output("stream", name="stdout", text=out.getvalue()))
        cell_out.extend(outputs)
        if not ok:
            cell_out.append(nbf.v4.new_output("error", ename="Error", evalue="see traceback",
                                              traceback=tb.splitlines()))
        cell.outputs = cell_out
        cell.execution_count = count
        print(f"cell {count}: {'ok' if ok else 'ERROR'} {_t.time() - t0:.1f}s", file=sys.__stdout__, flush=True)
        if not ok:
            print(tb, file=sys.__stdout__)
    nbf.write(nb, path)


if __name__ == "__main__":
    main(sys.argv[1])
