"""Fixed locations for cvdv_fast."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
CVDV_SRC = REPO / "cvdv" / "src"
V3_INPUTS = REPO / "v3" / "suite" / "inputs"
GENESIS_OUT = REPO / "v3" / "baselines" / "genesis"
RULES = ROOT / "rules"
RESULTS = ROOT / "results"
BENCH = ["kerr_small", "boseHubbard_small", "z2Higgs_small", "heisenberg_small", "electronicVibration_small"]
EPS = 1e-3
N_PROBE = 3
if str(CVDV_SRC) not in sys.path:
    sys.path.insert(0, str(CVDV_SRC))
# whole-circuit cutoffs (total photon number K) per benchmark; default judge.verify.WHOLE_CUTOFFS = (10, 12)
WHOLE_CUTOFFS = {"electronicVibration_small": (8, 10)}  # 9 qumodes: K=12 would be 4.7e6 x 8 probes
