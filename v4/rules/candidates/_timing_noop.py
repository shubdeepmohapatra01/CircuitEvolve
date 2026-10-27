"""Temporary no-op rule used only to measure the harness floor of one test_rule call."""
from v4.api import Rule
def _trigger(circuit): return []
def _apply(circuit, match): return circuit
RULE = Rule(name="_timing_noop", domain="dv", kind="rewrite", contract="exact",
            source="timing probe", idea="never fires; measures harness overhead only",
            trigger=_trigger, apply=_apply)
