"""No-LLM control: Quartz-style enumeration of short Clifford+T identities (RepGen-like).

For k qubits, all gate sequences over the tier-2 gate set are generated level by level, extending only class
REPRESENTATIVES (the cheapest sequence found so far for each unitary-up-to-global-phase). A sequence whose
unitary is already represented by a strictly cheaper sequence (T, gates) yields a candidate identity
`sequence -> representative`. Candidates are kept only if they are minimal (prefix and suffix are representatives,
so no shorter sub-identity explains them) and connected. Classes are keyed by a floating-point FINGERPRINT
(phase-normalized, rounded unitary) — this is only a proposal mechanism: every candidate that is used is verified
exactly with `rules.verify_rule` (the same once-per-rule proof as LLM rules, counted in the same budget).

Optionally, random longer sequences (`random_lookup`) are looked up against the representative table, finding
cheaper equivalents beyond the exhaustive depth.
"""
from __future__ import annotations

import itertools
import random

import numpy as np

from .commute import GATES, ONE_Q, T_GATES
from .rules import VARS, Rule, seq_cost

_M1 = {
    "h": np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2),
    "x": np.array([[0, 1], [1, 0]], dtype=complex),
    "z": np.diag([1, -1]).astype(complex),
    "s": np.diag([1, 1j]),
    "sdg": np.diag([1, -1j]),
    "t": np.diag([1, np.exp(1j * np.pi / 4)]),
    "tdg": np.diag([1, np.exp(-1j * np.pi / 4)]),
}


def alphabet(k: int) -> list:
    out = [(g, (VARS[q],)) for q in range(k) for g in ONE_Q]
    for a, b in itertools.permutations(range(k), 2):
        out.append(("cx", (VARS[a], VARS[b])))
    for a, b in itertools.combinations(range(k), 2):
        out.append(("cz", (VARS[a], VARS[b])))
    return out


def gate_matrix(g, k: int) -> np.ndarray:
    """Dense 2^k matrix, qubit q = bit q of the index (little-endian)."""
    name, vs = g
    qs = [VARS.index(v) for v in vs]
    d = 2 ** k
    M = np.zeros((d, d), dtype=complex)
    for x in range(d):
        bits = [(x >> q) & 1 for q in range(k)]
        if name in _M1:
            q = qs[0]
            for y in (0, 1):
                amp = _M1[name][y, bits[q]]
                if amp != 0:
                    nb = list(bits)
                    nb[q] = y
                    M[sum(b << i for i, b in enumerate(nb)), x] += amp
        elif name == "cx":
            nb = list(bits)
            if bits[qs[0]]:
                nb[qs[1]] ^= 1
            M[sum(b << i for i, b in enumerate(nb)), x] = 1
        elif name == "cz":
            M[x, x] = -1 if bits[qs[0]] and bits[qs[1]] else 1
    return M


def fingerprint(U: np.ndarray) -> bytes:
    f = U.reshape(-1)
    i = int(np.argmax(np.abs(f) > 1e-6))
    ph = f[i] / abs(f[i])
    v = np.round(f / ph, 6) + 0.0
    return v.real.tobytes() + v.imag.tobytes()


def _connected(seq) -> bool:
    bound = set(seq[0][1])
    for _, vs in seq[1:]:
        if not set(vs) & bound:
            return False
        bound |= set(vs)
    return True


def enumerate_identities(k: int, max_len: int, max_reps: int = 400000, seed: int = 0) -> dict:
    """Return dict(reps={fp: seq}, identities=[(seq, rep)], levels=[#reps per level])."""
    alph = alphabet(k)
    mats = {g: gate_matrix(g, k) for g in alph}
    I = np.eye(2 ** k, dtype=complex)
    table = {fingerprint(I): ((), I)}           # fp -> (seq, U)
    frontier = [((), I)]
    identities, levels = [], []
    for L in range(1, max_len + 1):
        nxt = []
        for seq, U in frontier:
            for g in alph:
                s2 = seq + (g,)
                U2 = mats[g] @ U
                fp = fingerprint(U2)
                hit = table.get(fp)
                if hit is None:
                    table[fp] = (s2, U2)
                    nxt.append((s2, U2))
                elif seq_cost(hit[0]) < seq_cost(s2):
                    identities.append((s2, hit[0]))
                elif seq_cost(s2) < seq_cost(hit[0]):        # a cheaper (fewer-T) representative appeared
                    identities.append((hit[0], s2))
                    table[fp] = (s2, U2)
                    nxt.append((s2, U2))
        levels.append(len(nxt))
        frontier = nxt
        if len(table) > max_reps:
            break
    rep_of = {fp: s for fp, (s, _) in table.items()}
    keep = []
    for s, r in identities:
        if not _connected(s):
            continue
        if len(s) >= 2:
            # minimal: neither the prefix nor the suffix is itself reducible to something strictly cheaper
            red = False
            for sub in (s[:-1], s[1:]):
                U = np.eye(2 ** k, dtype=complex)
                for g in sub:
                    U = mats[g] @ U
                hit = table.get(fingerprint(U))
                if hit is not None and seq_cost(hit[0]) < seq_cost(sub):
                    red = True
                    break
            if red:
                continue
        keep.append((s, r))
    return dict(reps=rep_of, identities=keep, levels=levels, table=table, mats=mats, k=k)


def random_lookup(enum: dict, n_samples: int, length_range=(5, 7), seed: int = 0) -> list:
    """Random connected sequences of the given lengths whose unitary is in the table with a cheaper rep."""
    rng = random.Random(seed)
    alph = list(enum["mats"])
    out = []
    for _ in range(n_samples):
        L = rng.randint(*length_range)
        seq = [rng.choice(alph)]
        while len(seq) < L:
            g = rng.choice(alph)
            if set(g[1]) & {v for _, vs in seq for v in vs}:
                seq.append(g)
        seq = tuple(seq)
        U = np.eye(2 ** enum["k"], dtype=complex)
        for g in seq:
            U = enum["mats"][g] @ U
        hit = enum["table"].get(fingerprint(U))
        if hit is not None and seq_cost(hit[0]) < seq_cost(seq):
            out.append((seq, hit[0]))
    return out


def canonical_rule(seq, rep, source="control", name=None) -> Rule:
    r = Rule(name or "", tuple(seq), tuple(rep), "commute", source)
    r = r.canonical()
    dt, dg = r.cost_delta()
    r.meaning = f"enumerated identity (T -{dt}, gates -{dg})"
    return r


def candidate_pool(specs=((1, 8), (2, 5), (3, 3)), random_samples: int = 0, seed: int = 0) -> list:
    """Deduplicated candidate rules from several (k, max_len) enumerations (+ optional random lookups)."""
    seen, pool = set(), []
    for k, L in specs:
        e = enumerate_identities(k, L)
        ids = list(e["identities"])
        if random_samples and k >= 2:
            ids += random_lookup(e, random_samples, seed=seed)
        for s, r in ids:
            rule = canonical_rule(s, r)
            if rule.key() in seen:
                continue
            seen.add(rule.key())
            pool.append(rule)
    return pool
