"""P3.5 gates: the candidates-per-call knob (proposal-side only, default 3 bit-exact).

The default-path identity is ALSO guarded by the golden fixture (test_golden_dv.py, runs in
the suite unchanged): prompts and parsing at max_candidates=3 are byte-identical to pre-P3.5.
"""
from __future__ import annotations

from circuitevolve.core.mutator import MAX_CANDIDATES, build_prompt, extract_proposals, window_text
from circuitevolve.core.mutator import WindowTask


def _reply(k: int) -> str:
    block = "```window\n" + window_text([("h", (0,), None), ("t", (0,), None)]) + "\n```\n"
    return block * k


def test_default_cap_is_three():
    assert MAX_CANDIDATES == 3
    props, errs = extract_proposals(_reply(6))
    assert len(props) == 3 and not errs


def test_cap_five_parses_five():
    props, errs = extract_proposals(_reply(6), 5)
    assert len(props) == 5 and not errs
    assert all(kind == "window" for kind, _ in props)


def test_prompt_text_carries_the_cap():
    t = WindowTask(local_ops=[("h", (0,), None), ("rz", (0,), 0.3)], k=1, eps_rz=1e-4,
                   allowance=1e-4, t_rot=[12], t_fixed=0, rules=[], feedback=[])
    p3 = build_prompt(t)                    # default: unchanged wording
    p5 = build_prompt(t, 5)
    assert "at most 3 blocks" in p3 and "at most 5 blocks" in p5
    assert p3.replace("at most 3 blocks", "at most 5 blocks") == p5


def test_plugin_threads_the_knob(tmp_path):
    """WindowLoop(max_candidates=5): the plugin's parse cap and prompt cap both move."""
    from circuitevolve.core.circuit import load_input, original_ops
    from circuitevolve.core.loop import WindowLoop
    circ = load_input("tfim_6")
    orig, n = original_ops("tfim_6")
    loop5 = WindowLoop(circ, orig, 1e-3, lambda ps: ["NONE"] * len(ps),
                       runs_dir=tmp_path, max_candidates=5)
    assert loop5.plugin.max_candidates == 5
    props, errs, declined = loop5.plugin.parse(_reply(6))
    assert len(props) == 5 and not declined
    loop3 = WindowLoop(circ, orig, 1e-3, lambda ps: ["NONE"] * len(ps), runs_dir=tmp_path)
    assert loop3.plugin.max_candidates == 3
    props3, _, _ = loop3.plugin.parse(_reply(6))
    assert len(props3) == 3
