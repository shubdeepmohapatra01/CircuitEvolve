"""Engine-owned error-ledger protocol. Physical implementation: core/ledger.py (kept in place
so existing imports and documented behavior stay valid; see engine/__init__.py)."""
from ..core.ledger import Ledger  # noqa: F401

__all__ = ["Ledger"]
