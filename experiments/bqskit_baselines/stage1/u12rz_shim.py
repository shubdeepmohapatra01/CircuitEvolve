"""Shim for `bqskit.passes.rules.u12rz.U1ToRZPass`.

bqskit-ft @ 2e99ba6 (bqskit/ft/cliffordrz/defaultworkflow.py:35) imports this module, but it exists
in no published bqskit release (1.2.1) nor any branch of github.com/BQSKit/bqskit (checked
2026-10-13, main @ 9324d64). Without it `CliffordRZModel` cannot be imported at all.

The workflow applies it via ForEachBlockPass(collection_filter=single_qudit_u1), i.e. ONLY to
U1Gate operations. U1(theta) = diag(1, e^{i theta}) = e^{i theta/2} RZ(theta), so the faithful
replacement is RZ(theta) (global phase only). Stage-1 inputs contain no U1 gates (CX/H/Rz only),
so on them this pass is never invoked and the shim cannot affect results.

install() registers the module in sys.modules; nothing in site-packages is modified.
"""
from __future__ import annotations

import sys
import types


def install():
    from bqskit.compiler.basepass import BasePass
    from bqskit.ir.gates.parameterized.rz import RZGate
    from bqskit.ir.gates.parameterized.u1 import U1Gate
    from bqskit.ir.operation import Operation

    class U1ToRZPass(BasePass):
        """Replace every U1Gate(theta) with RZGate(theta) (equal up to global phase)."""

        async def run(self, circuit, data) -> None:
            for cycle, op in list(circuit.operations_with_cycles()):
                if isinstance(op.gate, U1Gate):
                    circuit.replace((cycle, op.location[0]), Operation(RZGate(), op.location, op.params))

    mod = types.ModuleType('bqskit.passes.rules.u12rz')
    mod.U1ToRZPass = U1ToRZPass
    mod.__doc__ = __doc__
    sys.modules['bqskit.passes.rules.u12rz'] = mod
    import bqskit.passes.rules as rules
    rules.u12rz = mod
    return U1ToRZPass
