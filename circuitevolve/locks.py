"""Process-wide locks shared by every stack.

NUMERIC_LOCK: held while a subprocess is SPAWNED and while numpy verification runs. On this macOS build,
fork/exec of a subprocess from one thread while another thread runs numpy linear algebra corrupted the
numpy results in the PARENT (30/30 wrong distances in .cache/evolve_opt/rep3.py, 0/30 without spawning;
2026-10-11). Spawning is fast, so holding the lock only around Popen costs nothing. Moved here from
evolve_opt/sandbox.py on 2026-10-13 so the window core and the legacy stacks share ONE lock.
"""
import threading

NUMERIC_LOCK = threading.RLock()
