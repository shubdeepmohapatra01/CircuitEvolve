"""P2.1 accept-anatomy reflector input: rotation-diff anatomy on DV accepts, anatomy in the
reflect prompt, failure-stream compression. The golden fixture must pass unchanged (proposer
prompts and all pinned record fields untouched)."""
from __future__ import annotations

import math

from circuitevolve.core.circuit import Circuit, window_text
from circuitevolve.core.ledger import Ledger
from circuitevolve.core.loop import WindowLoop
from circuitevolve.engine.reflector import compress_failures, render_anatomy
from circuitevolve.search.playbook import Playbook

EPS = 1e-3
TINY = 1e-7

# one connected 3-qubit window: two equal-frame rz on q1 separated by ops that commute with
# Z on q1 (cx control, h on q2) -> merge-shaped accept; t t -> s on q0
ORIG = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.30), ("cx", (1, 2), None),
        ("h", (2,), None), ("rz", (1,), 0.25), ("rz", (2,), 0.90), ("t", (0,), None), ("t", (0,), None)]
MERGED = [ORIG[0], ORIG[1], ("rz", (1,), 0.55), ORIG[3], ORIG[4], ORIG[6], ("s", (0,), None)]


def _w(ops):
    return "```window\n" + window_text(ops) + "\n```\n"


def _fake(responses):
    def complete(prompts):
        return [responses.pop(0) if responses else "NONE" for _ in prompts]
    return complete


def _run(responses, reflect_responses, **kw):
    pb = Playbook(ab_fraction=1.0, evidence="improvement")
    pb.add("Equal-Pauli-frame rotations with a commuting path merge.", 0)
    circ = Circuit(3, list(ORIG), dict(name="anat", source="test"))
    loop = WindowLoop(circ, list(ORIG), EPS, _fake(list(responses)),
                      reflect_complete=_fake(list(reflect_responses)), playbook=pb,
                      n_calls=len(responses) + 1, batch=1, reflect_every=len(responses),
                      p_best=1.0, seed=0, **kw)
    loop.reflect_prompts = []
    orig_reflect = loop.reflect_complete

    def capture(prompts):
        loop.reflect_prompts.extend(prompts)
        return orig_reflect(prompts)

    loop.reflect_complete = capture
    s = loop.run()
    return loop, s


def test_merge_accept_yields_frame_anatomy():
    loop, s = _run([_w(MERGED)], ["NONE"])
    assert s["stats"]["accepted"] == 1
    assert len(loop.anatomy) == 1
    a = loop.anatomy[0]
    assert a.action == "window" and a.call == 1
    assert a.primary_before > a.primary_after                     # one rotation word saved
    d = a.detail
    assert d["rz_before"] == 3 and d["rz_after"] == 2
    removed_frames = {r["P"] for r in d["removed"]}
    assert removed_frames and all("Z" in p for p in removed_frames)
    assert d["merged_frames"], "equal-frame absorption must be flagged"
    # the two 0.30/0.25 rz vanished, a 0.55 appeared on the same frame
    assert any(math.isclose(r["angle"], 0.55, abs_tol=1e-9) for r in d["added"])


def test_reflect_prompt_contains_anatomy_block():
    loop, s = _run([_w(MERGED)], ["NONE"])
    assert loop.reflect_prompts, "reflector must have been called"
    p = loop.reflect_prompts[0]
    assert "# ANATOMY" in p and "merge" in p.lower()
    assert "rules shown in this prompt" in p
    assert "rotations 3 -> 2" in p


def test_failure_stream_is_compressed():
    raw = [(f"cand{i}", f"rejected: no improvement (T 24{i} -> 25{i}, rz 3 -> 3)") for i in range(6)] + \
          [(f"win{i}", f"distance 1.{i}e-02 exceeds allowance 6.25e-05") for i in range(4)]
    groups = compress_failures(raw)
    assert len(groups) <= 4
    joined = " | ".join(why for _, why in groups)
    assert "(x6 since last reflection)" in joined and "(x4 since last reflection)" in joined


def test_anatomy_render_is_factual_and_compact():
    loop, _ = _run([_w(MERGED)], ["NONE"])
    txt = render_anatomy(loop.anatomy[0])
    assert "distance" in txt and "charge" in txt and txt.count("\n") <= 8


def test_reflector_sees_grouped_failures_not_stream():
    # 5 identical planted rejections (dropped gate) then one accept, then reflect
    bad = ORIG[:3] + ORIG[4:]                                               # cx(1,2) dropped
    loop, s = _run([_w(bad), _w(bad), _w(bad), _w(bad), _w(bad), _w(MERGED)], ["NONE"])
    assert s["stats"]["rejected_verifier"] == 5 and s["stats"]["accepted"] == 1
    p = loop.reflect_prompts[0]
    assert "(x5 since last reflection)" in p