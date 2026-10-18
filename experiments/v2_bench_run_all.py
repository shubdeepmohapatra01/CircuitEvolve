"""Run experiments/v2_bench_baselines.py for every new benchmark circuit, one fresh interpreter per circuit
(subprocess, no numpy in this driver), `--jobs` in parallel, smallest circuits first.

    .venv/bin/python experiments/v2_bench_run_all.py results/v2/bench_runs/<tag> [--jobs 6] [--timeout 3600]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "benchmarks", "nam_arith"))
from fetch_suite import NAMES  # noqa: E402
from normalize import CUCCARO_N  # noqa: E402


def size(name):
    p = os.path.join(ROOT, "benchmarks", "nam_arith",
                     "generated" if name.startswith("cuccaro_") else "cliffordt", name + ".qasm")
    return os.path.getsize(p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    names = a.only or (list(NAMES) + [f"cuccaro_{n}" for n in CUCCARO_N])
    names.sort(key=size)
    os.makedirs(a.out, exist_ok=True)
    log = open(os.path.join(a.out, "run_all.log"), "a")
    todo, running = list(names), {}
    while todo or running:
        while todo and len(running) < a.jobs:
            nm = todo.pop(0)
            err = open(os.path.join(a.out, nm + ".stderr"), "w")
            running[nm] = (subprocess.Popen([sys.executable, os.path.join(HERE, "v2_bench_baselines.py"), nm, a.out],
                                            stdout=err, stderr=err, cwd=ROOT), time.time(), err)
            log.write(f"{time.strftime('%H:%M:%S')} start {nm} pid={running[nm][0].pid}\n")
            log.flush()
        time.sleep(1)
        for nm, (p, t0, err) in list(running.items()):
            rc = p.poll()
            if rc is None and time.time() - t0 > a.timeout:
                p.kill()
                rc = "timeout"
            if rc is not None:
                err.close()
                line = f"{time.strftime('%H:%M:%S')} {nm} rc={rc} {time.time() - t0:.1f}s"
                print(line, flush=True)
                log.write(line + "\n")
                log.flush()
                del running[nm]


if __name__ == "__main__":
    main()
