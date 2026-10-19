"""angle_campaign1 driver plumbing with a fake host.llm (no real LLM): arm semantics (A learns,
B sham reflector + frozen placebo file, C none), budget split, freeze ordering, frozen held-out
runs leave every file unchanged, resumable skip-done, ceiling signature -> invalid row + rerun tag;
plus the two engine kwargs added for the campaign (playbook_frozen, injected playbook)."""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from circuitevolve.blocks import REPO  # noqa: E402
from circuitevolve.engine.run import optimize  # noqa: E402
from circuitevolve.search.playbook import Playbook  # noqa: E402
from experiments import engine_angle_campaign as ac  # noqa: E402

FAMILY = REPO / "playbooks" / "families" / "dv.windows.json"
START_SNAPSHOT = REPO / "results" / "engine" / "angle_campaign1" / "A_playbook_at_start.json"
REFLECT_REPLY = '```json\n[{"op": "add", "text": "fake reflector rule for the driver test"}]\n```'
BOGUS = "```window\nh q0\n```\n"         # parses, verifier rejects: counts as reflector evidence
QASM = """OPENQASM 2.0;
include "qelib1.inc";
qreg q[3];
h q[0];
cx q[0],q[1];
rz(0.30) q[1];
cx q[1],q[2];
h q[2];
rz(0.25) q[1];
rz(0.90) q[2];
t q[0];
"""


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fake_llm(log, ceiling=False):
    def llm(reqs, max_concurrency=4):
        out = []
        for r in reqs:
            log.append(r)
            assert r["thinking"] == {"type": "adaptive"} and r["max_tokens"] == 16000
            if ceiling:
                out.append({"error": "host.llm() per-frame token ceiling (2.0M) reached"})
            elif r["model"] == ac.REFLECTOR:
                out.append({"text": REFLECT_REPLY, "usage": {"input_tokens": 10, "output_tokens": 5}})
            else:
                assert r["model"] == ac.PROPOSER
                out.append({"text": BOGUS, "usage": {"input_tokens": 10, "output_tokens": 1}})
        return out
    return llm


@pytest.fixture
def camp(tmp_path, monkeypatch):
    out = tmp_path / "angle_campaign1"
    a_pb = tmp_path / "dv.windows.json"
    shutil.copyfile(START_SNAPSHOT, a_pb)        # campaign-start layout (the live file evolves)
    for k, v in dict(OUT=out, RUNS=out / "runs", RESULTS=out / "results.jsonl", START=out / "START.json",
                     FREEZE=out / "FREEZE.json", FUTILITY=out / "futility_check.json",
                     ZERO_LLM=out / "zero_llm.json", PLACEBO_DIR=out / "placebo",
                     B_DEV=out / "placebo" / "B_dev.json", B_HELD=out / "placebo" / "B_held.json",
                     A_PB=a_pb, A_START_SNAPSHOT=out / "A_playbook_at_start.json").items():
        monkeypatch.setattr(ac, k, v)
    monkeypatch.setattr(ac, "frozen_inputs", lambda: {"fake": "0"})   # real family files: read-only anyway
    fam_sha = _sha(FAMILY)
    yield ac
    assert _sha(FAMILY) == fam_sha                                   # the real playbook never touched


def test_schedule_and_budget_split():
    cs = ac.cells()
    assert len(cs) == 5 * 3 + 3 * 3 * 2
    # A-first order (2026-10-19 user decision): DEV A, HELD A, then DEV B/C, then HELD B/C
    assert [c["arm"] for c in cs[:5]] == ["A"] * 5 and [c["phase"] for c in cs[5:11]] == ["held"] * 6
    assert all(c["arm"] == "A" for c in cs[:11]) and {c["arm"] for c in cs[11:]} == {"B", "C"}
    assert len({ac.key(c) for c in cs}) == len(cs)
    assert ac.expected_split(45, True) == (40, 5)
    assert ac.expected_split(45, False) == (45, 0)
    assert ac.expected_split(40, False) == (40, 0)
    assert sum(c["calls"] for c in cs) == 15 * 45 + 18 * 40
    assert all(len(t) >= 205 and len(t) <= 383 for t in ac.NEUTRAL_TEXTS)


