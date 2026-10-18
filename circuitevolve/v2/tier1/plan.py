"""Tier 1, part 2: the COMPILATION PLAN format, toolbox, and literal parser (json + regex; never exec/eval).

A plan (the LLM's reply, one JSON object, optionally inside a ```json fence):

    {"target": "exact" | "relaxed",
     "decisions": [
        {"element": "P0", "route": "temporary_and"},
        {"element": "P1", "route": "temporary_and", "via_ancilla": true},
        {"element": "P2", "route": "relative_phase_toffoli"},
        {"element": "T5", "route": "jones_toffoli"},
        {"element": "T6", "route": "clean_and"},
        {"element": "M0", "route": "ancilla_mcx", "middle": "jones"},
        {"element": "T3+T9", "route": "relative_phase_toffoli"},          # an explicit pair of Toffolis
        {"element": "T7", "route": "custom", "gates": ["h q3", "t q3", "cx q1 q3", ...]},
        {"element": "P4", "route": "custom", "first": [...], "second": [...]}
     ],
     "global_pass": "pyzx" | "tket" | "none" | "pyzx_then_tket",
     "request_cards": ["07_phase_folding_tpar"],
     "rationale": "..."}

Toffolis not named by any decision use 'toffoli_7T'. Custom gate DSL (one gate per string):
    h|s|sdg|t|tdg|x|z <q>          cx|cz <q>, <q>          measure <q> -> c<k>          if(c<k>) <gate>
with qubits q<int> (circuit qubit) or a<int> (a fresh clean ancilla local to the decision; it must be returned to
|0>; in a pair decision the same a<k> is shared by 'first' and 'second'), classical bits c<int> local to the decision.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

TOOLBOX_VERSION = "tier1-toolbox-v1"

# route -> (element kinds, verification mode, T cost, description shown to the LLM)
TOOLBOX = {
    "toffoli_7T": (("T",), "exact", "7 T", "standard exact Toffoli/CCZ decomposition (default for unnamed Toffolis)"),
    "relative_phase_toffoli": (("P", "TT"), "exact", "4 T each, 8 T per pair",
                               "Maslov RCCX (Toffoli up to a diagonal phase). ONLY valid on a PAIR whose second "
                               "member cancels the phase (mirror pairs: target only read in between). A single "
                               "Toffoli with this route is rejected."),
    "temporary_and": (("P", "TT"), "relaxed", "4 T per pair (compute 4 T, uncompute 0 T by X-measurement + CZ fix-up)",
                      "Gidney temporary AND. Default: computed directly into the pair's target, which must be a "
                      "declared zero-init qubit that is |0> before the pair and not written in between (class "
                      "'clean'); dirty targets are rejected by the verifier. With \"via_ancilla\": true the AND is "
                      "computed into a FRESH clean ancilla and cx(ancilla, target) is applied at both ends (needs "
                      "only unchanged controls: classes clean/mirror/controls_fixed). 1 measurement per pair."),
    "clean_and": (("T",), "relaxed", "4 T, no measurement",
                  "compute-only Gidney AND (no uncompute) into a target that is a declared zero-init qubit and |0> "
                  "just before this Toffoli (e.g. first write into an output register). ccx only."),
    "jones_toffoli": (("T",), "relaxed", "4 T + 1 fresh ancilla + 1 measurement",
                      "Jones 2013: AND into a fresh clean ancilla (4 T), cx/cz(ancilla, target), measurement-based "
                      "uncompute (0 T). Works for any single ccx or ccz."),
    "ancilla_mcx": (("M",), "relaxed", "4 T per work AND, middle 4 T (jones) or 7 T",
                    "multi-controlled X cascade: every enclosing pair -> temporary_and (direct if clean, else "
                    "via_ancilla), middle Toffoli -> jones_toffoli (\"middle\": \"jones\", default) or toffoli_7T "
                    "(\"middle\": \"7T\")."),
    "barenco_mcx": (("M",), "exact", "8 T per enclosing pair, middle 7 T",
                    "multi-controlled X cascade kept unitary: enclosing pairs -> relative_phase_toffoli, middle -> "
                    "toffoli_7T (Barenco/Maslov with borrowed work qubits)."),
    "custom": (("T", "P", "TT"), "auto", "count of t/tdg in the gate list",
               "your own construction for ONE element in the gate DSL (Clifford+T + measurement + feed-forward)."),
}
GLOBAL_PASSES = ("pyzx", "tket", "none", "pyzx_then_tket")
TARGETS = ("exact", "relaxed")


class PlanError(ValueError):
    """Malformed plan (bad JSON, unknown route/element, bad DSL)."""


@dataclass
class DSLGate:
    name: str
    qubits: tuple          # tokens: ('q', int) or ('a', int)
    cbit: int | None = None       # measure: local classical bit written
    cond: int | None = None       # if(c<k>): local classical bit


@dataclass
class Decision:
    element: str
    route: str
    via_ancilla: bool = False
    middle: str = "jones"
    gates: list = field(default_factory=list)      # custom single: [DSLGate]
    first: list = field(default_factory=list)      # custom pair
    second: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = dict(element=self.element, route=self.route)
        if self.via_ancilla:
            d["via_ancilla"] = True
        if self.route == "ancilla_mcx":
            d["middle"] = self.middle
        for k in ("gates", "first", "second"):
            v = getattr(self, k)
            if v:
                d[k] = [dsl_text(g) for g in v]
        return d


@dataclass
class Plan:
    decisions: list
    global_pass: str = "none"
    target: str = ""
    request_cards: list = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict:
        return dict(target=self.target, decisions=[d.to_dict() for d in self.decisions],
                    global_pass=self.global_pass, request_cards=list(self.request_cards), rationale=self.rationale)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=1)


# ============================================================================================ DSL
_Q = r"(q\[?\d+\]?|a\[?\d+\]?)"
_RE_1Q = re.compile(rf"^(h|s|sdg|t|tdg|x|z)\s+{_Q}$")
_RE_2Q = re.compile(rf"^(cx|cz)\s+{_Q}\s*(?:,|\s)\s*{_Q}$")
_RE_MEAS = re.compile(rf"^measure\s+{_Q}\s*->\s*c\[?(\d+)\]?$")
_RE_IF = re.compile(r"^if\s*\(\s*c\[?(\d+)\]?\s*(?:==\s*1\s*)?\)\s*(.+)$")


def _qtok(s: str) -> tuple:
    m = re.match(r"^([qa])\[?(\d+)\]?$", s.strip())
    if not m:
        raise PlanError(f"bad qubit token {s!r}")
    return (m.group(1), int(m.group(2)))


def parse_dsl_gate(text: str) -> DSLGate:
    s = " ".join(str(text).strip().rstrip(";").split())
    s = s.replace(" ,", ",")
    m = _RE_IF.match(s)
    if m:
        inner = parse_dsl_gate(m.group(2))
        if inner.name == "measure" or inner.cond is not None:
            raise PlanError(f"conditional measure / nested if not allowed: {text!r}")
        inner.cond = int(m.group(1))
        return inner
    m = _RE_MEAS.match(s)
    if m:
        return DSLGate("measure", (_qtok(m.group(1)),), cbit=int(m.group(2)))
    m = _RE_1Q.match(s)
    if m:
        return DSLGate(m.group(1), (_qtok(m.group(2)),))
    m = _RE_2Q.match(s)
    if m:
        a, b = _qtok(m.group(2)), _qtok(m.group(3))
        if a == b:
            raise PlanError(f"two-qubit gate on one qubit: {text!r}")
        return DSLGate(m.group(1), (a, b))
    raise PlanError(f"cannot parse DSL gate {text!r} (allowed: h s sdg t tdg x z <q>; cx/cz <q>,<q>; "
                    f"measure <q> -> c<k>; if(c<k>) <gate>)")


def dsl_text(g: DSLGate) -> str:
    qs = ", ".join(f"{k}{i}" for k, i in g.qubits)
    s = f"measure {qs} -> c{g.cbit}" if g.name == "measure" else f"{g.name} {qs}"
    return f"if(c{g.cond}) {s}" if g.cond is not None else s


def parse_dsl(lines) -> list:
    if isinstance(lines, str):
        lines = [l for l in re.split(r"[;\n]", lines) if l.strip()]
    if not isinstance(lines, list) or len(lines) > 400:
        raise PlanError("custom gate list must be a list of <= 400 strings")
    return [parse_dsl_gate(l) for l in lines]


# ============================================================================================ plan parsing
def _extract_json(text: str) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise PlanError("empty reply")
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    cands = [m.group(1)] if m else []
    # first balanced {...} block
    start = text.find("{")
    if start >= 0:
        depth, in_str, esc = 0, False, False
        for k in range(start, len(text)):
            ch = text[k]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    cands.append(text[start:k + 1])
                    break
    errs = []
    for c in cands:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError as e:
            errs.append(str(e))
    raise PlanError("no parseable JSON object in reply" + (f" ({errs[0]})" if errs else ""))


_ELEM = re.compile(r"^(T\d+|P\d+|M\d+|T\d+\+T\d+)$")


def parse_plan(text_or_obj) -> Plan:
    obj = text_or_obj if isinstance(text_or_obj, dict) else _extract_json(text_or_obj)
    decs = obj.get("decisions", [])
    if not isinstance(decs, list):
        raise PlanError("'decisions' must be a list")
    gp = str(obj.get("global_pass", "none")).strip().lower()
    if gp not in GLOBAL_PASSES:
        raise PlanError(f"global_pass {gp!r} not in {GLOBAL_PASSES}")
    out = []
    for k, d in enumerate(decs):
        if not isinstance(d, dict):
            raise PlanError(f"decision {k} is not an object")
        el = str(d.get("element", "")).replace(" ", "")
        route = str(d.get("route", "")).strip()
        if not _ELEM.match(el):
            raise PlanError(f"decision {k}: bad element {el!r} (T<k>, P<k>, M<k> or T<i>+T<j>)")
        if route not in TOOLBOX:
            raise PlanError(f"decision {k}: unknown route {route!r}; toolbox: {sorted(TOOLBOX)}")
        kind = "TT" if "+" in el else el[0]
        if kind not in TOOLBOX[route][0]:
            raise PlanError(f"decision {k}: route {route!r} does not apply to element {el!r} "
                            f"(applies to {TOOLBOX[route][0]})"
                            + (" - relative_phase_toffoli needs a cancelling partner: use a pair element"
                               if route == "relative_phase_toffoli" else ""))
        dec = Decision(el, route, via_ancilla=bool(d.get("via_ancilla", False)),
                       middle=str(d.get("middle", "jones")).lower())
        if dec.middle not in ("jones", "7t"):
            raise PlanError(f"decision {k}: middle must be 'jones' or '7T'")
        if route == "custom":
            if kind == "T":
                dec.gates = parse_dsl(d.get("gates", []))
                if not dec.gates:
                    raise PlanError(f"decision {k}: custom needs a non-empty 'gates' list")
            else:
                dec.first, dec.second = parse_dsl(d.get("first", [])), parse_dsl(d.get("second", []))
                if not dec.first and not dec.second:
                    raise PlanError(f"decision {k}: custom pair needs 'first' and 'second' gate lists")
        out.append(dec)
    rc = obj.get("request_cards", [])
    rc = [str(x) for x in rc][:3] if isinstance(rc, list) else []
    tgt = str(obj.get("target", "")).lower()
    return Plan(out, gp, tgt if tgt in TARGETS else "", rc, str(obj.get("rationale", ""))[:2000])


def toolbox_text() -> str:
    L = [f"TOOLBOX ({TOOLBOX_VERSION}). Routes: name [applies to] (verification mode; T cost): description"]
    for r, (kinds, mode, cost, desc) in TOOLBOX.items():
        L.append(f"- {r} [{'/'.join(kinds).replace('TT', 'Ti+Tj')}] ({mode}; {cost}): {desc}")
    L.append("Global pass after routing (applied to every measurement-free segment, kept only where it lowers T): "
             + ", ".join(GLOBAL_PASSES) + ".")
    L.append("Custom gate DSL, one gate per string: 'h|s|sdg|t|tdg|x|z q<i>', 'cx|cz q<i>, q<j>', "
             "'measure q<i> -> c<k>', 'if(c<k>) <gate>'; a<k> = fresh clean ancilla local to the decision (must end "
             "in |0>), c<k> = local classical bit. Element T<k>: key 'gates' replaces that Toffoli; pair element: "
             "keys 'first' and 'second' replace its two Toffolis.")
    return "\n".join(L)
