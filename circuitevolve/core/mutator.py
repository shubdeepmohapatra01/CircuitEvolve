"""LLM window mutator: prompt construction and LITERAL parsing of replacement windows.

The model sees one window (<= 4 local qubits q0..q3, <= 40 ops), the window's T-cost under the BQSKit
convention at the circuit's current eps_rz (per rotation), its error allowance eps_w, the active playbook
rules and recent verifier feedback, and returns replacement windows in a literal text format:

    ```window
    h q0
    cx q0 q1
    rz(-3*pi/8) q1
    rz(0.0123) q2
    ```

Gates: h s sdg x z t tdg cx cz rz(angle); `cx a b` = control a, target b. Angles: a decimal literal,
optionally times pi and divided by an integer (`0.25`, `-1.5e-3`, `pi/4`, `-3*pi/8`, `3pi/4`).
Parsing is regex-only - nothing from the response is ever passed to exec/eval/ast.literal_eval - and every
parsed window goes to the frozen verifier (core/verifier.py), so the mutator can change what is PROPOSED,
never what is ACCEPTED. The backend is any `complete(list[str]) -> list[str | Exception]`
(circuitevolve.llm_backends.make_api_backend over host.llm, thinking disabled; docs/LLM_BACKENDS.md).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

from ..blocks.circuit_io import classify_angle
from ..blocks.cost_model import canonical_angle
from .circuit import window_text

MAX_CANDIDATES = 3
MAX_LINES = 120
GATE_RE = re.compile(r"^(h|s|sdg|x|z|t|tdg|cx|cz|rz)\s*(?:\(\s*([^()]*?)\s*\))?\s+"
                     r"q\[?(\d+)\]?(?:\s*,?\s*q\[?(\d+)\]?)?\s*;?$")
ALIASES = {"tdag": "tdg", "sdag": "sdg", "t_dg": "tdg", "s_dg": "sdg", "cnot": "cx"}
NUM = r"(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
ANGLE_RE = re.compile(rf"^([+-])?\s*(?:({NUM})\s*\*?\s*)?(pi)?\s*(?:/\s*({NUM}))?$")
FENCE_RE = re.compile(r"```[ \t]*window[ \t]*\n(.*?)```", re.S | re.I)


class ParseError(ValueError):
    pass


def parse_angle(text: str) -> float:
    m = ANGLE_RE.match(text.strip().replace("\u03c0", "pi"))
    if not m or not (m.group(2) or m.group(3)):
        raise ParseError(f"bad angle {text!r}")
    sign, num, pi, den = m.groups()
    v = float(num) if num else 1.0
    if pi:
        v *= math.pi
    if den:
        d = float(den)
        if d == 0:
            raise ParseError("division by zero in angle")
        v /= d
    v = -v if sign == "-" else v
    if not math.isfinite(v):
        raise ParseError(f"non-finite angle {text!r}")
    return v


def parse_window(body: str) -> list:
    """Literal window text -> local ops. Raises ParseError."""
    ops = []
    lines = [ln.split("#", 1)[0].split("//", 1)[0].strip() for ln in body.splitlines()]
    lines = [ln for ln in lines if ln]
    if len(lines) > MAX_LINES:
        raise ParseError(f"more than {MAX_LINES} lines")
    for ln in lines:
        low = ln.lower()
        head = low.split("(", 1)[0].split()[0]
        if head in ALIASES:
            low = ALIASES[head] + low[len(head):]
        m = GATE_RE.match(low)
        if not m:
            raise ParseError(f"cannot parse line {ln!r}")
        g, arg, q1, q2 = m.groups()
        two = g in ("cx", "cz")
        if two != (q2 is not None):
            raise ParseError(f"wrong number of qubits in {ln!r}")
        if (g == "rz") != (arg is not None):
            raise ParseError(f"angle missing or unexpected in {ln!r}")
        qs = (int(q1), int(q2)) if two else (int(q1),)
        ops.append((g, qs, parse_angle(arg) if g == "rz" else None))
    return ops


def extract_candidates(text: str, max_candidates: int = MAX_CANDIDATES) -> tuple[list, list]:
    """-> (list of local op lists, list of parse errors)."""
    cands, errors = [], []
    for body in FENCE_RE.findall(text or "")[:max_candidates]:
        try:
            cands.append(parse_window(body))
        except ParseError as e:
            errors.append(str(e))
    if not cands and not errors:
        errors.append("no ```window block in the response")
    return cands, errors


# ---------------------------------------------------------------------- prompt
TASK = """You are optimizing a fault-tolerant quantum circuit compiled to Clifford+T. You get one WINDOW of the
circuit (a sub-circuit on {k} local qubits q0..q{km1}) and must return a cheaper replacement window that
implements the same {k}-qubit unitary up to global phase, within an error allowance.

