"""Recognizer features for the router. Physical implementation: v2/tier1/recognize.py (kept in
place; its tier-1 results reference it). The router uses light-weight op counts (router.py);
full structural summaries (Toffoli pairs, MCX, repeated blocks, qubit roles) come from here and
feed the triage payload and the future arithmetic family (point 3)."""
from ..v2.tier1.recognize import LogicalCircuit, Summary, load_logical, normalize, summarize  # noqa: F401

__all__ = ["load_logical", "normalize", "summarize", "Summary", "LogicalCircuit"]
