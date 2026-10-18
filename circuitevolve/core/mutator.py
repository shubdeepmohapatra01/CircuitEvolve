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
from ..blocks.cost_model import canonical_angle, canonicalize
from .circuit import ParseError, parse_angle, window_text  # noqa: F401 (re-exported)

MAX_CANDIDATES = 3
MAX_LINES = 120
GATE_RE = re.compile(r"^(h|s|sdg|x|z|t|tdg|cx|cz|rz)\s*(?:\(\s*([^()]*?)\s*\))?\s+"
                     r"q\[?(\d+)\]?(?:\s*,?\s*q\[?(\d+)\]?)?\s*;?$")
ALIASES = {"tdag": "tdg", "sdag": "sdg", "t_dg": "tdg", "s_dg": "sdg", "cnot": "cx"}
FENCE_RE = re.compile(r"```[ \t]*window[ \t]*\n(.*?)```", re.S | re.I)


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


DECLINED = "declined (NONE)"


def is_declined(text: str) -> bool:
    """The model answered NONE (as the prompt allows), outside or inside a window block, and gave no fix block."""
    from .refit import FIX_FENCE_RE
    if FIX_FENCE_RE.findall(text or ""):
        return False
    bodies = [b.strip().upper() for b in FENCE_RE.findall(text or "")]
    if bodies:
        return all(b in ("NONE", "") for b in bodies)
    return bool(re.search(r"(^|\n)\s*\**NONE\**\s*\.?\s*$", (text or "").strip()))


def extract_candidates(text: str, max_candidates: int = MAX_CANDIDATES) -> tuple[list, list]:
    """-> (list of local op lists, list of parse errors). A NONE answer gives ([], [DECLINED]); callers
    count DECLINED separately from parse errors."""
    if is_declined(text):
        return [], [DECLINED]
    cands, errors = [], []
    for body in FENCE_RE.findall(text or "")[:max_candidates]:
        try:
            cands.append(parse_window(body))
        except ParseError as e:
            errors.append(str(e))
    if not cands and not errors:
        errors.append("no ```window block in the response")
    return cands, errors


BLOCK_RE = re.compile(r"```[ \t]*(window|fix)[ \t]*\n(.*?)```", re.S | re.I)


def extract_proposals(text: str, max_candidates: int = MAX_CANDIDATES) -> tuple[list, list]:
    """Both actions, in response order: -> ([("window", local_ops) | ("fix", {op_index: target})], errors).
    At most `max_candidates` blocks in total. A NONE answer gives ([], [DECLINED])."""
    from .refit import parse_fix
    if is_declined(text):
        return [], [DECLINED]
    props, errors = [], []
    for kind, body in BLOCK_RE.findall(text or "")[:max_candidates]:
        kind = kind.lower()
        try:
            props.append(("window", parse_window(body)) if kind == "window" else ("fix", parse_fix(body)))
        except ParseError as e:
            errors.append(f"{kind}: {e}")
    if not props and not errors:
        errors.append("no ```window or ```fix block in the response")
    return props, errors


# ---------------------------------------------------------------------- prompt
TASK = """You are optimizing a fault-tolerant quantum circuit compiled to Clifford+T. You get one WINDOW of the
circuit (a sub-circuit on {k} local qubits q0..q{km1}) and propose a cheaper replacement that implements the same
{k}-qubit unitary up to global phase, within an error allowance.

Cost model (lower is better, compared lexicographically): total T-count of the whole circuit, where
  * t / tdg cost 1 T; h, s, sdg, x, z, cx, cz are free; rz at a multiple of pi/4 is exact (odd multiples = 1 T);
  * every other rz is synthesized by gridsynth at eps_rz = {eps_rz:.3e}, costing about 3*log2(1/eps_rz) T
    (~{t_per_rz} T each here); removing a rotation also loosens eps_rz for all others; error budget you spend is
    taken from synthesis, so a rewrite must save more T than it costs the other rotations.
So the main gains are FEWER rotations that need synthesis, then fewer t/tdg. Merely changing an angle
to a different non-pi/4 value is not counted as an improvement.

Acceptance (decided by an exact/numerical verifier, not by you): phase-aligned operator-norm distance
between the original and the replacement window <= allowance = {allow:.3e}. Clifford+T windows are checked exactly.

Two actions (you may mix them; at most {maxc} blocks in total, best first):
 A. EXACT REWRITE - a full replacement window in a ```window block (gates h s sdg x z t tdg cx cz rz(angle) on
    q0..q{km1}; `cx a b` = control a, target b; angles as decimals or k*pi/m). Useful facts: rz on the CONTROL of
    cx commutes with it; x on the TARGET commutes with it; rz(a) rz(b) = rz(a+b) on one wire; a cx pair
    conjugating an rz moves the rotation to a wire parity; h rz(a) h = rx(a).
 B. FIX-AND-REFIT - a ```fix block naming rotations of this window by op index and a target value each:
        ```fix
        op 7 -> pi/4
        op 12 -> 0
        ```
    Targets: 0 (delete), a multiple of pi/4 (exact, free or 1 T), or 2*pi*m/2^k with k <= 4 (pi/8 multiples are
    still synthesized here, so they save nothing by themselves). A numerical optimizer then re-fits ALL OTHER
    non-pi/4 rotations of the window to stay as close as possible to the original unitary; the verifier
    checks the refitted window against the allowance. A fix only survives if the remaining rotations can
    absorb the change - e.g. another rotation acting on the same wire or the same cx-parity, or a set of
    rotations whose combined effect is redundant. A rotation with nothing to absorb it fails unless its
    plain snap distance (table) is itself within the allowance. Fixing several rotations at once is allowed.

Window (time order, top to bottom; angles reduced to [-pi, pi]; `# op i` = index for fix blocks):
```window
{window}
```
Rotations needing synthesis (op index: angle | nearest pi/4 multiple | |angle - multiple| rad | plain snap
distance without refit (an upper bound; usable directly only if <= allowance, summed) | T now | P):
P = the rotation's Pauli with all Clifford gates of the window moved to its end: op i = exp(-i*angle/2 * P).
Two rotations with the same P letters merge (same sign: angles add; opposite sign: subtract) when every
rotation between them has a P that COMMUTES with theirs (two Paulis commute iff they differ, both non-I, on an
even number of qubits); a fix of one of them to 0 is then refitted exactly. Different P letters do not merge.
{rot_table}
Window T-cost now: {t_window} T ({n_rot} rotation(s) to synthesize, {t_fixed} explicit T).
{rules}{feedback}
Keep the reasoning short. If you see no valid improvement, reply NONE."""


