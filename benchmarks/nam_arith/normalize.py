"""Write the OpenQASM 2 copies used by CircuitEvolve v2 from the pinned upstream files (run fetch_suite.py first).

  logical/<name>.qasm    Quartz nam-benchmarks file, gates {x, h, cx, ccz}; a `gate ccz` definition is inserted so
                         the file is valid OpenQASM 2 with qelib1.inc (ccz a,b,c = h c; ccx a,b,c; h c).
  cliffordt/<name>.qasm  Quartz nam_circs file (the fully decomposed Clifford+T circuit as given, 7 T per CCZ) with
                         rz(pi*0.25) -> t and rz(pi*-0.25) -> tdg (equal up to a global phase per gate; any other
                         angle raises).
  nam/<name>_{before,light,heavy}.qasm   the authors' Quipper-ASCII files (njross/optimizer) converted gate by gate
                         (H, not/X, Z, T, T*, S, S*, with up to two positive or negative controls; a negative control
                         is conjugated by X). before = circuit Nam et al. started from; light/heavy = their outputs.
  generated/cuccaro_<n>.qasm  circuitevolve.baselines.cuccaro.construct(n) (logical, ccx kept).
"""
from __future__ import annotations

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
from fetch_suite import NAMES, nam_file  # noqa: E402

CCZ_DEF = "gate ccz a,b,c { h c; ccx a,b,c; h c; }"
CUCCARO_N = (4, 8, 16)


def header(n: int, ccz: bool = False) -> list:
    out = ["OPENQASM 2.0;", 'include "qelib1.inc";']
    if ccz:
        out.append(CCZ_DEF)
    out.append(f"qreg q[{n}];")
    return out


def _body(text: str):
    n = None
    body = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("OPENQASM", "include", "//")):
            continue
        m = re.match(r"qreg\s+\w+\[(\d+)\];", s)
        if m:
            assert n is None, "single register expected"
            n = int(m.group(1))
            continue
        body.append(re.sub(r"\b\w+\[(\d+)\]", r"q[\1]", s).replace(", ", ","))
    return n, body


def logical(text: str) -> str:
    n, body = _body(text)
    for s in body:
        assert re.match(r"(x|h|cx|ccz|ccx) ", s), s
    return "\n".join(header(n, ccz=True) + body) + "\n"


def cliffordt(text: str) -> str:
    n, body = _body(text)
    out = []
    for s in body:
        m = re.match(r"rz\(pi\*(-?[0-9.]+)\) (q\[\d+\]);", s)
        if m:
            k = float(m.group(1))
            name = {0.25: "t", -0.25: "tdg", 0.5: "s", -0.5: "sdg", 1.0: "z", -1.0: "z"}.get(k)
            if name is None:
                raise ValueError(f"non-Clifford+T angle {s}")
            out.append(f"{name} {m.group(2)};")
        else:
            assert re.match(r"(x|h|cx) ", s), s
            out.append(s)
    return "\n".join(header(n) + out) + "\n"


_QG = re.compile(r'QGate\["(\w+)"\](\*?)\((\d+)\)(?: with controls=\[([^\]]*)\])?(?: with nocontrol)?$')


def quipper_to_qasm(text: str) -> str:
    """Quipper ASCII (as in njross/optimizer Arithmetic_and_Toffoli) -> OpenQASM 2."""
    lines = text.splitlines()
    assert lines[0].startswith("Inputs:"), lines[0]
    n = len(re.findall(r"(\d+):Qbit", lines[0]))
    body = []
    use_ccz = False
    for s in lines[1:]:
        s = s.strip()
        if not s or s.startswith("Outputs:"):
            continue
        m = _QG.match(s)
        if not m:
            raise ValueError(f"unsupported Quipper line: {s}")
        g, dag, t, ctl = m.group(1), m.group(2) == "*", int(m.group(3)), m.group(4)
        ctls = [c.strip() for c in ctl.split(",")] if ctl else []
        neg = [int(c[1:]) for c in ctls if c.startswith("-")]
        cq = [int(c[1:]) for c in ctls]
        assert all(c[0] in "+-" for c in ctls), s
        pre = [f"x q[{c}];" for c in neg]
        if not cq:
            name = {("H", False): "h", ("not", False): "x", ("X", False): "x", ("Z", False): "z",
                    ("T", False): "t", ("T", True): "tdg", ("S", False): "s", ("S", True): "sdg",
                    ("H", True): "h", ("not", True): "x", ("X", True): "x", ("Z", True): "z"}[(g, dag)]
            op = f"{name} q[{t}];"
        elif g in ("not", "X") and len(cq) == 1:
            op = f"cx q[{cq[0]}],q[{t}];"
        elif g in ("not", "X") and len(cq) == 2:
            op = f"ccx q[{cq[0]}],q[{cq[1]}],q[{t}];"
        elif g == "Z" and len(cq) == 1:
            op = f"cz q[{cq[0]}],q[{t}];"
        elif g == "Z" and len(cq) == 2:
            op = f"ccz q[{cq[0]}],q[{cq[1]}],q[{t}];"
            use_ccz = True
        else:
            raise ValueError(f"unsupported controlled gate: {s}")
        body += pre + [op] + pre
    return "\n".join(header(n, ccz=use_ccz) + body) + "\n"


def cuccaro_qasm(n: int) -> str:
    from circuitevolve.baselines.cuccaro import construct
    c = construct(n)
    body = []
    for g in c.gates:
        body.append(f"{g.name} " + ",".join(f"q[{q}]" for q in g.qubits) + ";")
    return "\n".join(header(c.n_qubits) + body) + "\n"


def main():
    up = os.path.join(HERE, "upstream")
    for d in ("logical", "cliffordt", "nam", "generated"):
        os.makedirs(os.path.join(HERE, d), exist_ok=True)
    for name in NAMES:
        with open(os.path.join(up, "quartz_logical", name + ".qasm")) as f:
            txt = logical(f.read())
        open(os.path.join(HERE, "logical", name + ".qasm"), "w").write(txt)
        with open(os.path.join(up, "quartz_cliffordt", name + ".qasm")) as f:
            txt = cliffordt(f.read())
        open(os.path.join(HERE, "cliffordt", name + ".qasm"), "w").write(txt)
        for stage, tag in (("before", "before"), ("after_light", "light"), ("after_heavy", "heavy")):
            p = os.path.join(up, "nam_quipper", nam_file(name, stage))
            if os.path.exists(p):
                open(os.path.join(HERE, "nam", f"{name}_{tag}.qasm"), "w").write(quipper_to_qasm(open(p).read()))
    for n in CUCCARO_N:
        open(os.path.join(HERE, "generated", f"cuccaro_{n}.qasm"), "w").write(cuccaro_qasm(n))


if __name__ == "__main__":
    main()
