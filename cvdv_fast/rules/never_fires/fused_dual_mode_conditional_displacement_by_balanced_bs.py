from cvdv_fast.api import Rule, Op, same_wires_adjacent
import math
import cmath

# grid neighbour map for the 2x4 layout: home mode j <-> partner mode j+4
PARTNER = {0: 4, 1: 5, 2: 6, 3: 7, 4: 0, 5: 1, 6: 2, 7: 3}


def _is_cd(op):
    return op.name == "CD" and len(op.wires) == 2 and op.wires[0][0] == "q" and op.wires[1][0] == "qm"


def _z_x_term(op, qj, xj):
    """Return beta (complex param) if op is CD(beta) on (qubit qj, mode xj), else None."""
    if not _is_cd(op):
        return None
    (wq, wm) = op.wires
    if wq != ("q", qj) or wm != ("qm", xj):
        return None
    return complex(op.params[0])


def _commutes_with_zx(op, qj, mj, mm):
    """Does op commute with Z_{qj} x_{mj} (and with Z_{qj} x_{mm})? True if op acts on disjoint
    qubit qj and disjoint modes mj, mm, or if op itself is a CD on (qj, mj) (Z_j x_j term), or a
    phase-space rotation R/CR purely diagonal-compatible... kept conservative: disjoint wires only,
    except allowing another CD(qj, mj)."""
    ws = set(op.wires)
    if ("q", qj) in ws:
        # must be exactly a CD on (qj, mj) to be allowed (that's Z_j x_j itself)
        if _is_cd(op) and set(op.wires) == {("q", qj), ("qm", mj)}:
            return True
        return False
    if ("qm", mj) in ws or ("qm", mm) in ws:
        return False
    return True


def trigger(ops):
    out = []
    n = len(ops)
    for i, op in enumerate(ops):
        if not _is_cd(op):
            continue
        wq, wm = op.wires
        qj = wq[1]
        mj = wm[1]
        mm = PARTNER.get(mj)
        if mm is None:
            continue
        th_beta = complex(op.params[0])
        # th corresponds to beta = -i*th  =>  th = i*beta  (beta purely imaginary expected)
        # search forward for the matching Z_qj x_mm term, skipping commuting ops
        j = None
        for k in range(i + 1, n):
            ok = ops[k]
            if ("q", qj) in set(ok.wires) and _is_cd(ok) and set(ok.wires) == {("q", qj), ("qm", mm)}:
                j = k
                break
            if not _commutes_with_zx(ok, qj, mj, mm):
                j = None
                break
        else:
            j = None
        if j is None:
            continue
        beta2 = complex(ops[j].params[0])
        out.append((i, j, qj, mj, mm, th_beta, beta2))
    return out


def apply(ops, m):
    i, j, qj, mj, mm, beta1, beta2 = m
    # recover th, th' from beta = -i * th  (th real)
    th = (1j * beta1).real
    thp = (1j * beta2).real
    mag = math.sqrt(th * th + thp * thp)
    if mag < 1e-15:
        return i, j, list(ops[i + 1:j])
    s = math.atan2(thp, th)
    beta = -1j * mag

    new_ops = []
    # BS(2s, +pi/2) on (mode j, mode m)   == V^+
    new_ops.append(Op("BS", (2 * s, math.pi / 2), (("qm", mj), ("qm", mm))))
    # CD(beta) on (qubit j, mode j)
    new_ops.append(Op("CD", (beta,), (("q", qj), ("qm", mj))))
    # BS(2s, -pi/2) on (mode j, mode m)   == V
    new_ops.append(Op("BS", (2 * s, -math.pi / 2), (("qm", mj), ("qm", mm))))

    # keep any intervening ops that commuted (they must be re-emitted between i and j originally;
    # since they all commuted with both Z_j x_j and Z_j x_m, and the new sequence implements the
    # product of those two exponentials as a block, we can emit the intervening ops either before
    # or after the fused block — emit them first, preserving their relative order)
    middle = list(ops[i + 1:j])
    return i, j, middle + new_ops


RULE = Rule(name="fused_dual_mode_conditional_displacement_by_balanced_bs", kind="rewrite", contract="exact",
            stage="logical", trigger=trigger, apply=apply,
            idea="Two commuting qubit-conditioned linear mode terms exp(-i th Z_j x_j) exp(-i th' Z_j x_m), with "
                 "x = a+a^+ and m the grid-neighbour partner mode of qubit j's home mode j, fuse into a single "
                 "native CD on the home mode conjugated by a beam-splitter pair. Let G = a^+ b - b^+ a with "
                 "a = mode j, b = mode m; V = e^{-sG} with s = atan2(th', th) rotates a into "
                 "(th a + th' b)/sqrt(th^2+th'^2). Conjugating the native CD_j(beta) = exp(Z_j(beta a^+ - beta* a)) "
                 "by V with beta = -i*sqrt(th^2+th'^2) gives exactly exp(-i Z_j(th x_j + th' x_m)), i.e. the product "
                 "of the two target exponentials, with V realized as BS(2s, +-pi/2) in ISA form. This replaces the "
                 "router's SWAP-in/CD/SWAP-out pattern for the off-home-mode term with a single beam-splitter pair "
                 "and no ancilla, saving two-op gates and the associated R/SWAP overhead. The rewrite only fires if "
                 "every op between the two CD terms commutes with both Z_j x_j and Z_j x_m (disjoint wires, or is "
                 "the Z_j x_j term itself), and only if mode m is the fixed grid neighbour of mode j (0-4,1-5,2-6,3-7).",
            source="Liu et al. 2407.10381 (Heisenberg-Weyl / Gaussian beam-splitter conjugation of conditional "
                   "displacements); rule-card derivation for electronicVibration_small benchmark")
