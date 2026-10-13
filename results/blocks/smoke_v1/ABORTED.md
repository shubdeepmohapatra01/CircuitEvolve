Run `smoke_v1` (2026-10-11) was interrupted before any LLM call: the gridsynth multiprocessing pool hung
inside the notebook kernel while costing the classical input of tfim_4. No results were produced; 0 proposer
calls were made. Fix: gridsynth runs serially by default (cost_model.Gridsynth procs=1). See smoke_v2.
