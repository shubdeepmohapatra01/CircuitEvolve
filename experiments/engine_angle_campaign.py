"""angle_campaign1 — the dv.windows (angle method) 3-arm campaign.

Scientific contract: docs/P2_CAMPAIGN.md (FROZEN). Operations: docs/ANGLE_CAMPAIGN_RUNBOOK.md.
Driven FROM the platform kernel (environment circuitevolve-dev; needs host.llm). FIRST cell of
any kernel, before importing circuitevolve/pytket (else the kernel dies):

    import os, pathlib; cfg = pathlib.Path.cwd()/".config"; cfg.mkdir(exist_ok=True)
    os.environ["XDG_CONFIG_HOME"] = str(cfg)
    import sys; sys.path.insert(0, "/Users/shubdeepmohapatra/Documents/CircuitEvolve")
    from experiments import engine_angle_campaign as ac
    ac.status()                       # what is done / what the next chunk would run
    ac.run_chunk(host.llm)            # <= CHUNK_MAX_CALLS LLM calls, resumable, sequential

Pins (user-approved 2026-10-19, results/CHANGELOG.md): proposer claude-opus-5, reflector
claude-sonnet-5-5, both thinking={"type": "adaptive"}, max_tokens 16000.

Operationalization of the contract (recorded in CHANGELOG before launch; nothing here weakens it):
  * Budget: every DEV cell gets DEV_CALLS = 45 LLM calls in total. Reflector calls count against
    the arm's budget (invariant 7): arms A and B spend 40 proposer + 5 reflector calls
    (reflect_every 8), arm C spends 45 proposer calls. (Engine rule: a reflection with no new
    proposal evidence since the last one is skipped and costs no call, so A/B spend <= 5 reflector
    calls and the remainder of the 45 on proposals; the realized split is in every row.) HELD-OUT: 40 proposer calls per cell,
    reflector off in every arm. Batch 4 (= concurrency 4), seed 0, archive 4, p_best 0.7.
  * Arm A (seeded learning): playbooks/families/dv.windows.json, MUTABLE on DEV (the only writer),
    loaded frozen=True on held-out.
  * Arm B (placebo): "same rule COUNT, neutral texts, reflector ON" + runbook "playbook files
    loaded frozen for B; only arm A's playbook mutates". Reconciled as: B_dev.json has exactly
    A's live rule layout at campaign start (same number of active and candidate rules; retired
    rules are never shown and are omitted) with hand-written generic, task-agnostic texts;
    candidates are A/B-sampled into prompts by the SAME select path (same ab_fraction, same RNG
    consumption) so the per-prompt rule dose matches arm A. The reflector is ON — called on the
    same cadence with the real reflector prompt, its calls and tokens counted — but its deltas
    are DISCARDED (sham reflector; no promotion/retirement either): the placebo file never
    changes (sha checked before/after every run). On held-out B_held.json holds as many neutral
    ACTIVE rules as arm A's frozen playbook has active rules at the freeze (frozen=True shows
    active rules only, in both arms).
  * Arm C (none): no playbook, no reflector.
  * G1 graduated pass ON in every arm (optimize default); its gains are reported in their own
    zero-LLM column (zero_llm_columns) and are never credited to an arm.
  * Order: DEV circuit-major (A, B, C per circuit, fixed DEV order) -> freeze -> HELD-OUT
    (eps 1e-3 for all circuits, then the 1e-5 secondary arm), arms A, B, C per circuit.
  * Futility (contract stop condition): evaluated ONCE, when the first 3 of the 5 DEV circuits
    are complete in all arms (405 of 675 DEV calls = first point >= half budget). Fires iff
    mean over those circuits of (T-reduction% arm A - T-reduction% arm C) < -MDE_PP (5 pp);
    B - C is reported alongside. A fired futility stop halts the campaign (reported as such).
  * Resumability: one row per finished cell appended to results.jsonl; a cell is done iff it has
    a VALID row. A cell whose run hit the per-session host.llm token ceiling (every call erroring
    with 'token ceiling') is INVALID and rerun in the next sub-session under a fresh tag suffix
    (_r2, _r3, ... — run logs are append-only; rerun_of records the invalid tag).
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROPOSER = "claude-opus-5"
REFLECTOR = "claude-sonnet-5-5"
THINKING = {"type": "adaptive"}
MAX_TOKENS = 16000

DEV = ["qft_8", "heisenberg_6", "hubbard_8", "qml_13", "hhl_8"]
HELD = ["qpe_8", "qae_13", "tfim_6"]
DEV_EPS = 1e-3
HELD_EPS = (1e-3, 1e-5)
ARMS = ("A", "B", "C")
DEV_CALLS = 45                     # 40 proposer + 5 reflector (A, B) | 45 proposer (C)
REFLECT_EVERY = 8
HELD_CALLS = 40
BATCH = 4
SEED = 0
MDE_PP = 5.0
FUTILITY_AFTER = 3                 # DEV circuits complete in all arms
CHUNK_MAX_CALLS = 150              # per sub-session (runbook: 2.0M-token ceiling, ~200 calls)

OUT = ROOT / "results" / "engine" / "angle_campaign1"
RUNS = OUT / "runs"
RESULTS = OUT / "results.jsonl"
START = OUT / "START.json"
FREEZE = OUT / "FREEZE.json"
FUTILITY = OUT / "futility_check.json"
ZERO_LLM = OUT / "zero_llm.json"
PLACEBO_DIR = OUT / "placebo"
B_DEV = PLACEBO_DIR / "B_dev.json"
B_HELD = PLACEBO_DIR / "B_held.json"
A_PB = ROOT / "playbooks" / "families" / "dv.windows.json"
A_START_SNAPSHOT = OUT / "A_playbook_at_start.json"
BASELINES = ROOT / "results" / "bqskit_baselines" / "stage1" / "stage1_baselines_v2.csv"

# Placebo texts: generic, task-agnostic (no circuit, gate, rotation, angle or error-budget
# content and no search-strategy advice), hand-written for this campaign in the style of
# playbooks/placebo_v1.json. Lengths are in arm A's live-rule range (205..383 chars).
NEUTRAL_TEXTS = [
    "Before you answer, read your reply once more and check that every line follows the exact output "
    "format given in the instructions (names, labels, number format, block markers); a malformed line "
    "wastes the attempt. Keep the answer concise and add no commentary outside the requested blocks.",
    "Work through the task in an orderly way: first restate to yourself what is being asked, then decide "
    "how you will answer, then write the answer. A short reply that has been re-read before it is "
    "submitted is more useful than a long one that has not been read back at all.",
    "Answer in the register of the instructions: plain, technical and direct. A consistent register "
    "keeps the reply easy to scan and avoids sentences whose purpose the reader has to work out before "
    "the actual content of the reply can be used.",
    "Use the exact names, labels and numbering that appear in the instructions. Do not invent new labels, "
    "rename items or reorder fields; the reader parses your reply mechanically and cannot guess what an "
    "unfamiliar label was meant to say.",
    "Where the instructions show the expected reply, match its layout closely: the same block markers, "
    "the same line shapes and the same spacing. Deviating from the shown layout is a frequent cause of "
    "replies that cannot be parsed, whatever their content.",
    "Keep numbers in the format that the instructions use: the same style of digits, the same units and "
    "the same sign conventions throughout. Mixing formats inside a single reply makes the reply harder "
    "to read and easier to misinterpret.",
    "Read the whole prompt before writing anything. Details near the end of an instruction often change "
    "how its beginning should be read, and answering after a partial reading is a common source of "
    "avoidable mistakes in otherwise reasonable replies.",
    "If you notice a mistake partway through your reply, fix it in place instead of adding a correction "
    "afterwards. The final reply should read as one clean answer, not as a draft followed by a list of "
    "amendments that the reader has to apply.",
    "Stay within the scope of the request. Do not answer a different question, and do not add extra "
    "deliverables that were not asked for; extra material dilutes the reply and can hide the part that "
    "the reader actually needs.",
    "Each attempt is read on its own, so make every reply self-contained: do not refer to earlier replies, "
    "to hidden context or to work you intend to do later. Everything needed to read the reply should be "
    "present in the reply itself.",
    "Treat any notes about earlier attempts that appear in the prompt as background information about "
    "what has already happened. Read them once, then answer the current request as it is written, in "
    "the format that the current instructions ask for.",
    "Prefer clear structure: one item per line, the same order every time, and blank lines only where "
    "the format calls for them. Consistent structure makes a reply easy to parse and reduces the chance "
    "of a formatting slip going unnoticed.",
    "Do not pad the reply with apologies, disclaimers or restatements of the task. The reader only needs "
    "the requested content; every extra sentence is something that has to be skipped before the useful "
    "part of the reply can be found.",
    "Spell out each item fully in its expected place rather than pointing back to an earlier line with "
    "words such as 'same as above'; every line should be readable on its own by someone who skips the "
    "lines around it.",
    "Keep the reply free of decorative formatting: no headings, bold text or emphasis unless the format "
    "asks for them. Plain text inside the requested blocks is the easiest form for the reader to process "
    "reliably and without ambiguity.",
    "Before finishing, go through the formatting requirements in the instructions one by one and confirm "
    "that the reply meets each of them. A short final pass of this kind catches most omissions and costs "
    "very little time.",
    "Use plain, unambiguous wording. Avoid private shorthand, and avoid words with two possible readings "
    "when a precise word is available; the reply should mean exactly one thing to the person or program "
    "that reads it.",
    "Do not mention these notes in your reply; apply them silently. The reply should contain only what "
    "the instructions ask for, without remarks about how it was produced or about which guidance was "
    "followed while writing it.",
    "Read this request as it is written rather than as a remembered request that looks similar. Surface "
    "similarity can hide differences in what is being asked, and a reply shaped by memory may not fit "
    "the layout requested here.",
    "Keep the reply proportionate to the request: a small request deserves a small reply. Long replies "
    "are slower to read and to check, and length on its own does not make a reply clearer or more "
    "useful to the person reading it.",
    "End the reply cleanly once the requested content is complete. Trailing notes, alternative versions "
    "or open questions after the answer make it unclear which part is the actual answer and which part "
    "is commentary.",
    "Write as if the reader will use your reply without asking any follow-up questions. Anything "
    "ambiguous may be read in an unintended way, so remove ambiguity before you submit rather than "
    "relying on the reader to interpret it kindly.",
]
PLACEBO_NOTE = "(placebo control: generic, task-agnostic; hand-written for angle_campaign1, no evidence)"


# ---------------------------------------------------------------------------- small helpers
def _rel(p) -> str:
    p = Path(p).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def sha256(p) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def elabel(eps: float) -> str:
    return {1e-3: "e3", 1e-5: "e5"}[eps]


def key(cell: dict) -> str:
    return f"{cell['phase']}|{cell['circuit']}|{cell['arm']}|{elabel(cell['eps'])}"


def cells() -> list:
    """The full campaign schedule, in execution order."""
    out = [dict(phase="dev", circuit=c, arm=a, eps=DEV_EPS, calls=DEV_CALLS) for c in DEV for a in ARMS]
    out += [dict(phase="held", circuit=c, arm=a, eps=e, calls=HELD_CALLS)
            for e in HELD_EPS for c in HELD for a in ARMS]
    return out


def rows() -> list:
    return [json.loads(x) for x in RESULTS.read_text().splitlines() if x.strip()] if RESULTS.exists() else []


def done_keys() -> set:
    return {r["key"] for r in rows() if r.get("valid")}


def _append(path: Path, rec: dict):
    with open(path, "a") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")


def _write_once(path: Path, obj) -> None:
    with open(path, "x") as fh:                    # append-only: refuse to overwrite
        json.dump(obj, fh, indent=1, default=str)


def expected_split(calls: int, reflect: bool, batch: int = BATCH, every: int = REFLECT_EVERY) -> tuple:
    """NOMINAL (proposer, reflector) split of a budget (progress-bar total / record only). The
    realized split comes from the loop's stats (batch alignment and evidence-skips can move one
    call between the two); the total always equals the budget and proposer calls stay >= 40."""
    prop = n = refl = 0
    while n < calls:
        k = min(batch, calls - n)
        prop += k
        n += k
        if reflect and n < calls and prop // every > refl:
            refl += 1
            n += 1
    return prop, refl


# ---------------------------------------------------------------------------- placebo arm
def placebo_class():
    """Factory (keeps module import light): Playbook subclass for the DEV placebo arm."""
    from circuitevolve.search.playbook import Playbook

    class PlaceboPlaybook(Playbook):
        """Shows rules exactly like a live playbook (A/B-sampled candidates) but never learns:
        no credit, no gate changes, reflector deltas discarded. frozen stays False only so the
        engine loop issues the (sham) reflector calls on arm A's cadence."""

        def record(self, *a, **k):
            return None

        def update_status(self, call):
            return []

        def apply_deltas(self, text, call):
            return [], ["placebo arm: deltas discarded (sham reflector; playbook file frozen)"]

    return PlaceboPlaybook


