"""v2 scaffold: package layout, isolation from the frozen verifier, reused-input checksums."""
import hashlib
import importlib

from circuitevolve import integrity
from circuitevolve.blocks import REPO


def test_package_layout_and_lazy_submodules():
    v2 = importlib.import_module("circuitevolve.v2")
    for name in ("verify", "metric", "baselines"):
        assert getattr(v2, name).__name__ == f"circuitevolve.v2.{name}"
    for p in ("circuitevolve/v2/README.md", "results/v2/README.md", "docs/v2/DESIGN.md"):
        assert (REPO / p).is_file(), p


def test_frozen_files_untouched_by_v2():
    from circuitevolve.v2 import verify as v
    assert v.FROZEN_DIGEST == integrity.frozen_digest()
    v.check_integrity()


def test_v2_does_not_shadow_frozen_modules():
    # v2 imports the frozen exact stack; it must be the same module objects, not copies
    from circuitevolve import sim
    from circuitevolve.v2 import verify as v
    assert v.run is sim.run and v.n_measurements is sim.n_measurements


def test_reused_inputs_unchanged():
    from circuitevolve.v2 import baselines as bl
    for key, path in (("stage1_v2", bl.STAGE1_CSV), ("reference_pipelines", bl.REFERENCE_CSV),
                      ("published", bl.PUBLISHED_CSV)):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == bl.SHA256[key], key
