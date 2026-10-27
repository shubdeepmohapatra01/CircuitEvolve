"""Shim for `bqskit.ir.gates.measure.MidCircuitMeasurement`.

bqskit-ft branch `greedy_ntro` @ c04a322 imports this class in
`bqskit/ft/ftpasses/pkac_to_gates.py:12`, and `bqskit/ft/ftpasses/__init__.py` imports that module,
so WITHOUT it nothing under `bqskit.ft` can be imported at all. The class exists in no published
bqskit release (1.2.1) and in no branch of github.com/BQSKit/bqskit. Method of that check
(2026-10-26): `git ls-remote --heads` listed 14 heads (ZXZXZ-fix, cstr, discrete, fix-ci-precommit,
fullCircuitAwareDecomp, main, num-residuals-fix, register_workflow, runtime-cache,
runtime-cancel-fix, runtime-funny-business, scalable_ensembles, small-updates, sqrt-T-gate); each
head tarball was downloaded from codeload and grepped over its WHOLE tree (475-516 .py files per
head) for the string `MidCircuitMeasurement` -> 0 matching files on all 14, and
`bqskit/ir/gates/measure.py` declares exactly one class, `MeasurementPlaceholder(Gate)`, on all 14.
(An earlier GitHub code-search query returned total_count 0 but is not evidence for non-default
branches; the tarball grep above is.)

Where it is used upstream:
  * pkac_to_gates.py:35  - inside PKACtoGatesPass, the ONLY live use;
  * pkac_to_gates.py:45, gidney_adder.py:142 - commented out.

PKACtoGatesPass is NOT used by our T-count arm. Its own docstring states it "does *not* keep the
unitary of the circuit the same, since we replace LogicalAndInverses with an H gate and control Z
(which is applied 50% of the time)" - it mocks measurement outcomes with `random.rand() < 0.5` and
exists to feed lattice-surgery tilers, not to produce a verified circuit. T-count is therefore read
off the PKAC-form circuit (after ConvertToPKAC), where GidneyAdder / LogicalAnd are still gadgets
with known T content. The shim exists only to let the package import; our pipeline never
instantiates it. If a future arm DOES run PKACtoGatesPass, this shim must be revisited.

install() registers the class on the module object; nothing in site-packages is modified.
"""
from __future__ import annotations


def install():
    import bqskit.ir.gates.measure as measure_mod
    if hasattr(measure_mod, 'MidCircuitMeasurement'):
        return getattr(measure_mod, 'MidCircuitMeasurement')

    from bqskit.ir.gate import Gate
    from bqskit.ir.location import CircuitLocation
    from bqskit.qis.unitary.unitary import RealVector
    from bqskit.qis.unitary.unitarymatrix import UnitaryMatrix

    class MidCircuitMeasurement(Gate):
        """Single-qubit mid-circuit measurement marker into a named classical register."""

        def __init__(self, reg_name: str) -> None:
            self._name = 'mid_circuit_measurement'
            self._num_qudits = 1
            self._radixes = (2,)
            self._num_params = 0
            self.reg_name = str(reg_name)

        def get_unitary(self, params: RealVector = []) -> UnitaryMatrix:
            raise RuntimeError(
                'MidCircuitMeasurement has no unitary (shimmed stand-in; see '
                'experiments/bqskit_baselines/pk/midmeasure_shim.py).',
            )

        def get_qasm_gate_def(self) -> str:
            return f'creg {self.reg_name}[1];\n'

        def get_qasm(self, params: RealVector, location: CircuitLocation) -> str:
            return f'measure q[{location[0]}] -> {self.reg_name}[0];\n'

        def __eq__(self, other: object) -> bool:
            return (isinstance(other, MidCircuitMeasurement)
                    and other.reg_name == self.reg_name)

        def __hash__(self) -> int:
            return hash(('MidCircuitMeasurement', self.reg_name))

    measure_mod.MidCircuitMeasurement = MidCircuitMeasurement
    return MidCircuitMeasurement
