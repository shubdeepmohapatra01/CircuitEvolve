from cvdv_fast.api import Rule, Op
import math
import cmath


def synth(t, g, r):
    # exp(-i theta Z_j Z_k) (and XX/YY via basis change) using the co-located qumodes
    # m_j, m_k of the two qubits as a transient bus: a Heisenberg-Weyl closed loop in
    # mode m_j's phase space, with the bus state shuttled from m_j to m_k and back by a
    # full beam-splitter swap S = BS(pi,0) (S^4 = I), so mode m_k is left untouched.
    #   S^+ a S = -i b,  S^2 a S^{+2} = -a,  S^3 a S^{+3} = i b   (a = m_j, b = m_k)
    #   U = S CD_k(beta) S CD_j(alpha) S CD_k(beta) S CD_j(alpha)
    #     = D_a(-i B) D_a(-A) D_a(i B) D_a(A),  A = Z_j alpha, B = Z_k beta
    #     = exp(2 i alpha beta Z_j Z_k)  (via D(u)D(v)D(-u)D(-v) = exp(u v* - u* v)),
    # exact on both modes for any oscillator state (no truncation needed). No ancilla
    # qumode is allocated: m_j, m_k are the qumodes co-located with q_j, q_k (same site
    # index), so every two-mode gate is either co-located (CD) or acts on a neighbouring
    # mode pair (BS), and the router adds no SWAPs when m_j, m_k are grid neighbours.
    if t.kind != "pauli":
        return None
    if len(t.q) != 2 or len(t.label) != 2:
        return None
    label = t.label
    if label not in ("XX", "YY", "ZZ"):
        return None
    theta = t.theta
    if theta == 0:
        return None

    qj, qk = t.q
    mj = ("qm", qj[1])
    mk = ("qm", qk[1])

    def basis_in():
        for q, s in zip(t.q, label):
            if s == "X":
                g.h(q)
            elif s == "Y":
                g.sdg(q)
                g.h(q)

    def basis_out():
        for q, s in zip(t.q, label):
            if s == "X":
                g.h(q)
            elif s == "Y":
                g.h(q)
                g.s(q)

    alpha = math.sqrt(abs(theta) / 2.0)
    sign = 1.0 if theta >= 0 else -1.0
    beta = -sign * alpha

    basis_in()

    g.CD(alpha, qj, mj)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(beta, qk, mk)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(alpha, qj, mj)
    g.BS(math.pi, 0.0, mj, mk)
    g.CD(beta, qk, mk)
    g.BS(math.pi, 0.0, mj, mk)

    basis_out()


RULE = Rule(
    name="colocated_mode_swap_loop_pauli_zz",
    kind="synth",
    contract="exact",
    term_kinds=("pauli",),
    synth=synth,
    idea="exp(-i theta Z_j Z_k) (and XX/YY by single-qubit basis change) for neighbouring qubits via a "
         "Heisenberg-Weyl closed phase-space loop using no ancilla qumode: the bus state is shuttled between "
         "the two co-located qumodes m_j, m_k (one qumode per qubit site) by full beam-splitter swaps "
         "S = BS(pi,0), with S^4 = I. The sequence CD_j(alpha) S CD_k(beta) S CD_j(alpha) S CD_k(beta) S "
         "conjugates each CD_k displacement into mode m_j's frame (S^+ a S = -i b, S^2 a S^{+2} = -a, "
         "S^3 a S^{+3} = i b), closing a rectangle D_a(-iB) D_a(-A) D_a(iB) D_a(A) whose commutator phase "
         "D(u)D(v)D(-u)D(-v) = exp(u v* - u* v) gives exp(2i alpha beta Z_j Z_k) exactly, with mode m_k "
         "returned untouched (S^4 = I) and mode m_j returned to vacuum. Choosing alpha = sqrt(|theta|/2), "
         "beta = -sign(theta) * alpha gives exactly exp(-i theta Z_j Z_k). Every two-mode gate is either "
         "co-located (CD on q_j-m_j, q_k-m_k) or a BS on the neighbouring mode pair (m_j,m_k), so the router "
         "adds no SWAPs when m_j, m_k are grid neighbours.",
    source="Liu et al. 2407.10381, Heisenberg-Weyl displacement-commutator (geometric phase) construction, "
           "specialized to a swap-shuttled single co-located bus mode instead of a shared ancilla mode",
)