def _placebo_file(path: Path, n_active: int, n_candidate: int, settings: dict, purpose: str) -> str:
    assert n_active + n_candidate <= len(NEUTRAL_TEXTS), "not enough neutral texts"
    rules = []
    for i, t in enumerate(NEUTRAL_TEXTS[:n_active + n_candidate]):
        rules.append(dict(id=f"P{i + 1}", text=t, status=("active" if i < n_active else "candidate"),
                          created_call=0, origin="placebo", supersedes=None, with_props=0, with_pass=0,
                          without_props=0, without_pass=0, exposures=0, improvements=0, note=PLACEBO_NOTE,
                          with_prompts=0, with_improvements=0, without_prompts=0, without_improvements=0))
    d = dict(blinded=False, next_id=len(rules) + 1, settings=settings, rules=rules,
             history=[dict(call=0, op="placebo_build", purpose=purpose)])
    PLACEBO_DIR.mkdir(parents=True, exist_ok=True)
    with open(path, "x") as fh:
        json.dump(d, fh, indent=1)
    return sha256(path)


def _live_layout(pb_path: Path) -> tuple:
    d = json.loads(pb_path.read_text())
    st = [r["status"] for r in d["rules"]]
    return st.count("active"), st.count("candidate"), dict(d.get("settings", {}))


