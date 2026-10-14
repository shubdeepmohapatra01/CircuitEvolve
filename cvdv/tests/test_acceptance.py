"""Acceptance suite for the frozen verifier stack (certify + library static checks + compiler gates).

Every planted bug must be detected (eps above threshold, rule rejected, or library refused);
every legitimate rule must pass.  Run:  pytest -q tests/test_acceptance.py   (env cvdv-opt)
"""
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from cvdv import certify as C, compiler as CO, isa as ISA, library as L, terms as T, unit_terms as UT  # noqa: E402

SEED = open(os.path.join(os.path.dirname(__file__), "..", "libraries", "seed.py")).read()
DETECT = 1e-6   # a planted bug must give eps above this
PASS = 1e-9     # an exact rule must give eps below this


def certify_rule(src, kind, H, n_max=3, r=1, n_sys_q=None, n_sys_m=None):
    rules = L.load(src)
    part = T.classify(H)[0]
    ws = H.wires()
    nq = n_sys_q if n_sys_q is not None else max([w[1] + 1 for w in ws if w[0] == "q"], default=0)
    nm = n_sys_m if n_sys_m is not None else max([w[1] + 1 for w in ws if w[0] == "qm"], default=0)
    comp = CO.Compiler(rules, n_max=n_max, n_sys_q=nq, n_sys_m=nm)
    (name, fn), = rules[kind]
    ops = comp.emit(part, fn, r)
    return C.certify(H, ops, part.kind, n_max=n_max), comp.evaluate(part, H, fn, r)


def one(body, kind):
    return f"def rule_{kind}__x(t, g, r):\n" + "\n".join("    " + l for l in body.strip().splitlines()) + "\n"


HOP = UT.hop(0, 1, 0.4, 0.3)
ZHOP = UT.hop(0, 1, 0.6, 0.2, "Z")
N2 = (UT.n_(0) * UT.n_(0)).scale(0.7)
ZZ = UT.pauli("ZZ", -0.37)
DISP = T.Poly({((), ((0, 1, 0),)): 0.3 + 0.2j, ((), ((0, 0, 1),)): 0.3 - 0.2j})

PARITY = """
a = g.anc_qubit()
md = t.m[0]
g.R(3 * t.theta, md)
g.h(a)
g.CP(a, md)
g.h(a)
g.rz(3 * t.theta, a)
g.CR(-2 * t.theta, a, md)
g.h(a)
g.CR(-m.pi, a, md)
g.h(a)
"""

GOOD = [
    ("hop", HOP, "g.BS(2 * t.theta, t.phi, t.m[0], t.m[1])", 3),
    ("z_hop", ZHOP, "g.CP(t.q[0], t.m[1])\ng.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])\ng.CR(-m.pi, t.q[0], t.m[1])", 3),
    ("disp", DISP, "g.D(t.alpha, t.m[0])", 3),
    ("n2", N2, PARITY, 3),
    # global phase only: rz on an ancilla in |0> must pass
    ("hop", HOP, "g.BS(2 * t.theta, t.phi, t.m[0], t.m[1])\ng.rz(0.7, g.anc_qubit())", 3),
]

BUGS = [
    ("hop: half angle", "hop", HOP, "g.BS(t.theta, t.phi, t.m[0], t.m[1])", 3),
    ("hop: phase sign", "hop", HOP, "g.BS(2 * t.theta, -t.phi, t.m[0], t.m[1])", 3),
    ("z_hop: missing CP dagger (qubit garbage)", "z_hop", ZHOP,
     "g.CP(t.q[0], t.m[1])\ng.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])", 3),
    ("z_hop: CP instead of CP dagger", "z_hop", ZHOP,
     "g.CP(t.q[0], t.m[1])\ng.BS(2 * t.theta, t.phi + m.pi / 2, t.m[0], t.m[1])\ng.CP(t.q[0], t.m[1])", 3),
    ("disp: conjugated amplitude", "disp", DISP, "g.D(m.conj(t.alpha), t.m[0])", 3),
    ("n2: wrong BCH sign (A,B swapped)", "n2", N2, """
a = g.anc_qubit()
x = m.sqrt(abs(t.theta) / 2)
for sgn in (-1, 1):
    g.h(a)
    g.CR(2 * sgn * x, a, t.m[0])
    g.h(a)
    g.sdg(a)
    g.h(a)
    g.CR(2 * sgn * x, a, t.m[0])
    g.h(a)
    g.s(a)
""", 3),
    ("n2: truncation-edge-only (exact n<=3, certified at n_max=4)", "n2", N2.scale(0.3 / 0.7), PARITY, 4),
    ("n2: ancilla left excited", "n2", N2, PARITY + "g.x(a)\n", 3),
    ("pauli ZZZ: CP reused for U dagger (wrong for odd weight)", "pauli", UT.pauli("ZZZ", -0.37), """
a = g.anc_mode()
b = m.sqrt(abs(t.theta) / 2)
gg = -b if t.theta < 0 else b
g.D(-1j * gg, a)
for q in t.q:
    g.CP(q, a)
g.D(-b * 1j ** 3, a)
for q in t.q:
    g.CP(q, a)
g.D(1j * gg, a)
for q in t.q:
    g.CP(q, a)
g.D(b * 1j ** 3, a)
for q in t.q:
    g.CP(q, a)
""", 3),
    ("pauli ZZ: angle 2|c|^2 vs c (Genesis parameterisation)", "pauli", ZZ, """
a = g.anc_mode()
b = abs(t.theta)
g.D(1j * b, a)
for q in t.q:
    g.CR(-m.pi, q, a)
g.D(b, a)
for q in t.q:
    g.CP(q, a)
g.D(-1j * b, a)
for q in t.q:
    g.CR(-m.pi, q, a)
g.D(-b, a)
for q in t.q:
    g.CP(q, a)
""", 3),
    ("hop: tiny 1e-5 angle error", "hop", HOP, "g.BS(2 * t.theta + 1e-5, t.phi, t.m[0], t.m[1])", 3),
]