def test_engine_split_matches_expected(tmp_path):
    """A 45 budget: >= 40 proposer calls (contract floor), <= 5 reflector calls, total exactly 45."""
    pb = tmp_path / "pb.json"
    shutil.copyfile(FAMILY, pb)
    log = []
    s = optimize("heisenberg_6", 1e-3, lambda ps: [BOGUS] * len(ps), playbook_path=str(pb),
                 reflect_complete=lambda ps: (log.extend(ps), ["```json\n[]\n```"] * len(ps))[1],
                 n_calls=45, batch=4, reflect_every=8, seed=0)
    st = s["stats"]
    assert st["proposal_calls"] + st["reflect_calls"] == 45
    assert st["proposal_calls"] >= 40 and st["reflect_calls"] + st["reflect_skipped_no_evidence"] <= 5
    assert st["reflect_calls"] >= 4


def test_engine_playbook_frozen_and_injected(tmp_path):
    pb = tmp_path / "pb.json"
    shutil.copyfile(FAMILY, pb)
    sha = _sha(pb)
    refl = []
    s = optimize(QASM, 1e-3, lambda ps: ["NONE"] * len(ps), playbook_path=str(pb), playbook_frozen=True,
                 reflect_complete=lambda ps: (refl.extend(ps), ["x"] * len(ps))[1],
                 n_calls=4, batch=1, reflect_every=1, seed=0, runs_dir=tmp_path)
    assert _sha(pb) == sha and not refl and s["playbook"] is not None
    obj = Playbook.load(pb)
    s = optimize(QASM, 1e-3, lambda ps: ["NONE"] * len(ps), playbook=obj, n_calls=2, batch=1, seed=0)
    assert _sha(pb) == sha                                    # injected object never saved back
    with pytest.raises(ValueError):
        optimize(QASM, 1e-3, lambda ps: ["NONE"], playbook=obj, playbook_path=str(pb), n_calls=1)


def test_dev_cells_arm_semantics(camp):
    log = []
    llm = fake_llm(log)
    rec = camp.start()
    assert rec["a_layout_start"] == {"active": 1, "candidate": 21}
    b_sha = _sha(camp.B_DEV)
    a_sha = _sha(camp.A_PB)
    rows = {}
    for arm in ("A", "B", "C"):
        rows[arm] = camp.run_cell(llm, dict(phase="dev", circuit="heisenberg_6", arm=arm, eps=1e-3, calls=18))
    # A: real reflector, deltas applied, family copy mutated
    assert rows["A"]["stats"]["reflect_calls"] >= 1 and rows["A"]["stats"]["rules_added"] >= 1
    assert _sha(camp.A_PB) != a_sha
    # B: sham reflector calls happen, nothing applied, placebo file unchanged
    assert rows["B"]["stats"]["reflect_calls"] >= 1 and rows["B"]["stats"]["rules_added"] == 0
    assert _sha(camp.B_DEV) == b_sha and rows["B"]["reflector_mode"].startswith("sham")
    # placebo texts reached the proposer prompts of arm B only
    b_prompts = [r["prompt"] for r in log if r["model"] == camp.PROPOSER and camp.NEUTRAL_TEXTS[0][:60] in r["prompt"]]
    assert len(b_prompts) >= 1
    # C: no reflector, all 18 proposer calls
    assert rows["C"]["stats"]["proposal_calls"] == 18 and rows["C"]["stats"]["reflect_calls"] == 0
    assert all(r["valid"] for r in rows.values())
    # held-out refused before freeze; freeze refused while DEV incomplete
    with pytest.raises(RuntimeError):
        camp.run_cell(llm, dict(phase="held", circuit="tfim_6", arm="C", eps=1e-3, calls=4))
    with pytest.raises(RuntimeError):
        camp.freeze()


