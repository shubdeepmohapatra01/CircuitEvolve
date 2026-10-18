"""Engine-owned playbook A/B machinery. Physical implementation: search/playbook.py (kept in
place so existing imports, saved playbook files and documented behavior stay valid)."""
from ..search.playbook import MAX_RULE_CHARS, Playbook, Rule  # noqa: F401

__all__ = ["Playbook", "Rule", "MAX_RULE_CHARS"]