# ---------------------------------------------------------------------------- shas / records
def frozen_inputs() -> dict:
    """SHA-256 of every file the freeze procedure names (families, graduated + referenced, router)."""
    fam = ROOT / "playbooks" / "families"
    out = {str(p.relative_to(ROOT)): sha256(p) for p in sorted(fam.glob("*.json"))}
    gi = ROOT / "playbooks" / "graduated" / "index.json"
    out[str(gi.relative_to(ROOT))] = sha256(gi)
    for entries in json.loads(gi.read_text())["families"].values():
        for e in entries:
            out[e["path"]] = sha256(ROOT / e["path"])
    rj = ROOT / "playbooks" / "router.json"
    out[str(rj.relative_to(ROOT))] = sha256(rj)
    return out


def _verifier_digest() -> str:
    from circuitevolve.integrity import frozen_digest
    return frozen_digest()


def start() -> dict:
    """Campaign start record (once): pins, shas, arm-A snapshot, placebo B_dev built + hashed."""
    if START.exists():
        return json.loads(START.read_text())
    OUT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(A_PB, A_START_SNAPSHOT)
    n_act, n_cand, settings = _live_layout(A_PB)
    b_sha = _placebo_file(B_DEV, n_act, n_cand, settings,
                          f"DEV placebo: arm A live layout at start ({n_act} active + {n_cand} candidate)")
    rec = dict(campaign="angle_campaign1", contract="docs/P2_CAMPAIGN.md",
               runbook="docs/ANGLE_CAMPAIGN_RUNBOOK.md", started=time.strftime("%Y-%m-%d %H:%M:%S"),
               proposer=PROPOSER, reflector=REFLECTOR, thinking=THINKING, max_tokens=MAX_TOKENS,
               dev=DEV, held=HELD, dev_eps=DEV_EPS, held_eps=list(HELD_EPS), arms=list(ARMS),
               dev_calls=DEV_CALLS, dev_split_AB=expected_split(DEV_CALLS, True),
               dev_split_C=expected_split(DEV_CALLS, False), held_calls=HELD_CALLS,
               reflect_every=REFLECT_EVERY, batch=BATCH, seed=SEED, mde_pp=MDE_PP,
               futility_after=FUTILITY_AFTER, verifier_digest=_verifier_digest(),
               frozen_inputs=frozen_inputs(), a_playbook_sha_start=sha256(A_PB),
               a_layout_start=dict(active=n_act, candidate=n_cand),
               b_dev_sha=b_sha, b_dev_text_chars=[len(t) for t in NEUTRAL_TEXTS[:n_act + n_cand]])
    _write_once(START, rec)
    return rec