@pytest.mark.parametrize("kind,H,body,n_max", GOOD)
def test_good_rules_pass(kind, H, body, n_max):
    cert, ev = certify_rule(one(body, kind), kind, H, n_max=n_max)
    assert cert["reliable"] and cert["eps"] < PASS, cert


@pytest.mark.parametrize("label,kind,H,body,n_max", BUGS, ids=[b[0] for b in BUGS])
def test_planted_bugs_detected(label, kind, H, body, n_max):
    cert, ev = certify_rule(one(body, kind), kind, H, n_max=n_max)
    assert cert["eps"] > DETECT, (label, cert)


def test_seed_library_exact_kinds():
    rules = L.load(SEED)
    for name, H in UT.cases():
        part = T.classify(H)[0]
        if part.kind == "n2":
            continue
        best = None
        comp = CO.Compiler(rules, n_max=3, n_sys_q=4, n_sys_m=2)
        for rn, fn in rules[part.kind]:
            ev = comp.evaluate(part, H, fn, 1)
            if ev is not None:
                best = ev[1]["eps"] if best is None else min(best, ev[1]["eps"])
        assert best is not None and best < PASS, (name, best)


def test_foreign_wire_rejected():
    src = one("g.BS(2 * t.theta, t.phi, t.m[0], t.m[1])\ng.R(0.1, ('qm', 0))", "hop")
    rules = L.load(src)
    H = UT.hop(1, 2, 0.4, 0.3)  # system modes 1, 2; mode 0 is another system mode, not an ancilla
    comp = CO.Compiler(rules, n_max=3, n_sys_q=0, n_sys_m=3)
    part = T.classify(H)[0]
    assert comp.evaluate(part, H, rules["hop"][0][1], 1) is None


@pytest.mark.parametrize("src", [
    "import os\n",
    "def rule_n__x(t, g, r):\n    import os\n",
    "def rule_n__x(t, g, r):\n    g.__class__\n",
    "def rule_n__x(t, g, r):\n    g._add('R', (1,), t.m[0])\n",
    "def rule_n__x(t, g, r):\n    while True:\n        pass\n",
    "def rule_n__x(t, g, r):\n    open('x')\n",
    "def rule_n__x(t, g, r):\n    t.m.__len__()\n",
    "x = open\n",
    "def helper(t, g, r):\n    pass\n",
    "def rule_n__x(t, g, r):\n    (lambda: 0)()\n",
])
def test_static_check_rejects(src):
    with pytest.raises((L.LibraryError, NameError, SyntaxError)):
        rules = L.load(src)
        for fns in rules.values():
            for _, fn in fns:
                fn(None, None, 1)


PDISP_X = UT.pauli_disp("X", 0.25 - 0.1j)


@pytest.mark.parametrize("kind,H,body,good", [
    ("z_hop", ZHOP, "g.CBS(2 * t.theta, t.phi, t.q[0], t.m[0], t.m[1])", True),
    ("z_hop", ZHOP, "g.CBS(t.theta, t.phi, t.q[0], t.m[0], t.m[1])", False),           # half angle
    ("z_hop", ZHOP, "g.CBS(2 * t.theta, -t.phi, t.q[0], t.m[0], t.m[1])", False),      # phase sign
    ("pauli_disp", PDISP_X, "g.RB(1j * t.alpha, t.q[0], t.m[0])", True),
    ("pauli_disp", PDISP_X, "g.RB(t.alpha, t.q[0], t.m[0])", False),                   # missing i
], ids=["CBS ok", "CBS half angle", "CBS phase sign", "RB ok", "RB missing i"])
def test_genesis_isa_gates(kind, H, body, good):
    rules = L.load(one(body, kind))
    part = T.classify(H)[0]
    nq = max([w[1] + 1 for w in H.wires() if w[0] == "q"], default=0)
    nm = max([w[1] + 1 for w in H.wires() if w[0] == "qm"], default=0)
    comp = CO.Compiler(rules, n_max=3, n_sys_q=nq, n_sys_m=nm, isa=ISA.GENESIS)
    ops = comp.emit(part, rules[kind][0][1], 1)
    cert = C.certify(H, ops, part.kind, n_max=3)
    assert (cert["reliable"] and cert["eps"] < PASS) if good else cert["eps"] > DETECT, cert
    # the same rule must be refused under the phase-space ISA
    comp_ps = CO.Compiler(rules, n_max=3, n_sys_q=nq, n_sys_m=nm, isa=ISA.PS_BS)
    assert comp_ps.evaluate(part, H, rules[kind][0][1], 1) is None
