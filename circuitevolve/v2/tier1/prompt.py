"""Tier 1 prompt template (FROZEN for the evaluation phase; SHA-256 recorded in results/v2/tier1/FROZEN.md).

build_prompt(summary, lc, target, best, feedback, cards, classical) -> str
select_cards(summary, requested) -> [card stem]   deterministic: 2-3 cards from recognizer features + requested ones
"""
from __future__ import annotations

import json
import re

from ...blocks import REPO
from .plan import toolbox_text

PROMPT_VERSION = "tier1-prompt-v1"
CARDS_DIR = REPO / "docs" / "v2" / "cards"

TEMPLATE = """You choose a fault-tolerant COMPILATION STRATEGY for one logical reversible circuit (Toffoli level). A \
deterministic compiler executes your plan and an exact verifier checks the result against the logical circuit; \
only verified results count.

OBJECTIVE: minimise T-count (then qubits, then T-depth). Two separate leaderboards:
- EXACT: unitary-preserving on the same qubits (no measurement, no extra qubit, no zero-init promise).
- RELAXED: may use fresh clean ancillas, mid-circuit measurement + classically controlled fix-ups, and the declared \
zero-init promise; every ancilla must return to |0> and every measurement branch must act correctly with an \
input-independent phase.
THIS CALL TARGETS: {target}.

{summary}

{toolbox}

TECHNIQUE CARDS (index; ask for any by name with "request_cards"):
{index}

FULL CARDS:
{cards}

REFERENCE POINTS: naive {naive} T. Best classical EXACT T-count on record for this circuit (pyzx / TKET / Nam et \
al. / published optimizers, unitary-preserving): {classical}.

BEST VERIFIED SO FAR (this circuit):
{best}

RECENT RESULTS (newest last):
{feedback}

Reply with ONE JSON object and nothing else:
{{"target": "{target_l}", "decisions": [{{"element": "...", "route": "...", ...}}], "global_pass": "...", \
"request_cards": [], "rationale": "<= 3 sentences"}}
Unnamed Toffolis use toffoli_7T. Prefer changing something that has not been tried; do not resubmit a plan already \
listed above."""


def card_index() -> str:
    txt = (CARDS_DIR / "INDEX.md").read_text()
    rows = [l for l in txt.splitlines() if l.startswith("|")]
    out = []
    for l in rows:
        l = re.sub(r"\[([^\]]+)\]\(([^)]+)\.md\)", lambda m: f"{m.group(2)} ({m.group(1)})", l)
        out.append(l)
    return "\n".join(out)


def card_names() -> list:
    return sorted(p.stem for p in CARDS_DIR.glob("[0-9][0-9]_*.md"))


def resolve_card(name: str) -> str | None:
    name = str(name).strip().replace(".md", "")
    names = card_names()
    if name in names:
        return name
    m = re.match(r"^(\d{1,2})", name)
    if m:
        k = f"{int(m.group(1)):02d}"
        for n in names:
            if n.startswith(k + "_"):
                return n
    for n in names:
        if name.lower() in n.lower():
            return n
    return None


def select_cards(s, requested=(), k: int = 3) -> list:
    """Deterministic 2-3 most relevant cards from recognizer features, plus up to 2 requested ones."""
    score = {}
    cls = [p["cls"] for p in s.pairs]
    if cls.count("clean") or cls.count("controls_fixed"):
        score["01_gidney_temporary_and"] = 10 + cls.count("clean") + cls.count("controls_fixed")
    if cls.count("mirror") or cls.count("clean"):
        score["03_relative_phase_toffoli"] = 8 + cls.count("mirror")
    if s.unpaired:
        score["02_jones_toffoli_measurement"] = 6 + len(s.unpaired)
    if s.mcx:
        score["05_barenco_multicontrolled"] = 9 + len(s.mcx)
    if cls.count("controls_fixed") >= 2:
        score["06_cuccaro_ripple_carry"] = 7
    score.setdefault("08_pyzx_zx_simplification", 3)
    score.setdefault("07_phase_folding_tpar", 2)
    picked = [c for c, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))][:k]
    for r in list(requested)[:2]:
        rc = resolve_card(r)
        if rc and rc not in picked:
            picked.append(rc)
    return picked


def _fmt_best(best: dict) -> str:
    L = []
    for mode in ("exact", "relaxed"):
        b = best.get(mode)
        if b is None:
            L.append(f"- {mode}: none yet")
        else:
            L.append(f"- {mode}: T={b['t_count']} qubits={b['qubits']} meas={b['measurements']} "
                     f"T-depth={b['t_depth']} plan={json.dumps(b['plan_compact'])}")
    return "\n".join(L)


def _fmt_feedback(fb: list) -> str:
    if not fb:
        return "- none yet"
    return "\n".join(f"- call {f['call']} ({f['target']}): {f['text']}" for f in fb[-4:])


def build_prompt(s, lc, target: str, best: dict, feedback: list, cards: list, classical: str) -> str:
    body = "\n\n".join(f"### {c}\n" + (CARDS_DIR / f"{c}.md").read_text().strip() for c in cards)
    return TEMPLATE.format(target=target.upper(), target_l=target, summary=s.text(lc), toolbox=toolbox_text(),
                           index=card_index(), cards=body, naive=7 * len(s.toffolis), classical=classical,
                           best=_fmt_best(best), feedback=_fmt_feedback(feedback))


def compact_plan(plan: dict) -> dict:
    """Short form for the prompt: decisions grouped by route."""
    by = {}
    for d in plan.get("decisions", []):
        key = d["route"] + ("(via_ancilla)" if d.get("via_ancilla") else "") + \
            (f"(middle={d['middle']})" if d.get("route") == "ancilla_mcx" else "")
        by.setdefault(key, []).append(d["element"])
    return {"routes": by, "global_pass": plan.get("global_pass")}
