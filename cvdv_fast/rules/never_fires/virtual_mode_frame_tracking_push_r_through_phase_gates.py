from cvdv_fast.api import Rule, Op
import math
import cmath

TWO_PI = 2 * math.pi


def _norm_angle(theta):
    # reduce to (-pi, pi] to decide near-zero / near-multiple-of-2pi cleanly
    theta = theta % TWO_PI
    if theta > math.pi:
        theta -= TWO_PI
    return theta


def _is_zero(theta, tol=1e-12):
    return abs(_norm_angle(theta)) < tol


def _mode_wire(w):
    # a wire is a qumode wire tuple ('qm', j)
    return w[0] == 'qm'


def trigger(ops):
    # a single match covers the whole circuit: we rewrite it in one shot.
    for o in ops:
        if o.name == 'R':
            return [(0, len(ops) - 1)]
    return []


def apply(ops, m):
    i0, i1 = m
    frame = {}  # mode wire -> pending angle theta

    def get_frame(w):
        return frame.get(w, 0.0)

    def add_frame(w, d):
        frame[w] = get_frame(w) + d

    new_ops = []

    for o in ops:
        name = o.name
        wires = tuple(o.wires)

        if name == 'R':
            # R acts on a single qumode wire; absorb into pending frame, drop the gate
            w = wires[0]
            add_frame(w, o.params[0])
            continue

        if name == 'CR' or name == 'CP':
            # commutes with n on its qumode wire(s); pass through unchanged
            new_ops.append(o)
            continue

        if name == 'D':
            w = wires[0]
            theta = get_frame(w)
            if theta == 0.0:
                new_ops.append(o)
            else:
                alpha = complex(o.params[0])
                new_ops.append(Op('D', (alpha * cmath.exp(1j * theta),), wires))
            continue

        if name == 'CD':
            # CD acts on (q, a): qubit wire + one qumode wire
            mode_w = None
            for w in wires:
                if _mode_wire(w):
                    mode_w = w
                    break
            if mode_w is None:
                new_ops.append(o)
                continue
            theta = get_frame(mode_w)
            if theta == 0.0:
                new_ops.append(o)
            else:
                alpha = complex(o.params[0])
                new_ops.append(Op('CD', (alpha * cmath.exp(1j * theta),), wires))
            continue

        if name == 'RB':
            # RB acts on (q, a): qubit wire + one qumode wire
            mode_w = None
            for w in wires:
                if _mode_wire(w):
                    mode_w = w
                    break
            if mode_w is None:
                new_ops.append(o)
                continue
            theta = get_frame(mode_w)
            if theta == 0.0:
                new_ops.append(o)
            else:
                t = complex(o.params[0])
                new_ops.append(Op('RB', (t * cmath.exp(1j * theta),), wires))
            continue

        if name == 'BS' or name == 'CBS':
            # wires: find the two qumode wires among the op's wires, in order.
            mode_ws = [w for w in wires if _mode_wire(w)]
            if len(mode_ws) != 2:
                new_ops.append(o)
                continue
            wa, wb = mode_ws[0], mode_ws[1]
            theta_a = get_frame(wa)
            theta_b = get_frame(wb)
            if theta_a == 0.0 and theta_b == 0.0:
                new_ops.append(o)
            else:
                tparam, pparam = o.params[0], o.params[1]
                new_p = pparam + theta_a - theta_b
                new_ops.append(Op(name, (tparam, new_p), wires))
            continue

        # any other gate: if it touches a qumode that has a pending frame, flush first
        touched = [w for w in wires if _mode_wire(w) and get_frame(w) != 0.0]
        for w in touched:
            theta = get_frame(w)
            new_ops.append(Op('R', (theta,), (w,)))
            frame[w] = 0.0
        new_ops.append(o)

    # flush remaining frames at the end, one R per mode, skip near-zero / near-2pi-multiple
    # preserve a stable order: by first appearance order of the wire in frame dict
    for w, theta in frame.items():
        if not _is_zero(theta):
            reduced = _norm_angle(theta)
            new_ops.append(Op('R', (reduced,), (w,)))

    return i0, i1, new_ops


RULE = Rule(
    name="virtual_mode_frame_tracking_push_R_through_phase_gates",
    kind="rewrite",
    contract="exact",
    stage="physical",
    trigger=trigger,
    apply=apply,
    idea="R_a(theta)=exp(-i theta n_a) commutes with n_a and rotates a, a^+ by a c-number phase. Walking the routed "
         "circuit in time order, each R on a mode is deleted and folded into a pending per-mode frame angle; every "
         "subsequent gate touching that mode (D, CD, RB, BS/CBS) is re-parameterized by the exact conjugation "
         "identity (R^+ a R = e^{-i theta} a), while R/CR/CP on the same mode commute and pass through untouched. "
         "Any unrecognized gate on the mode forces a flush of the pending R just before it. At the end of the "
         "circuit one residual R per mode is emitted (omitted if it reduces to the identity mod 2 pi). This removes "
         "the compensating R's from every router SWAP block and the native R terms without adding or removing any "
         "two-qubit/qumode gate, so the 2-op count and critical structure are unchanged while the 1-op count and "
         "critical-path duration drop.",
    source="Hadamard-lemma conjugation of phase-space ISA gates by number-rotations; virtual frame / phase tracking "
           "technique as used for router SWAP compensating-rotation elimination (cf. Liu et al. 2407.10381 gate "
           "algebra; analogous to virtual-Z frame tracking in superconducting-qubit compilers)",
)
