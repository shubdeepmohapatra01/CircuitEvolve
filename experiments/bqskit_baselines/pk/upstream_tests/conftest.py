import sys, os
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.dirname(_here))
sys.path.insert(0, os.path.join(os.path.dirname(_here), "stage1"))
from midmeasure_shim import install as _m; _m()
from u12rz_shim import install as _u; _u()
import serial_runtime; serial_runtime.install()