Cost model (lower is better, compared lexicographically): total T-count of the whole circuit, where
  * t / tdg cost 1 T; h, s, sdg, x, z, cx, cz are free; rz at a multiple of pi/4 is exact (odd multiples = 1 T);
  * every other rz is synthesized by gridsynth at eps_rz = {eps_rz:.3e}, costing about 3*log2(1/eps_rz) T
    (~{t_per_rz} T each here); removing a rotation also loosens eps_rz for all others.
So the main gains are FEWER rotations that need synthesis, then fewer t/tdg. Merely changing an angle
to a different non-pi/4 value is not counted as an improvement.

Acceptance (decided by an exact/numerical verifier, not by you): phase-aligned operator-norm distance
between the original and your window <= allowance = {allow:.3e}. Windows using only Clifford+T gates are
checked exactly. Useful facts:
  * replacing rz(a) by rz(b) costs operator distance 2*|sin((a-b)/4)| ~ |a-b|/2;
  * rz on the CONTROL of cx commutes with that cx; x on the TARGET commutes with cx; z/s/t/rz on the same
    wire parity can merge; rz(a) rz(b) = rz(a+b); h rz(a) h = rx(a);
  * a rotation with 2*|sin(a/4)| <= allowance can be dropped; one close to a multiple of pi/4 can be snapped.

Window (time order, top to bottom):
```window
{window}
```
Rotations needing synthesis in this window (index: angle | nearest pi/4 multiple | snap distance | T now):
{rot_table}
Window T-cost now: {t_window} T ({n_rot} rotation(s) to synthesize, {t_fixed} explicit T).
{rules}{feedback}
Return up to {maxc} candidate replacement windows, each in its own ```window block, best first, using only
the gates h s sdg x z t tdg cx cz rz(angle) on q0..q{km1} (`cx a b` = control a, target b; angles as decimals
or k*pi/m). Keep the reasoning short. If you see no valid improvement, reply NONE."""


def _rot_table(local_ops, t_list) -> str:
    rows, j = [], 0
    for i, (g, qs, a) in enumerate(local_ops):
        if g == "rz" and classify_angle(a) is None:
            c = canonical_angle(a)
            k = round(c / (math.pi / 4))
            snap = 2 * abs(math.sin((c - k * math.pi / 4) / 4))
            rows.append(f"  op {i} on q{qs[0]}: rz({c:.10g}) | {k}*pi/4 | {snap:.3e} | {t_list[j]}")
            j += 1
    return "\n".join(rows) or "  (none)"


@dataclass
class WindowTask:
    """Everything one prompt needs (built by the loop)."""
    local_ops: list
    k: int
    eps_rz: float
    allowance: float
    t_rot: list                         # gridsynth T per synthesized rotation, in order
    t_fixed: int
    rules: list = field(default_factory=list)
    feedback: list = field(default_factory=list)    # short strings: recent verifier outcomes

    @property
    def t_window(self) -> int:
        return self.t_fixed + sum(self.t_rot)


def build_prompt(task: WindowTask, max_candidates: int = MAX_CANDIDATES) -> str:
    from ..search.playbook import Playbook
    rules = Playbook.render(task.rules)
    fb = ""
    if task.feedback:
        fb = "Recent verifier feedback on earlier proposals:\n" + "\n".join(f"  - {s}" for s in task.feedback) + "\n"
    return TASK.format(k=task.k, km1=task.k - 1, eps_rz=task.eps_rz,
                       t_per_rz=max(1, round(3 * math.log2(1 / task.eps_rz))), allow=task.allowance,
                       window=window_text(task.local_ops), rot_table=_rot_table(task.local_ops, task.t_rot),
                       t_window=task.t_window, n_rot=len(task.t_rot), t_fixed=task.t_fixed,
                       rules=(rules + "\n") if rules else "", feedback=fb, maxc=max_candidates)
