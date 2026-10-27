from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def _basis_change(g, qs, labels, inverse):
    # X -> H, Y -> rx(-pi/2) going in; rx(pi/2) coming back out (forward order given; caller reverses for inverse)
    if not inverse:
        for q, s in zip(qs, labels):
            if s == "X":
                g.h(q)
            elif s == "Y":
                g.rx(-math.pi / 2, q)
    else:
        for q, s in zip(qs, labels):
            if s == "X":
                g.h(q)
            elif s == "Y":
                g.rx(math.pi / 2, q)


def _dressed_cd(g, dress_qs, core_q, alpha, m):
    # CP_{dress_qs} CD_core(alpha) CP_{dress_qs}^+ , built from CR(+-pi) conjugation (one extra qubit at a time).
    # Each dressing qubit multiplies the effective displacement coefficient by i (sign chosen via CR(-pi)...CR(pi)).
    for q in dress_qs:
        g.CR(-math.pi, q, m)
    g.CD(alpha, core_q, m)
    for q in dress_qs:
        g.CR(math.pi, q, m)


def _pauli_disp_core(g, qs, core_q, theta, alpha_disp, conj_disp, m):
    # even-weight Pauli string x displacement core: exp(-i theta (ZZ...Z) (alpha a^+ - alpha* a))
    # realized as CP-dressed CD on core_q with dress = qs (all qubits other than core_q), using (1):
    #   CP_j CD_k(a) CP_j^+ = Z_jZ_k ( (-i a) a^+ - (-i a)* a )
    # one dressing qubit flips direction by factor i (per qubit beyond the first paired qubit).
    w = len(qs) + 1
    extra = w - 1  # number of dressing CP's needed (all qubits except core)
    iw = (1j) ** extra
    beta = -alpha_disp if conj_disp else alpha_disp
    # we want Z_1..Z_w (beta a^+ - beta* a) with beta = alpha_disp (target).
    # identity gives factor i^{extra}: effective alpha' with -i*alpha' = i^{extra} * beta  =>  alpha' = i^{1-extra} * beta... 
    # instead directly solve for alpha s.t. (-i)^{extra} * alpha gives target beta:
    alpha = beta / ((-1j) ** extra)
    _dressed_cd(g, qs, core_q, alpha, m)


def synth(t, g, r):
    labels = t.label
    qs = t.q
    w = len(qs)
    if w < 2 or w % 2 != 0:
        return None
    if any(c not in ("X", "Y", "Z") for c in labels):
        return None

    if t.kind == "pauli_disp":
        if len(t.m) != 1:
            return None
        m = t.m[0]
        alpha = t.alpha
        # target: exp(- Z1Z2...Zw (alpha a^+ - alpha* a) ) on Z-dressed basis after basis change,
        # scaled so H_part = P * (alpha a^+ - alpha* a) matches pauli_disp convention directly:
        # we need Z-core coefficient equal to target alpha (post basis-change the string is all-Z).
        core_q = qs[-1]
        dress_qs = qs[:-1]

        _basis_change(g, qs, labels, inverse=False)
        _pauli_disp_core(g, dress_qs, core_q, None, alpha, False, m)
        _basis_change(g, qs, labels, inverse=True)
        return

    if t.kind == "pauli":
        # bus-mode geometric phase loop, built from CP-dressed CD instead of CP-wrapped D.
        a = g.anc_mode()
        theta = t.theta
        b = math.sqrt(abs(theta) / 2)
        gg = b if theta >= 0 else -b
        core_q = qs[-1]
        dress_qs = qs[:-1]
        extra = len(dress_qs)
        # alpha_b solves: dressed-CD with coefficient alpha_b realizes P * (b a^+ - b* a) exactly as in (1)/(2)
        # beta target = i*b  (so that CD_P(b) step matches bus loop convention: alpha = i*b)
        beta_b = 1j * b
        alpha_b = beta_b / ((-1j) ** extra)

        _basis_change(g, qs, labels, inverse=False)

        _dressed_cd(g, dress_qs, core_q, alpha_b, a)
        g.D(1j * gg, a)
        _dressed_cd(g, dress_qs, core_q, -alpha_b, a)
        g.D(-1j * gg, a)

        _basis_change(g, qs, labels, inverse=True)
        return

    return None


RULE = Rule(
    name="single_cp_conjugated_cd_pauli_string",
    kind="synth",
    contract="exact",
    term_kinds=("pauli_disp", "pauli"),
    synth=synth,
    idea=(
        "CP_j = CR(pi) = exp(-i pi/2 Z_j n) conjugation of a native CD turns one extra qubit into a Z-string "
        "extension: CP_j CD_k(alpha) CP_j^+ = exp(Z_jZ_k((-i alpha) a^+ - (-i alpha)* a)), each extra dressing "
        "qubit multiplying the effective displacement by a factor of i. For even-weight Pauli x displacement "
        "(pauli_disp) this realizes exp(-i theta Z-string (alpha a^+ - alpha* a)) with a single CD dressed by "
        "CP's on all-but-one qubit (3 two-op gates for weight 2, vs 4 for the CP/D/CP^+ sandwich), sandwiched "
        "between per-qubit X/Y basis changes (H for X, rx(+-pi/2) for Y). For two-qubit XX/YY (pauli kind) the "
        "same CP-dressed CD replaces the CP-wrapped D inside the bus-mode geometric-phase loop "
        "CD_P(b) D(ig) CD_P(-b) D(-ig) = exp(-2i b g P), dropping the two-op count per part from 8 to 6. All "
        "identities are exact BCH/conjugation relations on the full Fock space."
    ),
    source="Liu et al. 2407.10381 (Heisenberg-Weyl/CP conjugation identities); rule card single_cp_conjugated_cd_pauli_string",
)