CLIFFORD_1Q = ("h", "s", "sdg", "x", "z")


def rotation_paulis(local_ops, k: int) -> dict:
    """{op index: signed Pauli label} for every rz / t / tdg of the window: with all Clifford gates of the window
    moved to its END, rotation i equals exp(-i*angle/2 * P_i), P_i = C_<i^dag Z_q C_<i, where C_<i is the product
    of the Clifford gates before op i (non-Clifford rotations are skipped: they are themselves Pauli rotations).
    Computed numerically on 2^k-dim matrices with the frozen verifier's unitary() (qubit 0 most significant),
    then read off in the Pauli basis (exactly one coefficient is +-1). Label: sign + one letter per qubit q0..q{k-1}."""
    import itertools

    import numpy as np

    from ..blocks import verify_block as vb
    I2 = np.eye(2, dtype=complex)
    PM = {"I": I2, "X": np.array([[0, 1], [1, 0]], complex), "Y": np.array([[0, -1j], [1j, 0]], complex),
          "Z": np.diag([1.0 + 0j, -1.0])}
    basis = []
    for lab in itertools.product("IXYZ", repeat=k):
        M = PM[lab[0]]
        for c in lab[1:]:
            M = np.kron(M, PM[c])
        basis.append(("".join(lab), M))
    out, cliff = {}, []
    for i, (g, qs, a) in enumerate(local_ops):
        if g in ("rz", "t", "tdg"):
            Zq = basis[[lab for lab, _ in basis].index("".join("Z" if j == qs[0] else "I" for j in range(k)))][1]
            C = vb.unitary(cliff, k) if cliff else np.eye(2 ** k, dtype=complex)
            P = C.conj().T @ Zq @ C
            for lab, M in basis:
                c = np.trace(M @ P).real / 2 ** k
                if abs(abs(c) - 1) < 1e-9:
                    out[i] = ("+" if c > 0 else "-") + lab
                    break
        else:
            cliff.append((g, qs, a))
    return out


def _rot_table(local_ops, t_list, k: int | None = None) -> str:
    paulis = {}
    if k is not None:
        try:
            paulis = rotation_paulis(local_ops, k)
        except Exception:                 # pragma: no cover - informational column only
            paulis = {}
    rows, j = [], 0
    for i, (g, qs, a) in enumerate(local_ops):
        if g == "rz" and classify_angle(a) is None:
            c = canonical_angle(a)
            kq = round(c / (math.pi / 4))
            delta = abs(c - kq * math.pi / 4)
            snap = 2 * abs(math.sin(delta / 4))
            pl = f" | P={paulis[i]}" if i in paulis else ""
            rows.append(f"  op {i} on q{qs[0]}: rz({c:.10g}) | {kq}*pi/4 | {delta:.3e} | {snap:.3e} | {t_list[j]}{pl}")
            j += 1
    tg = [f"op {i}: {paulis[i]}" for i, (g, _, _) in enumerate(local_ops) if g in ("t", "tdg") and i in paulis]
    if tg:
        rows.append("  t/tdg gates (rotations by +-pi/4, cost 1 T each): " + ", ".join(tg))
    return "\n".join(rows) or "  (none)"


def indexed_window_text(local_ops) -> str:
    """window_text with a trailing `# op i` comment on every rz line (comments are ignored by parse_window)."""
    lines = window_text(canonicalize(local_ops)).splitlines()
    return "\n".join(f"{ln}  # op {i}" if local_ops[i][0] == "rz" else ln for i, ln in enumerate(lines))


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
                       window=indexed_window_text(task.local_ops), rot_table=_rot_table(task.local_ops, task.t_rot, task.k),
                       t_window=task.t_window, n_rot=len(task.t_rot), t_fixed=task.t_fixed,
                       rules=(rules + "\n") if rules else "", feedback=fb, maxc=max_candidates)
