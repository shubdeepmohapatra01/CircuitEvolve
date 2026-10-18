"""P1.3 gates: the CV-DV certified compiler behind the generic engine loop.

(a) a scripted fake-LLM run whose single response is the source of rule_n2__parity_exact
    (copied verbatim from cvdv/rulebook/rules.py): the frozen certifier verifies it, the loop
    ACCEPTS it, and the measured improvement matches the known numbers — the group-commutator
    best is replaced by a 3 two-op / 6 one-op implementation per n2 term.
(b) reproduction: compiling boseHubbard_small through the wrapped stack (the plugin's measure
    path) + Genesis routing under PYTHONHASHSEED=0 equals the 'ours' hashseed-0 row of
    cvdv/results/compare_isas_small_nmax3.csv.

These tests run in the cvdv acceptance env (cvdv-opt); qutip is that env's marker dependency,
so the lean repo venv skips them (importorskip) and they are run explicitly with
    conda run -n cvdv-opt python -m pytest tests/engine/test_cvdv_plugin.py -q
Deterministic: scripted responses only, no network, no real LLM.
"""
from __future__ import annotations

import csv
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("qutip", reason="cvdv stack runs in the cvdv-opt env (qutip marks it)")
plugin_mod = pytest.importorskip("circuitevolve.domains.cvdv.plugin")

from circuitevolve.core.ledger import Ledger          # noqa: E402
from circuitevolve.engine import EvolveLoop           # noqa: E402

REPO = Path(__file__).resolve().parents[2]
CVDV = REPO / "cvdv"


def _rule_source(name: str) -> str:
    """Copy one rule function verbatim out of cvdv/rulebook/rules.py."""
    out, keep = [], False
    for line in (CVDV / "rulebook" / "rules.py").read_text().splitlines():
        if line.startswith("def "):
            keep = line.startswith(f"def {name}(")
        elif line and line[0] not in " \t#":
            keep = False
        if keep:
            out.append(line)
    assert out, f"{name} not found in rulebook"
    return "\n".join(out).rstrip() + "\n"


def _n2_term(theta: float, mode: int):
    """Synthetic Trotter term exp(-i theta n^2) on one qumode (exponent = -i theta n n)."""
    from cvdv import target as TG

    expr = TG.parse_sexpr(f"prod(({-theta}j), dagger(b({mode})), b({mode}), "
                          f"dagger(b({mode})), b({mode}))")
    return TG.Term(wires=(("qm", mode),), expr=expr, pauli=None)


def _synthetic_plugin(**kw):
    terms = [_n2_term(0.05, 0), _n2_term(-0.05, 1)]
    seed_src = (CVDV / "libraries" / "seed.py").read_text()
    return plugin_mod.CvdvRulesPlugin(
        terms, seed_src, eps_total=0.05, n_max=3, r_max=512,
        meta=dict(name="synthetic_n2_pair", source="unit"), **kw)


# ---------------------------------------------------------------------------- gate (a)
def test_engine_accepts_parity_exact(tmp_path):
    pl = _synthetic_plugin()
    parity = _rule_source("rule_n2__parity_exact")
    reply = "Derivation: parity trick, see rulebook provenance.\n```python\n" + parity + "```\n"
    loop = EvolveLoop(pl, 0.05, lambda prompts: [reply for _ in prompts], Ledger(0.05),
                      n_calls=1, batch=1, seed=0, tag="cvdv_parity", runs_dir=tmp_path)
    s = loop.run()
    st = s["stats"]

    # the frozen certifier verified it (exact) and the loop accepted it
    assert st["verified"] == 1 and st["accepted"] == 1 and st["exact_accepts"] == 1
    assert st["rejected_verifier"] == 0 and st["parse_errors"] == 0
    assert s["ledger"]["window_spent"] == 0.0            # exact rules charge 0
    assert s["verifier_digest"] == pl.frozen_digest()[:16]
    assert s["final_check_vs_original"]["ok"] is True

    # before: the group-commutator rule was the best for every n2 part
    before = pl.measure(pl.start_state())
    assert [p["rule"] for p in before["report"]["parts"]] == ["group_commutator"] * 2
    assert s["t_before"] == before["cost"]["duration"]

    # after: every n2 part is the accepted parity rule at 3 two-op / 6 one-op (known numbers)
    best = loop.archive[0]
    after = pl.measure(best.state)
    n2 = [p for p in after["parts_metrics"] if p["kind"] == "n2"]
    assert len(n2) == 2
    assert all(p["rule"] == "parity_exact" for p in n2)
    assert [(p["two_op"], p["one_op"]) for p in n2] == [(3, 6), (3, 6)]
    assert (s["t_after"], s["after"]["two_op"], s["after"]["one_op"]) == (65, 6, 12)
    assert s["t_after"] < s["t_before"]
    assert after["cost"]["eps_bound"] <= 1e-9            # certified exact on n <= n_max

    # run artifacts: library with the appended rule + certified compile report
    rules_out = (tmp_path / "cvdv_parity_rules.py").read_text()
    assert "def rule_n2__parity_exact(t, g, r):" in rules_out


