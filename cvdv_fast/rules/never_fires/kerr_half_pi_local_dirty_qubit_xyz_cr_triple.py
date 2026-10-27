from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath


def _frame_pauli(sx, sy, sz):
    """Return 2x2 matrix for a*X + b*Y + c*Z style product tracking via simple matrix mult."""
    pass


def _mat_mul(a, b):
    return (
        (a[0][0] * b[0][0] + a[0][1] * b[1][0], a[0][0] * b[0][1] + a[0][1] * b[1][1]),
        (a[1][0] * b[0][0] + a[1][1] * b[1][0], a[1][0] * b[0][1] + a[1][1] * b[1][1]),
    )


_I = ((1, 0), (0, 1))
_X = ((0, 1), (1, 0))
_Y = ((0, -1j), (1j, 0))
_Z = ((1, 0), (0, -1))


def _rx(theta):
    c = math.cos(theta / 2)
    s = -1j * math.sin(theta / 2)
    return ((c, s), (s, c))


def _ry(theta):
    c = math.cos(theta / 2)
    s = math.sin(theta / 2)
    return ((c, -s), (s, c))


def _conj_pauli(frame_mat, pauli):
    # effective Pauli acting through conjugation: frame maps Z -> sigma, i.e. sigma = frame Z frame^+
    frame_dag = ((frame_mat[0][0].conjugate(), frame_mat[1][0].conjugate()),
                 (frame_mat[0][1].conjugate(), frame_mat[1][1].conjugate()))
    return _mat_mul(_mat_mul(frame_mat, pauli), frame_dag)


def _mat_scalar_of_product(mats):
    # multiply list of 2x2 matrices (in given order, mats[0] applied first in the product sigma3 sigma2 sigma1
    # convention used here: caller passes [sigma3, sigma2, sigma1] already in multiplication order)
    m = _I
    for mm in mats:
        m = _mat_mul(mm, m)
    return m


def synth(t, g, r):
    if t.kind != "n2":
        return None
    if len(t.q) < 1 or len(t.m) != 1:
        return None

    theta = t.theta
    # need theta = +-(pi/2 + k*pi)  i.e. theta mod pi close to pi/2
    tm = theta % math.pi
    dist = min(abs(tm - math.pi / 2), abs(tm - math.pi / 2 - math.pi), abs(tm - math.pi / 2 + math.pi))
    if dist > 1e-6:
        return None

    conj = theta < 0
    theta_abs = -theta if conj else theta
    # k such that theta_abs = pi/2 + k*pi  (k integer, nonnegative or negative as needed)
    k = round((theta_abs - math.pi / 2) / math.pi)
    residual = theta_abs - (math.pi / 2 + k * math.pi)
    if abs(residual) > 1e-6:
        return None

    q = t.q[0]
    m = t.m[0]

    # Determine sign c of sigma3 sigma2 sigma1 for the actual frame choice below.
    # Frame sequence (as emitted, time order):
    #   rx(-pi/2) ; ry(-pi/2)   -> frame F1 = ry(-pi/2) rx(-pi/2)   maps Z -> sigma1 (first CR's effective Pauli)
    #   then ry(pi/2)            -> frame F2 = ry(pi/2) F1          maps Z -> sigma2
    #   then rx(pi/2)            -> frame F3 = rx(pi/2) F2 = I      maps Z -> sigma3 = Z
    # matrix convention: if qubit state is acted on by gate matrices U1 then U2 (U1 first in time),
    # net unitary is U2 U1. The frame "seen" by CR at that point (conjugating Z back to the original basis)
    # is M such that effective_pauli = M Z M^+, where M is the net unitary applied so far (time order).
    F1 = _mat_mul(_ry(-math.pi / 2), _rx(-math.pi / 2))
    sigma1 = _conj_pauli(F1, _Z)

    F2 = _mat_mul(_ry(math.pi / 2), F1)
    sigma2 = _conj_pauli(F2, _Z)

    F3 = _mat_mul(_rx(math.pi / 2), F2)
    sigma3 = _conj_pauli(F3, _Z)

    # F3 should be identity (up to global phase); sigma3 should be Z (up to global phase sign)
    prod = _mat_scalar_of_product([sigma3, sigma2, sigma1])
    # prod should be c * I; extract c from the (0,0) entry
    c = prod[0][0]

    if abs(c - (-1j)) < 1e-6:
        phi0 = math.pi / 2
    elif abs(c - (1j)) < 1e-6:
        phi0 = 3 * math.pi / 2
    else:
        return None

    phi = phi0 + k * math.pi

    ops_signs = [-1.0, 1.0] if conj else [1.0]
    # we only need one overall conjugation; build the gate list then negate angles if conj

    def emit():
        g.rx(-math.pi / 2, q)
        g.ry(-math.pi / 2, q)
        g.CR(math.pi, q, m)
        g.ry(math.pi / 2, q)
        g.CR(math.pi, q, m)
        g.rx(math.pi / 2, q)
        g.CR(math.pi, q, m)
        g.R(phi, m)

    def emit_conj():
        g.rx(math.pi / 2, q)
        g.ry(math.pi / 2, q)
        g.CR(-math.pi, q, m)
        g.ry(-math.pi / 2, q)
        g.CR(-math.pi, q, m)
        g.rx(-math.pi / 2, q)
        g.CR(-math.pi, q, m)
        g.R(-phi, m)

    if conj:
        emit_conj()
    else:
        emit()


RULE = Rule(
    name="kerr_half_pi_local_dirty_qubit_xyz_cr_triple",
    kind="synth",
    contract="exact",
    term_kinds=("n2",),
    synth=synth,
    idea="exp(-i theta n^2) for theta = +-(pi/2 + k pi), using only the qubit co-located with the mode (dirty, "
         "no ancilla). Exact identity: n^2 mod 4 = n mod 2, so exp(-i(pi/2)n^2) = R(pi/2) * G with "
         "G = (-1)^{n(n-1)/2}. G is realized as a product of three CR(pi) gates conjugated into mutually "
         "anticommuting Pauli bases (X, Y, Z) via single-qubit frame rotations that compose to the identity "
         "overall, so U = C_X C_Y C_Z is a scalar multiple of the identity on the qubit for every Fock level n "
         "(scalar +-1 or +-i depending on n mod 4), leaving the qubit state untouched. The residual R(phi) on the "
         "mode absorbs the pi/2 vs 3pi/2 branch (sign of sigma3 sigma2 sigma1) plus the k*pi integer multiple. "
         "theta < 0 handled by conjugating (negating) the whole gate sequence.",
    source="Number theory n^2 mod 4 = n mod 2 (standard); CR(pi)=(-iZ)^n scalar-per-Fock-sector trick analogous to "
           "Liu et al. 2407.10381 displacement/rotation BCH tricks; local-dirty-qubit no-ancilla optimization "
           "motivated by avoiding router SWAPs for non-coupled ancilla qubits",
)
