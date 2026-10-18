"""Generic engine: the domain-blind selection loop + plugin contract (PLAN_P1).

Physical homes of engine-owned machinery that predates this package (kept in place so frozen
digests, documented commands and legacy imports stay valid):
    ledger    circuitevolve/core/ledger.py      (re-exported as engine.ledger)
    playbook  circuitevolve/search/playbook.py  (re-exported as engine.playbook)
"""
from .loop import EvolveLoop
from .plugin import DomainPlugin, Member

__all__ = ["EvolveLoop", "DomainPlugin", "Member"]