def test_parse_is_regex_only(monkeypatch):
    import builtins

    pl = _synthetic_plugin()

    def boom(*a, **k):  # pragma: no cover - must never run
        raise AssertionError("exec/eval reached from parse()")

    monkeypatch.setattr(builtins, "exec", boom)
    monkeypatch.setattr(builtins, "eval", boom)
    code = "def rule_n2__x(t, g, r):\n    g.R(1.0, t.m[0])"
    props, perr, declined = pl.parse(f"thinking...\n```python\n{code}\n```\n")
    assert props == [("rule", code + "\n")] and perr == [] and not declined
    assert pl.parse("NONE") == ([], [], True)
    assert pl.parse("no code here")[1] == ["no ```python code block"]


# ---------------------------------------------------------------------------- gate (b)
_REPRO_SCRIPT = """
import json
from circuitevolve.domains.cvdv import benchmark_plugin
from cvdv import metrics as M, route as RT

pl = benchmark_plugin("boseHubbard_small", eps_total=1e-3, n_max=3)
mm = pl.measure(pl.start_state())
assert mm["cost"]["valid"] == 0, mm["cost"]
phys, info = RT.route(mm["ops"])
m = M.metrics(phys)
print("RESULT " + json.dumps(dict(m, eps_bound=mm["report"]["eps_bound"])))
"""


def test_boseHubbard_small_reproduces_compare_isas_row():
    if not (CVDV / "third_party" / "genesis" / "src").exists():
        pytest.skip("Genesis checkout missing (cvdv/scripts/fetch_genesis.sh)")
    rows = [r for r in csv.DictReader(open(CVDV / "results" / "compare_isas_small_nmax3.csv"))
            if r["benchmark"] == "boseHubbard_small" and r["compiler"] == "ours"
            and r["isa"] == "phase-space + BS" and r["hashseed"] == "0"]
    assert len(rows) == 1, "expected exactly one 'ours' PS+BS hashseed-0 row"
    exp = rows[0]

    env = dict(os.environ, PYTHONHASHSEED="0")   # Genesis' router iterates hash-ordered sets
    # make the repo importable regardless of PYTHONSAFEPATH / how this pytest was launched
    env["PYTHONPATH"] = str(REPO) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    out = subprocess.run([sys.executable, "-c", _REPRO_SCRIPT], cwd=REPO, env=env,
                         capture_output=True, text=True, timeout=1800)
    assert out.returncode == 0, (out.stdout + out.stderr)[-3000:]
    line = [l for l in out.stdout.splitlines() if l.startswith("RESULT ")][-1]
    got = json.loads(line[len("RESULT "):])

    assert (got["one_op"], got["two_op"], got["total"], got["duration"]) == \
        tuple(int(exp[k]) for k in ("one_op", "two_op", "total", "duration"))
    assert math.isclose(got["eps_bound"], float(exp["eps_bound"]), rel_tol=1e-9)