def test_held_frozen_and_ceiling(camp, monkeypatch):
    camp.start()
    # pretend DEV arm A complete so the freeze is allowed (B/C DEV may follow the freeze)
    for c in camp.cells():
        if c["phase"] == "dev" and c["arm"] == "A":
            camp._append(camp.RESULTS, dict(key=camp.key(c), valid=True))
    f = camp.freeze()
    assert f["a_active_at_freeze"] == 1
    held = json.loads(camp.B_HELD.read_text())
    assert [r["status"] for r in held["rules"]] == ["active"]
    a_sha = _sha(camp.A_PB)
    log = []
    for arm in ("A", "B", "C"):
        r = camp.run_cell(fake_llm(log), dict(phase="held", circuit="tfim_6", arm=arm, eps=1e-3, calls=8))
        assert r["stats"]["reflect_calls"] == 0 and r["valid"]
    assert _sha(camp.A_PB) == a_sha and not any(x["model"] == camp.REFLECTOR for x in log)
    # ceiling signature -> invalid row; next attempt gets a fresh tag suffix
    cell = dict(phase="held", circuit="qpe_8", arm="C", eps=1e-3, calls=4)
    r = camp.run_cell(fake_llm([], ceiling=True), cell)
    assert r["ceiling_hit"] and not r["valid"] and camp.key(cell) not in camp.done_keys()
    assert camp._tag(cell)[0].endswith("_r2")


def _fake_row(c, arm, phase, eps, tb, ta):
    st = dict(accepted=1, exact_accepts=1, approx_accepts=0, proposal_calls=40, reflect_calls=0)
    return dict(key=f"{phase}|{c}|{arm}|{ac.elabel(eps)}", phase=phase, circuit=c, arm=arm, eps=eps, valid=True,
                t_before=tb, t_after=ta, stats=st, ledger=dict(window_spent=0.0),
                routing=dict(family="dv.windows", contract="unitary"))


def test_futility_and_report(camp):
    camp.start()
    for c in camp.DEV[:3]:                    # A worse than C by 10 pp on every circuit -> fires
        for arm, ta in (("A", 1000), ("B", 950), ("C", 900)):
            camp._append(camp.RESULTS, _fake_row(c, arm, "dev", 1e-3, 1000, ta))
    f = camp.futility()
    assert f["fired"] and abs(f["mean_A_minus_C_pp"] + 10.0) < 1e-9
    assert camp.run_chunk(lambda *a, **k: None)["stopped"] == "futility"
    rep = camp.report("REPORT_test")
    assert rep["paired"]["dev|0.001|A-C"]["n"] == 3
    with pytest.raises(FileExistsError):
        camp.report("REPORT_test")            # append-only


def test_infra_failure_restores_arm_a(camp):
    camp.start()
    sha0 = _sha(camp.A_PB)
    def dead(reqs, max_concurrency=4):
        return [{"error": "No credentials available for Anthropic API"}] * len(reqs)
    r = camp.run_cell(dead, dict(phase="dev", circuit="hubbard_8", arm="A", eps=1e-3, calls=8))
    assert r["infra_fail"] and not r["valid"] and r["a_playbook_restored"]
    assert _sha(camp.A_PB) == sha0 and not list(camp.OUT.glob("_A_backup_*"))


def test_watchdog_retries_hung_batch(monkeypatch):
    import time as _t
    from circuitevolve.llm_backends import make_api_backend
    n = {"k": 0}
    def flaky(reqs, max_concurrency=4):
        n["k"] += 1
        if n["k"] == 1:
            _t.sleep(1.0)                       # first batch "hangs"
        return [{"text": "NONE"} for _ in reqs]
    be = make_api_backend(ac.with_watchdog(flaky, timeout_s=0.2), model="m", backoff=0.0, sleep=lambda s: None)
    assert be(["a", "b"]) == ["NONE", "NONE"] and n["k"] == 2
