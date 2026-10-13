"""Self-evolving rule file ("playbook") for the LLM proposer.

The model weights are fixed, so the part of the system we can adapt is the context the proposer
sees. A Playbook is a persistent list of short natural-language rules ("lessons") that is rendered
into every proposer prompt and updated during search:

  Generator  - the proposer (search/llm.py) writes programs, with the active rules in its prompt.
  Reflector  - every few batches, an LLM reads recent verifier outcomes (improvements with their
               parent -> child edit, rejections with the verifier's reason) and proposes at most a
               few DELTAS: add a rule, edit a rule, retire a rule. It never rewrites the whole file
               (monolithic rewrites lose detail; ACE, Zhang et al., ICLR 2026).
  Curator    - this module. Deltas are parsed as literal JSON, validated, and merged by
               deterministic code. A new or edited rule starts as a CANDIDATE.

Evidence gate (the part that keeps the file from filling with plausible noise): each candidate is
shown in a random fraction of proposer prompts (A/B). For each candidate we count, in prompts that showed
it and in prompts where it was eligible but hidden, either
  * evidence="improvement" (DEFAULT since 2026-10-11): prompts, and prompts whose child was a MEASURED
    improvement over its parent (better fitness than the parent, as decided by the caller), or
  * evidence="pass" (the original gate): proposals and raw verifier passes.
Raw passes reward equivalent, non-improving programs (block smoke: rule R8 was promoted for producing
programs that verified but saved nothing), hence the switch. A candidate is promoted to ACTIVE when its
rate with is credibly higher than without, retired when credibly lower or when it reaches
`max_exposure` without showing a benefit. Only ACTIVE rules are
shown unconditionally. Pass/fail comes from the frozen verifier, so rules can change what is
proposed, never what is accepted.

Frozen mode (`frozen=True`) shows ACTIVE rules only and changes nothing: use it to evaluate a
playbook learned on development rows on held-out rows.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass, field

MAX_RULE_CHARS = 400
MAX_RULES = 40              # non-retired rules
MAX_DELTAS_PER_REFLECTION = 3


@dataclass
class Rule:
    id: str
    text: str
    status: str = "candidate"          # candidate | active | retired
    created_call: int = 0
    origin: str = "reflector"          # reflector | seed (hand-written)
    supersedes: str | None = None
    # A/B evidence: proposals and raw verifier passes (before repair) in prompts that showed / hid it
    with_props: int = 0
    with_pass: int = 0
    without_props: int = 0
    without_pass: int = 0
    exposures: int = 0                 # prompts that showed it
    improvements: int = 0              # prompts that showed it and produced a better-than-parent program
    note: str = ""
    # measured-improvement evidence (evidence="improvement"): prompts and improving prompts, shown / hidden
    with_prompts: int = 0
    with_improvements: int = 0         # improving prompts while shown as a CANDIDATE (the gate's numerator)
    without_prompts: int = 0
    without_improvements: int = 0

    @property
    def improvements_with(self) -> int:
        return self.with_improvements


@dataclass
class Playbook:
    blinded: bool = False
    rules: list = field(default_factory=list)
    history: list = field(default_factory=list)    # append-only log of curator decisions
    frozen: bool = False
    ab_fraction: float = 0.5
    min_exposure: int = 8
    max_exposure: int = 40
    z_promote: float = 1.64          # one-sided ~95%
    min_pass_with: int = 3           # never promote on one or two lucky passes
    z_retire: float = -1.0
    banned_words: tuple = ()           # rules containing any of these are refused (blinded runs: literature cues)
    evidence: str = "improvement"      # "improvement" (measured improvement over the parent) | "pass" (raw verifier passes)
    _next: int = 1

    # ------------------------------------------------------------------ persistence
    @classmethod
    def load(cls, path, frozen: bool | None = None) -> "Playbook":
        d = json.loads(open(path).read())
        st = dict(d.get("settings", {}))
        st["banned_words"] = tuple(st.get("banned_words", ()))
        pb = cls(blinded=d["blinded"], rules=[Rule(**r) for r in d["rules"]], history=d.get("history", []),
                 _next=d.get("next_id", 1), **st)
        if frozen is not None:
            pb.frozen = frozen
        return pb

    def save(self, path) -> None:
        settings = {k: getattr(self, k) for k in ("ab_fraction", "min_exposure", "max_exposure", "z_promote", "min_pass_with", "z_retire", "evidence")}
        settings["banned_words"] = list(self.banned_words)
        d = {"blinded": self.blinded, "next_id": self._next, "settings": settings,
             "rules": [asdict(r) for r in self.rules], "history": self.history}
        with open(path, "w") as f:
            json.dump(d, f, indent=1)

    def to_markdown(self) -> str:
        out = [f"# Playbook ({'blinded' if self.blinded else 'open'} naming)", ""]
        for st in ("active", "candidate", "retired"):
            rs = [r for r in self.rules if r.status == st]
            if rs:
                out += [f"## {st} ({len(rs)})", ""]
                for r in rs:
                    out.append(f"- **{r.id}** {r.text}  \n  _shown {r.exposures}, pass {r.with_pass}/{r.with_props} with vs "
                               f"{r.without_pass}/{r.without_props} without; improving prompts as candidate {r.with_improvements}/{r.with_prompts} "
                               f"shown vs {r.without_improvements}/{r.without_prompts} hidden; improvements while shown (any status) "
                               f"{r.improvements}_ {r.note}")
                out.append("")
        return "\n".join(out)

    # ------------------------------------------------------------------ queries
    def live(self) -> list:
        return [r for r in self.rules if r.status != "retired"]

    def get(self, rid):
        return next((r for r in self.rules if r.id == rid), None)

    def add(self, text: str, call: int = 0, origin: str = "reflector", supersedes=None, status="candidate") -> Rule:
        r = Rule(id=f"R{self._next}", text=text.strip(), status=status, created_call=call, origin=origin,
                 supersedes=supersedes)
        self._next += 1
        self.rules.append(r)
        self.history.append({"call": call, "op": "add", "id": r.id, "status": status, "text": r.text,
                             "supersedes": supersedes})
        return r

    # ------------------------------------------------------------------ generator side
    def select(self, rng):
        """Rules for one prompt. Returns (texts, shown_candidate_ids, hidden_candidate_ids)."""
        active = [r for r in self.rules if r.status == "active"]
        shown, hidden = [], []
        if not self.frozen:
            for r in self.rules:
                if r.status == "candidate":
                    (shown if rng.random() < self.ab_fraction else hidden).append(r.id)
        texts = [r.text for r in active] + [self.get(i).text for i in shown]
        return texts, shown, hidden

    @staticmethod
    def render(texts) -> str:
        if not texts:
            return ""
        body = "\n".join(f"  - {t}" for t in texts)
        return ("Lessons from earlier verifier feedback on this task (hints for proposing; scoring and "
                "verification are unchanged):\n" + body)

    def record(self, shown, hidden, n_props: int, n_pass: int, improved: bool, active_shown=True) -> None:
        """Credit one prompt's outcome to the candidates it showed or hid."""
        if self.frozen:
            return
        for i in shown:
            r = self.get(i)
            r.exposures += 1
            r.with_props += n_props
            r.with_pass += n_pass
            r.improvements += int(improved)
            r.with_prompts += 1
            r.with_improvements += int(improved)
        for i in hidden:
            r = self.get(i)
            r.without_props += n_props
            r.without_pass += n_pass
            r.without_prompts += 1
            r.without_improvements += int(improved)
        for r in self.rules:
            if r.status == "active" and active_shown:
                r.exposures += 1
                r.improvements += int(improved)

    # ------------------------------------------------------------------ evidence gate
    @staticmethod
    def z_score(r: Rule, evidence: str = "pass") -> float:
        """Difference of Beta(1,1)-posterior rates (with - without) over its standard error. Rate = raw
        verifier passes per proposal (evidence="pass") or improving prompts per prompt ("improvement")."""
        def post(s, n):
            a, b = s + 1, n - s + 1
            m = a / (a + b)
            return m, a * b / ((a + b) ** 2 * (a + b + 1))
        if evidence == "improvement":
            mw, vw = post(r.improvements_with, r.with_prompts)
            mo, vo = post(r.without_improvements, r.without_prompts)
        else:
            mw, vw = post(r.with_pass, r.with_props)
            mo, vo = post(r.without_pass, r.without_props)
        return (mw - mo) / math.sqrt(vw + vo)

    def _evidence(self, r: Rule) -> tuple:
        """(successes with, trials without) under the configured evidence."""
        if self.evidence == "improvement":
            return r.improvements_with, r.without_prompts
        return r.with_pass, r.without_props

    def update_status(self, call: int) -> list:
        if self.frozen:
            return []
        changes = []
        for r in self.rules:
            succ_with, trials_without = self._evidence(r)
            if r.status != "candidate" or r.exposures < self.min_exposure or trials_without == 0:
                continue
            z = self.z_score(r, self.evidence)
            new = None
            if z >= self.z_promote and succ_with >= self.min_pass_with:
                new = "active"
            elif z <= self.z_retire or r.exposures >= self.max_exposure:
                new = "retired"
            if new:
                r.status = new
                r.note = f"(z = {z:+.2f} at call {call})"
                changes.append((r.id, new, round(z, 2)))
                self.history.append({"call": call, "op": f"gate->{new}", "id": r.id, "z": round(z, 3)})
                if new == "active" and r.supersedes and self.get(r.supersedes):
                    old = self.get(r.supersedes)
                    if old.status != "retired":
                        old.status = "retired"
                        old.note = f"(superseded by {r.id})"
                        self.history.append({"call": call, "op": "superseded", "id": old.id, "by": r.id})
        return changes

    # ------------------------------------------------------------------ reflector side
    def reflect_prompt(self, task_text: str, improvements, failures, stats) -> str:
        rules = "\n".join(f"  {r.id} [{r.status}; shown {r.exposures}; pass with {r.with_pass}/{r.with_props}, "
                          f"without {r.without_pass}/{r.without_props}; improving prompts with {r.with_improvements}/{r.with_prompts}, "
                          f"without {r.without_improvements}/{r.without_prompts}] {r.text}" for r in self.live()) or "  (empty)"
        imp = "\n\n".join(f"# fitness {pf} -> {cf}\n## parent\n{ps}\n## child\n{cs}" for pf, cf, ps, cs in improvements) or "(none)"
        fail = "\n\n".join(f"# rejected: {why}\n{src}" for src, why in failures) or "(none)"
        return f"""You maintain a playbook of short lessons that is shown to a program-proposing model.

{task_text}

Current playbook:
{rules}

Search statistics since the last update: {json.dumps(stats)}

Accepted improvements (parent -> child):
{imp}

Recent rejections with the exact verifier's reason:
{fail}

Propose at most {MAX_DELTAS_PER_REFLECTION} changes that would help the proposer write programs that pass the
verifier and score better. Prefer specific, checkable lessons (a wiring pattern, a precondition that is often
violated, a phase fix-up that is needed) over generic advice. Do not restate an existing rule. Each rule at most
{MAX_RULE_CHARS} characters, in the same role and gate names as the programs above.
Answer with one ```json block containing a list of objects, each one of:
  {{"op": "add", "text": "..."}}
  {{"op": "edit", "id": "R3", "text": "..."}}   (creates a candidate that replaces R3 if it proves better)
  {{"op": "retire", "id": "R3", "why": "..."}}
An empty list is a valid answer."""

    def apply_deltas(self, text: str, call: int) -> tuple:
        """Parse a reflector response and merge it. Returns (applied, errors). Nothing is executed."""
        applied, errors = [], []
        if self.frozen:
            return applied, ["frozen"]
        m = re.findall(r"```(?:json)?\s*\n(.*?)```", text, re.S)
        if not m:
            return applied, ["no json block"]
        try:
            deltas = json.loads(m[0])
        except json.JSONDecodeError as e:
            return applied, [f"bad json: {e}"]
        if not isinstance(deltas, list):
            return applied, ["not a list"]
        for d in deltas[:MAX_DELTAS_PER_REFLECTION]:
            if not isinstance(d, dict) or d.get("op") not in ("add", "edit", "retire"):
                errors.append(f"bad delta: {str(d)[:80]}")
                continue
            op = d["op"]
            if op in ("add", "edit"):
                t = d.get("text")
                if not isinstance(t, str) or not t.strip() or len(t) > MAX_RULE_CHARS:
                    errors.append(f"{op}: text missing or longer than {MAX_RULE_CHARS}")
                    continue
                hit = [w for w in self.banned_words if w.lower() in t.lower()]
                if hit:
                    errors.append(f"{op}: banned word {hit[0]!r}")
                    continue
                if any(t.strip().lower() == r.text.lower() for r in self.live()):
                    errors.append(f"{op}: duplicate")
                    continue
                if len(self.live()) >= MAX_RULES:
                    errors.append("playbook full")
                    continue
                sup = None
                if op == "edit":
                    sup = d.get("id")
                    if not self.get(sup) or self.get(sup).status == "retired":
                        errors.append(f"edit: unknown id {sup}")
                        continue
                r = self.add(t, call, supersedes=sup)
                applied.append((op, r.id))
            else:
                r = self.get(d.get("id"))
                if r is None or r.status == "retired":
                    errors.append(f"retire: unknown id {d.get('id')}")
                    continue
                # The reflector may retire a candidate outright; an ACTIVE rule earned its place with
                # evidence, so it is demoted to candidate and must re-earn it.
                why = str(d.get("why", ""))[:160]
                if r.status == "active":
                    r.status, r.note = "candidate", f"(demoted at call {call}: {why})"
                    r.with_props = r.with_pass = r.without_props = r.without_pass = r.exposures = 0
                    r.with_prompts = r.without_prompts = r.without_improvements = r.improvements = 0
                    r.with_improvements = 0
                    self.history.append({"call": call, "op": "demote", "id": r.id, "why": why})
                    applied.append(("demote", r.id))
                else:
                    r.status, r.note = "retired", f"(retired by reflector at call {call}: {why})"
                    self.history.append({"call": call, "op": "retire", "id": r.id, "why": why})
                    applied.append(("retire", r.id))
        return applied, errors