def freeze() -> dict:
    """Freeze procedure (P2_CAMPAIGN.md): after DEV, before any held-out cell. Builds B_held with
    arm A's frozen ACTIVE-rule count; records SHA-256 of everything that conditions held-out."""
    if FREEZE.exists():
        return json.loads(FREEZE.read_text())
    pend = [key(c) for c in cells() if c["phase"] == "dev" and key(c) not in done_keys()]
    if pend:
        raise RuntimeError(f"freeze refused: DEV not complete ({len(pend)} cells pending)")
    n_act, _, settings = _live_layout(A_PB)
    b_sha = _placebo_file(B_HELD, n_act, 0, settings,
                          f"HELD-OUT placebo: arm A frozen active count at freeze ({n_act})")
    rec = dict(frozen=time.strftime("%Y-%m-%d %H:%M:%S"), a_active_at_freeze=n_act,
               a_playbook_sha=sha256(A_PB), b_held_sha=b_sha, b_dev_sha=sha256(B_DEV),
               frozen_inputs=frozen_inputs(), verifier_digest=_verifier_digest(),
               proposer=PROPOSER, reflector="OFF on held-out", seed=SEED)
    _write_once(FREEZE, rec)
    return rec


def check_freeze() -> None:
    f = json.loads(FREEZE.read_text())
    now = frozen_inputs()
    drift = [k for k in f["frozen_inputs"] if now.get(k) != f["frozen_inputs"][k]]
    if drift or sha256(B_HELD) != f["b_held_sha"] or sha256(A_PB) != f["a_playbook_sha"]:
        raise RuntimeError(f"freeze drift: {drift or 'placebo/arm-A playbook'} changed since FREEZE.json")
    if _verifier_digest() != f["verifier_digest"]:
        raise RuntimeError("verifier digest drift since FREEZE.json")


# ---------------------------------------------------------------------------- one cell
def _tag(cell: dict) -> tuple:
    base = f"ac1_{cell['phase']}_{cell['circuit']}_{cell['arm']}_{elabel(cell['eps'])}"
    tag, k, prev = base, 1, None
    while (RUNS / f"{tag}.jsonl").exists():
        prev = tag
        k += 1
        tag = f"{base}_r{k}"
    return tag, prev


