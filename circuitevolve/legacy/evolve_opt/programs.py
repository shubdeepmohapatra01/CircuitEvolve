"""Seed program (= best classical pipeline) and the program generator of the classical control."""
from __future__ import annotations

import random

SEED_PROGRAM = '''"""Seed: best classical pipeline = min(pyzx full_reduce, TKET FullPeepholeOptimise), then whole-circuit
phase folding + 1q resynthesis, keeping whichever is cheaper."""


def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    best = tools.best(a, b)
    folded = tools.fold_resynth(tools.canonicalize(best))
    return tools.best(best, folded)
'''

# The best-classical reference itself (no phase fold): used to sanity-check the toolbox against
# results/evolve_opt/baseline_dev.json.
BEST_CLASSICAL_PROGRAM = '''def optimize(circ, tools, budget):
    a = tools.pyzx_full_reduce(tools.lower(circ))
    b = tools.tket(circ, "FullPeepholeOptimise")
    return tools.best(a, b)
'''

# ------------------------------------------------------------------------------ control genome
START_CHOICES = ("pyzx", "tket_fpo", "tket_fpo_noswap", "minrz", "pyzx_teleport", "tket_fpo_pyzx", "pyzx_tket_fpo")
STEP_CHOICES = (
    "pyzx_full_reduce", "pyzx_teleport_reduce", "pyzx_clifford_simp", "pyzx_basic",
    "phase_fold", "resynth_1q", "fold_resynth",
    "tket:FullPeepholeOptimise", "tket:FullPeepholeOptimiseNoSwaps", "tket:PeepholeOptimise2Q", "tket:CliffordSimp",
    "tket:RemoveRedundancies", "tket:CommuteThroughMultis", "tket:KAKDecomposition", "tket:SynthesiseTket",
    "tket:OptimisePhaseGadgets", "tket:PauliSimp", "tket:GreedyPauliSimp", "tket:ZXGraphlikeOptimisation",
    "tket:CliffordResynthesis", "tket:ThreeQubitSquash", "tket:PauliSquash",
    "block:fold_resynth:3:40", "block:fold_resynth:2:40", "block:fold_resynth:4:80", "block:pyzx:3:40",
    "block:tket:3:40", "block:tket:2:20", "approx_round:0.5", "approx_round:1.0",
)
_START_SRC = {
    "pyzx": "tools.pyzx_full_reduce(tools.lower(circ))",
    "tket_fpo": 'tools.tket(circ, "FullPeepholeOptimise")',
    "tket_fpo_noswap": 'tools.tket(circ, "FullPeepholeOptimiseNoSwaps")',
    "minrz": "tools.lower(circ)",
    "pyzx_teleport": "tools.pyzx_teleport_reduce(tools.lower(circ))",
    "tket_fpo_pyzx": 'tools.pyzx_full_reduce(tools.tket(circ, "FullPeepholeOptimise"))',
    "pyzx_tket_fpo": 'tools.tket(tools.pyzx_full_reduce(tools.lower(circ)), "FullPeepholeOptimise")',
}

SEED_GENOME = dict(starts=["pyzx", "tket_fpo"], steps=["fold_resynth"])


def _step_src(s: str) -> str:
    if s.startswith("tket:"):
        return f'tools.tket(cur, "{s[5:]}")'
    if s.startswith("block:"):
        _, m, bs, mg = s.split(":")
        return f'tools.block_optimize(cur, method="{m}", block_size={bs}, max_gates={mg})'
    if s.startswith("approx_round:"):
        frac = float(s.split(":")[1])
        return f"tools.approx_round(cur, {frac} * tools.error_left(cur))"
    return f"tools.{s}(cur)"


def genome_source(g: dict) -> str:
    """Straight-line program: best of the start pipelines, then each step applied to the running best;
    a step's output is kept only if cheaper; failing steps are skipped."""
    lines = ['"""Classical-control program (generated from a pass-sequence genome)."""', "",
             "", "def optimize(circ, tools, budget):", "    starts = []"]
    for s in g["starts"]:
        lines += ["    try:", f"        starts.append({_START_SRC[s]})", "    except Exception:", "        pass"]
    lines += ["    cur = tools.best(starts)"]
    for s in g["steps"]:
        lines += ["    try:", f"        nxt = {_step_src(s)}", "        cur = tools.best(cur, nxt)",
                  "    except Exception:", "        pass"]
    lines += ["    return cur", ""]
    return "\n".join(lines)


def random_genome(rng: random.Random, max_starts: int = 3, max_steps: int = 6) -> dict:
    starts = rng.sample(START_CHOICES, rng.randint(1, max_starts))
    steps = [rng.choice(STEP_CHOICES) for _ in range(rng.randint(0, max_steps))]
    return dict(starts=starts, steps=steps)


def mutate_genome(g: dict, rng: random.Random, max_starts: int = 3, max_steps: int = 8) -> dict:
    g = dict(starts=list(g["starts"]), steps=list(g["steps"]))
    op = rng.choice(["add_step", "add_step", "del_step", "replace_step", "swap_steps", "toggle_start"])
    if op == "add_step" and len(g["steps"]) < max_steps:
        g["steps"].insert(rng.randint(0, len(g["steps"])), rng.choice(STEP_CHOICES))
    elif op == "del_step" and g["steps"]:
        g["steps"].pop(rng.randrange(len(g["steps"])))
    elif op == "replace_step" and g["steps"]:
        g["steps"][rng.randrange(len(g["steps"]))] = rng.choice(STEP_CHOICES)
    elif op == "swap_steps" and len(g["steps"]) >= 2:
        i, j = rng.sample(range(len(g["steps"])), 2)
        g["steps"][i], g["steps"][j] = g["steps"][j], g["steps"][i]
    else:
        s = rng.choice(START_CHOICES)
        if s in g["starts"] and len(g["starts"]) > 1:
            g["starts"].remove(s)
        elif s not in g["starts"] and len(g["starts"]) < max_starts:
            g["starts"].append(s)
        else:
            g["steps"].append(rng.choice(STEP_CHOICES)) if len(g["steps"]) < max_steps else None
    return g
