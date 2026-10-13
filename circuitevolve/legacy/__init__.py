"""LEGACY stacks (archived 2026-10-13; see circuitevolve/legacy/README.md).

  legacy.adder       relaxed-specification adder search (slice programs, MAP-Elites, LLM proposer)
  legacy.blocks_v1   block optimizer v1: structure programs, rule library, LLM proposer, pipeline
  legacy.evolve_opt  optimizer-program evolution (OpenEvolve-style programs over a fixed toolbox)

The old import paths (circuitevolve.search.{slice,evolve,llm}, circuitevolve.blocks.{program,rules,proposer,
pipeline}, circuitevolve.evolve_opt.*) are aliases of these modules, so every existing result can be
reproduced with its original command. The frozen verifier files did not move.
"""
