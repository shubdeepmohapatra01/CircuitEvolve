"""Block optimizer (v1): BQSKit partitions of the best classical Clifford+Rz circuit; an LLM proposes
rewrites of distinct block structures; the approximate verifier (verify_block.py, FROZEN) decides.

Op format used throughout: (name, qubits_tuple, angle) with name in
{x, z, h, s, sdg, t, tdg, cx, cz, rz} (plus u3/sx/swap for imported circuits); angle is a float for
rz, a (theta, phi, lambda) tuple for u3, else None. Qubit 0 is the most significant matrix index.
See docs/BLOCK_PIPELINE.md.
"""
import os as _os
from pathlib import Path as _Path

REPO = _Path(__file__).resolve().parents[2]
# pytket writes a config file under $XDG_CONFIG_HOME at import; ~/.config is not writable here.
_os.environ.setdefault("XDG_CONFIG_HOME", str(REPO / ".venv" / "xdg"))

# bqskit.runtime calls faulthandler.enable() at import; in notebook-style kernels stderr has no fileno
# and that raises io.UnsupportedOperation. Make it a no-op there (crash tracebacks only; no semantics).
import faulthandler as _fh
import io as _io

if not getattr(_fh.enable, "_circuitevolve_safe", False):
    _orig_enable = _fh.enable

    def _safe_enable(*a, **k):
        try:
            return _orig_enable(*a, **k)
        except (_io.UnsupportedOperation, ValueError, AttributeError):
            return None

    _safe_enable._circuitevolve_safe = True
    _fh.enable = _safe_enable
