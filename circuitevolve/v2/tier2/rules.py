"""Tier-2 executable rewrite rules: pattern -> replacement templates over qubit VARIABLES a, b, c, d.

DSL (literal, regex-parsed; never exec/eval)::

    RULE merge_tt
    PATTERN: t a; t a
    REPLACE: s a
    SIDE: commute            # optional; one of SIDE_CONDITIONS (default 'commute')
    END

Gates: h s sdg t tdg x z (one variable), cx cz (two distinct variables). `REPLACE:` may be empty or `id`.

Side conditions (fixed set):
    'commute'     commutation-aware matching over the circuit: unmatched gates between matched ones are allowed
                  if they can be moved out of the way using the fixed commutation table (`commute.py`).
    'contiguous'  no unmatched gate touching a matched qubit may lie between the matched gates.

Soundness: a rule is VERIFIED ONCE, as an exact unitary identity up to a global phase on its k <= 4 qubits, with
`circuitevolve.v2.verify.verify(..., mode='exact')` (frozen D[omega] simulator, exhaustive over all 2^k basis
inputs: a proof, `certified=True`). Only verified rules enter a library. A verified identity U_pat = c U_rep
applied anywhere (after moving commuting gates out of the way) leaves the whole-circuit unitary unchanged up to the
same global phase, so applications need no per-application proof; `apply.py` still offers whole-circuit guards.

Termination: a rule must strictly DECREASE (T-count, total gates) lexicographically, so every application
decreases a well-founded measure and fixpoint iteration terminates.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from .commute import ARITY, GATES, T_GATES

VARS = ("a", "b", "c", "d")
SIDE_CONDITIONS = ("commute", "contiguous")
MAX_PATTERN = 20
MAX_REPLACE = 20

_GATE_RE = re.compile(r"^([a-z]+)\s+([a-d](?:\s*,?\s*[a-d])*)$")
_RULE_RE = re.compile(r"RULE\s+([A-Za-z0-9_\-\.]+)\s*\n(.*?)\nEND\b", re.S)


class RuleError(ValueError):
    """A rule is malformed (syntax, gate set, arity, cost, connectivity)."""


def parse_seq(text: str) -> tuple:
    """'t a; cx a b' -> (('t', ('a',)), ('cx', ('a', 'b'))). Empty / 'id' -> ()."""
    text = text.strip()
    if text in ("", "id", "I", "identity", "()", "[]"):
        return ()
    out = []
    for part in re.split(r"[;\n]", text):
        part = part.strip().lower()
        if not part:
            continue
        m = _GATE_RE.match(part)
        if not m:
            raise RuleError(f"cannot parse gate {part!r}")
        g = m.group(1)
        vs = tuple(re.findall(r"[a-d]", m.group(2)))
        if g not in GATES:
            raise RuleError(f"gate {g!r} not allowed (allowed: {' '.join(GATES)})")
        if len(vs) != ARITY[g]:
            raise RuleError(f"gate {g!r} takes {ARITY[g]} variable(s), got {vs}")
        if len(set(vs)) != len(vs):
            raise RuleError(f"gate {part!r} repeats a variable")
        out.append((g, vs))
    return tuple(out)


def seq_text(seq) -> str:
    return "; ".join(f"{g} {' '.join(v)}" for g, v in seq) if seq else "id"


def seq_cost(seq) -> tuple:
    """(T-count, total gates)."""
    return (sum(1 for g, _ in seq if g in T_GATES), len(seq))


@dataclass
class Rule:
    name: str
    pattern: tuple
    replacement: tuple
    side: str = "commute"
    source: str = ""                       # 'llm' | 'control' | 'seed' | 'test'
    meaning: str = ""                      # one-line meaning (LLM-provided or generated)
    proof: dict = field(default_factory=dict)

    # ----------------------------------------------------------------------------- structure
    @property
    def variables(self) -> tuple:
        seen = []
        for _, vs in self.pattern:
            for v in vs:
                if v not in seen:
                    seen.append(v)
        return tuple(seen)

    @property
    def k(self) -> int:
        return len(self.variables)

    def cost_delta(self) -> tuple:
        (tp, gp), (tr, gr) = seq_cost(self.pattern), seq_cost(self.replacement)
        return (tp - tr, gp - gr)

    def key(self) -> tuple:
        """Content key (canonical variable naming by first appearance)."""
        ren = {v: VARS[i] for i, v in enumerate(self.variables)}
        f = lambda seq: tuple((g, tuple(ren[v] for v in vs)) for g, vs in seq)
        return (f(self.pattern), f(self.replacement), self.side)

    def canonical(self) -> "Rule":
        p, r, s = self.key()
        return Rule(self.name, p, r, s, self.source, self.meaning, dict(self.proof))

    def check_wellformed(self) -> None:
        if not self.pattern:
            raise RuleError("empty pattern")
        if len(self.pattern) > MAX_PATTERN or len(self.replacement) > MAX_REPLACE:
            raise RuleError(f"pattern/replacement longer than {MAX_PATTERN}/{MAX_REPLACE} gates")
        if self.side not in SIDE_CONDITIONS:
            raise RuleError(f"side condition {self.side!r} not in {SIDE_CONDITIONS}")
        pv = set(self.variables)
        if any(v not in VARS for v in pv):
            raise RuleError("variables must be a, b, c, d")
        rv = {v for _, vs in self.replacement for v in vs}
        if not rv <= pv:
            raise RuleError(f"replacement uses variables {sorted(rv - pv)} absent from the pattern")
        bound = set(self.pattern[0][1])
        for g, vs in self.pattern[1:]:
            if not (set(vs) & bound):
                raise RuleError(f"pattern not connected: gate {g} {' '.join(vs)} shares no variable with earlier "
                                f"gates (reorder the pattern so each gate touches an earlier variable)")
            bound |= set(vs)
        if seq_cost(self.replacement) >= seq_cost(self.pattern):
            raise RuleError(f"replacement cost {seq_cost(self.replacement)} is not lexicographically below the "
                            f"pattern cost {seq_cost(self.pattern)} (T, gates)")

    # ----------------------------------------------------------------------------- serialization
    def to_dict(self) -> dict:
        return dict(name=self.name, pattern=seq_text(self.pattern), replacement=seq_text(self.replacement),
                    side=self.side, source=self.source, meaning=self.meaning, proof=dict(self.proof))

    @staticmethod
    def from_dict(d: dict) -> "Rule":
        return Rule(d["name"], parse_seq(d["pattern"]), parse_seq(d["replacement"]), d.get("side", "commute"),
                    d.get("source", ""), d.get("meaning", ""), dict(d.get("proof", {})))

    def dsl(self) -> str:
        s = f"RULE {self.name}\nPATTERN: {seq_text(self.pattern)}\nREPLACE: {seq_text(self.replacement)}\n"
        if self.side != "commute":
            s += f"SIDE: {self.side}\n"
        return s + "END"


def parse_rules(text: str, source: str = "") -> tuple[list, list]:
    """Parse every RULE ... END block. Returns (rules, errors) — errors are (name, message) for blocks that do not
    parse; well-formedness (cost, connectivity) is checked later by verify_rule."""
    rules, errors = [], []
    for m in _RULE_RE.finditer(text.replace("\r", "")):
        name, body = m.group(1), m.group(2)
        fields = {}
        for line in body.splitlines():
            line = line.split("#", 1)[0].strip()
            mm = re.match(r"^(PATTERN|REPLACE|SIDE|MEANING)\s*:\s*(.*)$", line, re.I)
            if mm:
                fields[mm.group(1).upper()] = mm.group(2).strip()
        try:
            if "PATTERN" not in fields or "REPLACE" not in fields:
                raise RuleError("missing PATTERN: or REPLACE: line")
            rules.append(Rule(name, parse_seq(fields["PATTERN"]), parse_seq(fields["REPLACE"]),
                              fields.get("SIDE", "commute").strip().lower() or "commute", source,
                              fields.get("MEANING", "")))
        except RuleError as e:
            errors.append((name, str(e)))
    return rules, errors


# ================================================================================================ verification
def _ops(seq, var_index) -> list:
    return [(g, tuple(var_index[v] for v in vs), None) for g, vs in seq]


VERIFY_COUNTER = {"calls": 0}


def verify_rule(rule: Rule) -> dict:
    """Verify ONCE: well-formedness, then exact unitary identity up to global phase on k qubits.

    Returns dict(ok, reason, method, certified, global_phase). Never raises for a bad rule."""
    VERIFY_COUNTER["calls"] += 1
    try:
        rule.check_wellformed()
    except RuleError as e:
        return dict(ok=False, reason=f"malformed: {e}", method="literal", certified=False)
    from ..verify import verify
    idx = {v: i for i, v in enumerate(rule.variables)}
    k = len(idx)
    v = verify((_ops(rule.replacement, idx), k), (_ops(rule.pattern, idx), k), mode="exact")
    out = dict(ok=bool(v.ok and v.certified), reason=v.reason if not v.ok else ("" if v.certified else
               "not certified"), method=v.method, certified=bool(v.certified), k=k)
    if v.ok and "global_phase" in v.details:
        gp = complex(v.details["global_phase"])
        out["global_phase"] = [round(gp.real, 12), round(gp.imag, 12)]
    if not out["ok"] and out["reason"] and "differ" not in out["reason"]:
        out["reason"] = "not an identity: " + out["reason"]
    return out


# ================================================================================================ library
@dataclass
class Library:
    rules: list = field(default_factory=list)
    version: str = "v0"
    parent_sha: str | None = None
    meta: dict = field(default_factory=dict)

    def content(self) -> list:
        return [[seq_text(p), seq_text(r), s] for p, r, s in (x.key() for x in self.rules)]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.content(), separators=(",", ":")).encode()).hexdigest()

    def keys(self) -> set:
        return {r.key() for r in self.rules}

    def extended(self, new_rules, version: str, meta: dict | None = None) -> "Library":
        return Library(list(self.rules) + list(new_rules), version, self.sha256, dict(meta or {}))

    def to_json(self) -> dict:
        return dict(format="circuitevolve.v2.tier2.library/1", version=self.version, sha256=self.sha256,
                    parent_sha256=self.parent_sha, n_rules=len(self.rules), meta=self.meta,
                    rules=[r.to_dict() for r in self.rules])

    def save(self, path) -> str:
        d = self.to_json()
        with open(path, "w") as f:
            json.dump(d, f, indent=1)
        return d["sha256"]

    @staticmethod
    def load(path, reverify: bool = True) -> "Library":
        with open(path) as f:
            d = json.load(f)
        lib = Library([Rule.from_dict(x) for x in d["rules"]], d.get("version", "?"), d.get("parent_sha256"),
                      d.get("meta", {}))
        if d.get("sha256") and d["sha256"] != lib.sha256:
            raise ValueError(f"library {path}: stored sha256 {d['sha256']} != content sha256 {lib.sha256}")
        if reverify:
            for r in lib.rules:
                res = verify_rule(r)
                if not res["ok"]:
                    raise ValueError(f"library {path}: rule {r.name} fails verification: {res['reason']}")
        return lib

    def markdown(self) -> str:
        lines = [f"# Tier-2 rule library {self.version}", "", f"SHA-256 `{self.sha256}`; parent "
                 f"`{self.parent_sha}`; {len(self.rules)} rules (applied in this order).", "",
                 "| # | name | pattern | replacement | dT | dgates | side | source | meaning |",
                 "|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(self.rules, 1):
            dt, dg = r.cost_delta()
            lines.append(f"| {i} | {r.name} | `{seq_text(r.pattern)}` | `{seq_text(r.replacement)}` | -{dt} | -{dg} "
                         f"| {r.side} | {r.source} | {r.meaning} |")
        return "\n".join(lines) + "\n"
