"""Golden scenario for the engine refactor (PLAN_P1 P1.0/P1.2).

Runs a fully deterministic scripted-LLM WindowLoop and extracts a behavior record. The fixture
tests/engine/golden_dv.json is generated BEFORE the refactor (phase P1.0) with the original
core/loop.py; after phase P1.2 the same scenario runs through the engine path and must produce
an identical record. Volatile fields (wall time, absolute paths) are excluded; prompts are
pinned by SHA-1 so any prompt drift is caught without storing full text.

Regenerate ONLY with a documented reason (results/CHANGELOG.md):
    .venv/bin/python -c "from tests.engine.dv_golden_scenario import write_golden; write_golden()"
"""
from __future__ import annotations

import hashlib
import json
import pathlib

GOLDEN = pathlib.Path(__file__).with_name("golden_dv.json")

EPS = 1e-3
TINY = 1e-7
BIG = 1e-3

ORIG = [("h", (0,), None), ("rz", (0,), 0.3), ("rz", (0,), 0.4), ("cx", (0, 1), None), ("rz", (1,), TINY),
        ("rz", (1,), 0.25), ("cx", (0, 1), None), ("h", (2,), None), ("rz", (2,), 0.9), ("cx", (1, 2), None),
        ("rz", (2,), BIG), ("rz", (2,), 1.1), ("t", (0,), None), ("t", (0,), None)]


def _w(ops) -> str:
    from circuitevolve.core.circuit import window_text

    return "```window\n" + window_text(ops) + "\n```\n"


def _responses():
    good_exact = [ORIG[0], ("rz", (0,), 0.7)] + ORIG[3:12] + [("s", (0,), None)]   # merge rz; t t -> s
    good_approx = good_exact[:3] + good_exact[4:]                                   # ... and drop rz(TINY)
    wrong_angle = [ORIG[0], ("rz", (0,), 0.8)] + ORIG[3:]
    return [
        _w(wrong_angle) + _w(list(ORIG)),       # call 1: verifier reject + metric reject (copy)
        _w(good_exact),                         # call 2: ACCEPT exact (charge 0)
        _w(good_approx),                        # call 3: ACCEPT approx (charge 2 sin(TINY/4)) -> reflector fires
        RuntimeError("api: overloaded"),        # call 5: llm error
        "NONE",                                 # call 6: decline
    ]


def _fake(responses):
    def complete(prompts):
        return [responses.pop(0) if responses else "NONE" for _ in prompts]

    return complete


REFLECT = ['```json\n[{"op": "add", "text": "Drop rotations whose angle is below the allowance."}]\n```']


def run_scenario() -> dict:
    """Run the scenario through the CURRENT public API and return the behavior record."""
    import tempfile

    from circuitevolve.core.circuit import Circuit
    from circuitevolve.core.loop import WindowLoop
    from circuitevolve.search.playbook import Playbook

    pb = Playbook(ab_fraction=1.0, evidence="improvement")
    pb.add("Merge rotations on the same wire; two T on one wire make S.", 0)
    with tempfile.TemporaryDirectory() as td:
        loop = WindowLoop(Circuit(3, list(ORIG), dict(name="golden", source="scenario")), list(ORIG), EPS,
                          _fake(_responses()), reflect_complete=_fake(list(REFLECT)), playbook=pb,
                          tag="golden", runs_dir=pathlib.Path(td), n_calls=6, batch=1, reflect_every=3,
                          p_best=1.0, seed=0)
        summary = loop.run()
        lines = [json.loads(x) for x in (pathlib.Path(td) / "golden.jsonl").read_text().splitlines()]

    record = dict(
        kinds=[x["kind"] for x in lines],
        prompts_sha1=[hashlib.sha1(x["prompt"].encode()).hexdigest() for x in lines if x["kind"] == "propose"],
        decisions=[[c.get("decision") for c in x.get("candidates", [])] for x in lines if x["kind"] == "propose"],
        accepts=[dict(call=x["call"], action=x.get("action"), t_before=x.get("t_before"), t_after=x.get("t_after"),
                      charge=x.get("charge"), rz_before=x.get("rz_before"), rz_after=x.get("rz_after"))
                 for x in lines if x["kind"] == "propose" and x.get("accepted")],
        stats={k: v for k, v in summary["stats"].items() if not k.startswith("_")},
        before=summary["before"], after=summary["after"],
        t_before=summary["t_before"], t_after=summary["t_after"],
        ledger=summary["ledger"], archive=summary["archive"],
        playbook=summary["playbook"], calls=summary["calls"],
        verifier_digest=summary["verifier_digest"],
    )
    return record


def write_golden():
    GOLDEN.write_text(json.dumps(run_scenario(), indent=1, sort_keys=True) + "\n")
    print(f"wrote {GOLDEN}")