def _scan_log(path: Path) -> dict:
    ceiling = errs = 0
    if path.exists():
        for line in path.read_text().splitlines():
            r = json.loads(line)
            e = r.get("error")
            if e:
                errs += 1
                ceiling += int("token ceiling" in str(e))
    return dict(error_records=errs, ceiling_errors=ceiling)


def calls_to_best(path: Path):
    lines = [json.loads(x) for x in path.read_text().splitlines()]
    end = next(x for x in lines if x["kind"] == "end")["summary"]
    if end["t_after"] >= end["t_before"]:
        return None
    hits = [x["call"] for x in lines if x["kind"] == "propose" and x.get("accepted")
            and x.get("t_after") is not None and x["t_after"] <= end["t_after"]]
    return min(hits) if hits else None


def run_cell(llm, cell: dict) -> dict:
    from circuitevolve.engine.run import optimize
    from circuitevolve.llm_backends import make_api_backend
    from experiments.engine_recon_campaign import Progress
    phase, name, arm, eps, calls = cell["phase"], cell["circuit"], cell["arm"], cell["eps"], cell["calls"]
    if not START.exists():
        raise RuntimeError("call start() first (campaign start record)")
    if phase == "held":
        if not FREEZE.exists():
            raise RuntimeError("held-out refused: no FREEZE.json (run freeze() after DEV)")
        check_freeze()
    learning = phase == "dev" and arm in ("A", "B")      # A learns; B = sham reflector
    n_prop, n_refl = expected_split(calls, learning)
    tag, prev = _tag(cell)
    bar = Progress(n_prop, f"{name} {arm} {elabel(eps)}")
    complete = bar.wrap(make_api_backend(llm, model=PROPOSER, thinking=THINKING,
                                         max_tokens=MAX_TOKENS, max_concurrency=BATCH))
    reflect = (make_api_backend(llm, model=REFLECTOR, thinking=THINKING, max_tokens=MAX_TOKENS,
                                max_concurrency=1) if learning else None)
    kw, pb_file = {}, None
    if arm == "A":
        pb_file = A_PB
        kw = dict(playbook_path=str(A_PB)) if phase == "dev" else dict(playbook_path=str(A_PB),
                                                                         playbook_frozen=True)
    elif arm == "B":
        if phase == "dev":
            pb_file = B_DEV
            kw = dict(playbook=placebo_class().load(B_DEV))
        else:
            pb_file = B_HELD
            kw = dict(playbook_path=str(B_HELD), playbook_frozen=True)
    sha_before = sha256(pb_file) if pb_file else None
    print(f"== {tag} · {phase} · arm {arm} · eps {eps:g} · budget {calls} "
          f"({n_prop} proposer + {n_refl} reflector) · playbook sha {str(sha_before)[:12]}", flush=True)
    t0 = time.time()
    summ = optimize(name, eps, complete, runs_dir=RUNS, tag=tag, n_calls=calls, batch=BATCH, seed=SEED,
                    reflect_complete=reflect, reflect_every=REFLECT_EVERY, **kw)
    sha_after = sha256(pb_file) if pb_file else None
    if pb_file is not None and pb_file != A_PB and sha_after != sha_before:
        raise RuntimeError(f"placebo file {pb_file.name} changed during {tag}")
    if phase == "held":
        check_freeze()                                   # arm-A playbook unchanged by a frozen run
    scan = _scan_log(RUNS / f"{tag}.jsonl")
    st = summ["stats"]
    fc = summ.get("final_check_vs_original")
    ceiling_hit = scan["ceiling_errors"] > 0
    valid = (not ceiling_hit) and st["llm_errors"] <= max(2, calls // 10) and bool(fc and fc.get("ok"))
    row = dict(key=key(cell), phase=phase, circuit=name, arm=arm, eps=eps, tag=tag, rerun_of=prev,
               budget=calls, nominal_split=[n_prop, n_refl], proposer=PROPOSER,
               reflector=(REFLECTOR if learning else None),
               reflector_mode=("learning" if (learning and arm == "A") else
                               "sham (deltas discarded)" if learning else "off"),
               seed=SEED, batch=BATCH, t_before=summ["t_before"], t_after=summ["t_after"],
               t_after_reclaimed=summ.get("t_after_reclaimed"), before=summ["before"], after=summ["after"],
               calls=summ["calls"], stats=st, backend_stats=summ.get("backend_stats"),
               reflect_backend_stats=(dict(reflect.stats) if reflect is not None else None),
               ledger=summ["ledger"], final_check=fc, pre_opt=summ.get("pre_opt"),
               routing=dict(family=summ["routing"]["family"], contract=summ["routing"]["contract"]),
               playbook=summ.get("playbook"), playbook_file=(_rel(pb_file) if pb_file else None),
               playbook_sha_before=sha_before, playbook_sha_after=sha_after,
               calls_to_best=calls_to_best(RUNS / f"{tag}.jsonl"), log_scan=scan,
               ceiling_hit=ceiling_hit, valid=valid, seconds=round(time.time() - t0, 1),
               finished=time.strftime("%Y-%m-%d %H:%M:%S"))
    _append(RESULTS, row)
    print(f"== {tag} DONE: T {row['t_before']} -> {row['t_after']} · accepted {st['accepted']} "
          f"(exact {st['exact_accepts']}, approx {st['approx_accepts']}) · declined {st['declined']} · "
          f"errors {st['llm_errors']} · valid {valid} · {row['seconds']}s", flush=True)
    if fc is not None and not fc.get("ok"):
        raise RuntimeError(f"{tag}: final whole-circuit check vs original FAILED — integrity stop")
    return row


# ---------------------------------------------------------------------------- futility
def _red(r: dict) -> float:
    return 100.0 * (r["t_before"] - r["t_after"]) / r["t_before"]


def _valid_by_key() -> dict:
    out = {}
    for r in rows():
        if r.get("valid"):
            out[r["key"]] = r                       # last valid row wins (reruns are new rows)
    return out


def futility() -> dict | None:
    """Evaluate the contract's half-budget futility stop once (written to futility_check.json)."""
    if FUTILITY.exists():
        return json.loads(FUTILITY.read_text())
    v = _valid_by_key()
    first = DEV[:FUTILITY_AFTER]
    if not all(f"dev|{c}|{a}|e3" in v for c in first for a in ARMS):
        return None
    per = {c: {a: _red(v[f"dev|{c}|{a}|e3"]) for a in ARMS} for c in first}
    d_ac = statistics.mean(per[c]["A"] - per[c]["C"] for c in first)
    d_bc = statistics.mean(per[c]["B"] - per[c]["C"] for c in first)
    rec = dict(evaluated=time.strftime("%Y-%m-%d %H:%M:%S"), circuits=first, reduction_pct=per,
               mean_A_minus_C_pp=d_ac, mean_B_minus_C_pp=d_bc, mde_pp=MDE_PP,
               fired=bool(d_ac < -MDE_PP),
               rule=f"fires iff mean(A-C) < -{MDE_PP} pp over the first {FUTILITY_AFTER} DEV circuits")
    _write_once(FUTILITY, rec)
    return rec


# ---------------------------------------------------------------------------- chunking
def pending() -> list:
    d = done_keys()
    return [c for c in cells() if key(c) not in d]


def next_chunk(max_calls: int = CHUNK_MAX_CALLS) -> list:
    out, tot = [], 0
    for c in pending():
        if c["phase"] == "held" and not FREEZE.exists():
            break                                     # DEV must be frozen before held-out starts
        if out and (tot + c["calls"] > max_calls or c["phase"] != out[0]["phase"]):
            break
        out.append(c)
        tot += c["calls"]
    return out


def status() -> dict:
    d, p = done_keys(), pending()
    fut = json.loads(FUTILITY.read_text()) if FUTILITY.exists() else None
    s = dict(started=START.exists(), frozen=FREEZE.exists(), done=len(d), pending=len(p),
             pending_calls=sum(c["calls"] for c in p), futility=fut,
             next_chunk=[key(c) for c in next_chunk()],
             invalid_rows=[r["tag"] for r in rows() if not r.get("valid")])
    print(json.dumps(s, indent=1, default=str), flush=True)
    return s


def run_chunk(llm, max_calls: int = CHUNK_MAX_CALLS) -> dict:
    """One sub-session's worth: sequential cells within max_calls, never crossing a phase boundary.
    Stops at the first token-ceiling signature or a fired futility stop."""
    start()
    fut = futility()
    if fut and fut["fired"]:
        print("!! futility stop fired — campaign halted (see futility_check.json)", flush=True)
        return dict(ran=[], stopped="futility")
    chunk = next_chunk(max_calls)
    if not chunk:
        why = "complete" if not pending() else "awaiting freeze()"
        print(f"-- nothing to run: {why}", flush=True)
        return dict(ran=[], stopped=why)
    print(f"CHUNK {len(chunk)} cells / {sum(c['calls'] for c in chunk)} calls: "
          + ", ".join(key(c) for c in chunk), flush=True)
    ran, stopped = [], None
    for c in chunk:
        r = run_cell(llm, c)
        ran.append(dict(key=r["key"], tag=r["tag"], t=(r["t_before"], r["t_after"]), valid=r["valid"]))
        if r["ceiling_hit"]:
            stopped = "token ceiling"
            print("!! budget-ceiling signature: stopping chunk (rerun this cell in a fresh session)", flush=True)
            break
        fut = futility()
        if fut and fut["fired"]:
            stopped = "futility"
            print("!! futility stop fired", flush=True)
            break
    left = pending()
    print(f"CHUNK END · stopped={stopped} · pending {len(left)} cells "
          f"({sum(c['calls'] for c in left)} calls)", flush=True)
    return dict(ran=ran, stopped=stopped, pending=len(left))


# ---------------------------------------------------------------------------- zero-LLM columns
def zero_llm_columns() -> dict:
    """B0-under-engine-metric and the G1 pass column, zero LLM calls, all 8 circuits x both eps."""
    if ZERO_LLM.exists():
        return json.loads(ZERO_LLM.read_text())
    from circuitevolve.engine.run import optimize

    def never(prompts):                            # n_calls=0: must never be called
        raise AssertionError("zero-LLM column called the LLM")
    out = []
    for name in DEV + HELD:
        for eps in HELD_EPS:
            off = optimize(name, eps, never, n_calls=0, graduated="off")
            on = optimize(name, eps, never, n_calls=0)
            out.append(dict(circuit=name, eps=eps, split=("dev" if name in DEV else "held"),
                            t_input_no_pass=off["t_before"], t_after_g1=on["t_before"],
                            g1_delta=on["t_before"] - off["t_before"],
                            g1_pct=round(100.0 * (on["t_before"] - off["t_before"]) / off["t_before"], 3),
                            rz_before=(on.get("pre_opt") or {}).get("rz_before"),
                            rz_after=(on.get("pre_opt") or {}).get("rz_after"),
                            final_check_ok=bool((on.get("final_check_vs_original") or {}).get("ok"))))
    rec = dict(description="zero-LLM: engine angle stage with n_calls=0; t_input_no_pass = TKET input "
                           "(graduated off), t_after_g1 = after the G1 same-Pauli merge pass; same metric "
                           "and ledger v1 as the campaign runs. G1 gains are attributed HERE, never to an arm.",
               rows=out)
    OUT.mkdir(parents=True, exist_ok=True)
    _write_once(ZERO_LLM, rec)
    return rec


# ---------------------------------------------------------------------------- report
def bars() -> dict:
    """Per (circuit, eps): B0 and the best VALID arm of {B1, B2, B3g} (valid = measured_within_eps);
    B3 (published DPF workflow) as the external BQSKit-FT reference."""
    seen, out = set(), {}
    for r in csv.DictReader(open(BASELINES)):
        k = (r["circuit"], float(r["eps_total"]), r["arm"])
        if k in seen:
            continue
        seen.add(k)
        d = out.setdefault((r["circuit"], float(r["eps_total"])), {})
        d[r["arm"]] = dict(t=int(r["t_count_canon"]), valid=(r["measured_within_eps"] == "True"),
                           bound_over_eps=float(r["bound_over_eps"]))
    res = {}
    for (c, e), d in out.items():
        cand = [(v["t"], a) for a, v in d.items() if a in ("B1", "B2", "B3g") and v["valid"]]
        t, a = min(cand)
        res[(c, e)] = dict(B0=d["B0"]["t"], best=t, best_arm=a, B3_dpf=d.get("B3", {}).get("t"),
                           B3_valid=d.get("B3", {}).get("valid"))
    return res


def _boot_ci(xs, n=10000, seed=0):
    if len(xs) < 2:
        return (None, None)
    rng = random.Random(seed)
    ms = sorted(statistics.mean(rng.choice(xs) for _ in xs) for _ in range(n))
    return (ms[int(0.025 * n)], ms[int(0.975 * n) - 1])


def _pb_outcome() -> dict:
    s = {r["id"]: r for r in json.loads(A_START_SNAPSHOT.read_text())["rules"]}
    now = json.loads(A_PB.read_text())
    e = {r["id"]: r for r in now["rules"]}
    promoted = [i for i in e if e[i]["status"] == "active" and s.get(i, {}).get("status") != "active"]
    retired = [i for i in e if e[i]["status"] == "retired" and s.get(i, {}).get("status") != "retired"]
    added = [i for i in e if i not in s]
    demoted = [i for i in e if s.get(i, {}).get("status") == "active" and e[i]["status"] == "candidate"]
    low_exposure_active = [i for i in e if e[i]["status"] == "active" and e[i]["exposures"] < 8]
    return dict(promoted=promoted, retired=retired, added=added, demoted=demoted,
                active_now=[i for i in e if e[i]["status"] == "active"],
                active_below_min_exposure=low_exposure_active)


def report(name: str = "REPORT") -> dict:
    """Five-column report (contract §Reporting). Written once per name (append-only)."""
    v = _valid_by_key()
    B = bars()
    z = {(r["circuit"], r["eps"]): r for r in json.loads(ZERO_LLM.read_text())["rows"]} if ZERO_LLM.exists() else {}
    lines = [f"# angle_campaign1 — {name}", "",
             f"Proposer {PROPOSER} · reflector {REFLECTOR} (arm A learning, arm B sham, off on held-out) · "
             f"adaptive thinking · max_tokens {MAX_TOKENS} · batch {BATCH} · seed {SEED}.",
             "T-reduction % = 100 (T_before - T_after) / T_before, T_before = post-G1-pass input (loop metric).",
             f"HONEST MDE: ~{MDE_PP:g} pp on 3 held-out circuits; smaller effects need the 1e-5 arm to "
             "corroborate direction and are not claimed.", ""]
    table, paired = [], {}
    for phase, eps_list, circs in (("dev", [DEV_EPS], DEV), ("held", list(HELD_EPS), HELD)):
        for eps in eps_list:
            hdr = (f"## {phase.upper()} @ {eps:g}\n\n| circuit | B0 | best of B1/B2/B3g | B3 DPF | G1 col "
                   "(T in -> after G1) | arm | T_before | T_after | dT % | accepts (exact/approx) | window spent | "
                   "calls prop+refl | vs best bar |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
            lines.append(hdr)
            for c in circs:
                b = B.get((c, eps), {})
                zz = z.get((c, eps), {})
                red = {}
                for a in ARMS:
                    r = v.get(f"{phase}|{c}|{a}|{elabel(eps)}")
                    if r is None:
                        lines.append(f"| {c} | | | | | {a} | pending | | | | | | |")
                        continue
                    red[a] = _red(r)
                    st = r["stats"]
                    vs = (r["t_after"] - b["best"]) if b else None
                    lines.append(
                        f"| {c} | {b.get('B0')} | {b.get('best')} ({b.get('best_arm')}) | {b.get('B3_dpf')} | "
                        f"{zz.get('t_input_no_pass')} -> {zz.get('t_after_g1')} | {a} | {r['t_before']} | "
                        f"{r['t_after']} | {red[a]:.2f} | {st['accepted']} ({st['exact_accepts']}/"
                        f"{st['approx_accepts']}) | {r['ledger']['window_spent']:.2e} | "
                        f"{st['proposal_calls']}+{st['reflect_calls']} | {vs:+d} |")
                    table.append(dict(phase=phase, eps=eps, circuit=c, arm=a, t_before=r["t_before"],
                                      t_after=r["t_after"], red_pct=red[a], bar_best=b.get("best"),
                                      bar_arm=b.get("best_arm"), B0=b.get("B0"), stats=st,
                                      contract=r["routing"]["contract"]))
                if len(red) == 3:
                    for pa, pb_ in (("A", "C"), ("A", "B"), ("B", "C")):
                        paired.setdefault((phase, eps, f"{pa}-{pb_}"), []).append(red[pa] - red[pb_])
            lines.append("")
    lines.append("## Paired per-circuit deltas (pp of T reduction; bootstrap 95% CI over circuits)\n")
    lines.append("| phase | eps | contrast | n | mean | CI | +/0/- |\n|---|---|---|---|---|---|---|")
    pj = {}
    for (ph, e, ctr), xs in paired.items():
        lo, hi = _boot_ci(xs)
        sg = (sum(x > 1e-9 for x in xs), sum(abs(x) <= 1e-9 for x in xs), sum(x < -1e-9 for x in xs))
        ci = f"{lo:+.2f}..{hi:+.2f}" if lo is not None else "n/a"
        lines.append(f"| {ph} | {e:g} | {ctr} | {len(xs)} | {statistics.mean(xs):+.2f} | {ci} | "
                     f"{sg[0]}/{sg[1]}/{sg[2]} |")
        pj[f"{ph}|{e:g}|{ctr}"] = dict(n=len(xs), mean=statistics.mean(xs), ci=(lo, hi), signs=sg, xs=xs)
    po = _pb_outcome() if A_START_SNAPSHOT.exists() else None
    lines += ["", "## Playbook outcome (arm A, DEV learning; frozen transfer = held-out A rows above)", "",
              "```", json.dumps(po, indent=1), "```", "",
              "## Contract column", "",
              "All cells are angle-method (unitary-preserving, contract from routing); exact vs approx "
              "accepts per cell are in the accepts column. No relaxed-contract rows are mixed in.", ""]
    fut = json.loads(FUTILITY.read_text()) if FUTILITY.exists() else None
    if fut:
        lines += ["## Futility check", "", "```", json.dumps(fut, indent=1), "```", ""]
    md = OUT / f"{name}.md"
    with open(md, "x") as fh:
        fh.write("\n".join(lines) + "\n")
    rec = dict(table=table, paired=pj, playbook_outcome=po, futility=fut)
    _write_once(OUT / f"{name}.json", rec)
    print("\n".join(lines), flush=True)
    return rec
