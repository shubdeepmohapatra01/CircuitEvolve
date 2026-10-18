"""v2 metric: frozen cost.py on exact circuits, BQSKit convention (core/metric) on rotations."""
import math

import pytest

from circuitevolve.baselines import cuccaro, gidney
from circuitevolve.core.circuit import Circuit as CoreCircuit
from circuitevolve.core.metric import BqskitTMetric
from circuitevolve.cost import cost
from circuitevolve.v2 import metric
from circuitevolve.v2.verify import adder_reference


@pytest.mark.parametrize("n", (1, 2, 3, 4))
def test_adder_counts(n):
    c = cuccaro.construct(n)
    m = metric.measure(c, data_qubits=adder_reference(n))
    assert m["t_count"] == 14 * n == cost(c)["t_count"]
    assert m["ancillas"] == 1 and m["qubits"] == 2 * n + 2 and m["measurements"] == 0
    g = metric.measure(gidney.construct(n))
    assert g["t_count"] == 4 * n and g["ancillas"] == n - 1 and g["measurements"] == n - 1
    assert g["t_depth"] == cost(gidney.construct(n))["t_depth"]


def test_pi4_rotations_need_no_eps():
    c = CoreCircuit(1, [("rz", (0,), math.pi / 4), ("rz", (0,), math.pi / 2), ("t", (0,), None)])
    m = metric.measure(c)
    assert m["t_count"] == 2 and m["rz"] == 0


def test_rotations_use_bqskit_convention():
    ops = [("h", (0,), None), ("cx", (0, 1), None), ("rz", (1,), 0.3), ("rz", (0,), math.pi / 4),
           ("cx", (0, 1), None), ("rz", (0,), 1.1)]
    c = CoreCircuit(2, ops)
    with pytest.raises(ValueError):
        metric.measure(c)
    m = metric.measure(c, eps=1e-3)
    k = BqskitTMetric(1e-3).cost(c.ops)
    assert m["t_count"] == k["t"] and m["t_gs"] == k["t_gs"] and m["t_fixed"] == 1
    assert m["rz"] == 2 and m["eps_rz"] == pytest.approx(1e-3 / 2)
    assert m["t_gs"] <= m["t_depth"] <= m["t_count"]


def test_fitness_is_lexicographic():
    a = dict(t_count=10, qubits=50, t_depth=9)
    b = dict(t_count=11, qubits=3, t_depth=1)
    assert metric.fitness_key(a) < metric.fitness_key(b)
