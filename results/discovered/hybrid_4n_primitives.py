"""4n-T adder found by LLM proposals + local repair, primitives only (tier B), 2026-10-06.
Run: results/llm_runs/cuccaro_B_open_evo_repair300_120.*  Verified exactly n = 1..16.
LLM supplied the structure; local repair inserted s(cout) before the uncompute H (phase fix)."""
from circuitevolve.search.slice import G, SliceProgram

FWD = (
    G('cx', 'a', 'b'),
    G('cx', 'a', 'pa'),
    G('h', 'cout'),
    G('t', 'cout'),
    G('cx', 'b', 'cout'),
    G('tdg', 'cout'),
    G('cx', 'pa', 'cout'),
    G('t', 'cout'),
    G('cx', 'b', 'cout'),
    G('tdg', 'cout'),
    G('cx', 'pa', 'cout'),
    G('h', 'cout'),
    G('cx', 'cout', 'a'),
)
TOP = (
    G('cx', 'a', 'z'),
)
BWD = (
    G('cx', 'cout', 'a'),
    G('s', 'cout'),
    G('h', 'cout'),
    G('measure', 'cout', label='m'),
    G('cz', 'b', 'pa', cond='m'),
    G('x', 'cout', cond='m'),
    G('cx', 'a', 'pa'),
    G('cx', 'pa', 'b'),
)

PROGRAM = SliceProgram(FWD, TOP, BWD)
