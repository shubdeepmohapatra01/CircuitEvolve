"""Build the playbook tier layout (PLAN_P1 P1.4) — machinery only, content copied verbatim.

    playbooks/router.json                 tier-0 table (families, contracts, preconditions)
    playbooks/families/dv.windows.json    copy of playbooks/dev_v1.json (stage-1 learned playbook)
    playbooks/families/cvdv.bosonic.json  cvdv/rulebook/playbook.md numbered insights as Playbook
                                          rules (text verbatim, origin=seed, status=candidate)
    playbooks/graduated/index.json        EMPTY hash-checked library

Originals are left untouched. Refuses to overwrite without --force.
Usage: .venv/bin/python experiments/engine_build_tiers.py [--force]
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
PB = REPO / "playbooks"

ROUTER = {
    "format": "circuitevolve.engine.router/0",
    "provenance": ("P1.4 initial table. dv.windows playbook copied from playbooks/dev_v1.json; "
                   "cvdv.bosonic converted from cvdv/rulebook/playbook.md (texts verbatim). "
                   "Routing: deterministic features only; LLM triage fallback + arithmetic family land in point 3."),
    "families": {
        "dv.windows": {
            "plugin": "dv_windows", "contract": "approx",
            "precondition": "QASM, 0 Toffolis, >=1 non-Clifford rz (rotation-dominated)",
            "playbook": "playbooks/families/dv.windows.json", "graduated": []},
        "cvdv.bosonic": {
            "plugin": "cvdv", "contract": "certified_subspace",
            "precondition": "Hamiltonian term input",
            "playbook": "playbooks/families/cvdv.bosonic.json", "graduated": []},
        "arithmetic": {
            "plugin": None, "contract": "relaxed", "status": "reserved",
            "precondition": "Toffoli-dominated QASM (reserved until dv_arith lands, point 3)",
            "playbook": "playbooks/families/arith.relaxed.json", "graduated": []},
    },
}


def build(force: bool = False):
    for p in (PB / "router.json", PB / "families", PB / "graduated"):
        if p.exists() and not force:
            raise SystemExit(f"{p} exists; tier layout is built once (use --force)")
    (PB / "families").mkdir(parents=True, exist_ok=True)
    (PB / "graduated").mkdir(parents=True, exist_ok=True)
    (PB / "router.json").write_text(json.dumps(ROUTER, indent=1) + "\n")

    # tier-1 dv.windows: byte-identical copy of the stage-1 learned playbook
    shutil.copyfile(PB / "dev_v1.json", PB / "families" / "dv.windows.json")

    # tier-1 cvdv.bosonic: numbered markdown insights -> Playbook rules, text verbatim
    sys.path.insert(0, str(REPO))
    from circuitevolve.search.playbook import Playbook

    md = (REPO / "cvdv" / "rulebook" / "playbook.md").read_text()
    items = re.findall(r"^(\d+)\.\s+(.*?)(?=^\d+\.\s|\Z)", md, re.M | re.S)
    pb = Playbook(evidence="improvement")
    for num, text in items:
        t = " ".join(text.split())
        pb.add(f"[cvdv rulebook #{num}] {t}", 0, origin="seed")
    pb.save(PB / "families" / "cvdv.bosonic.json")

    families: dict = {"dv.windows": [], "cvdv.bosonic": []}
    idx = {"format": "circuitevolve.engine.graduated/0",
           "provenance": "P1.4: empty library; first graduation lands in point 2",
           "families": families,
           "index_sha256_of_entries": hashlib.sha256(json.dumps(families, sort_keys=True).encode()).hexdigest()}
    (PB / "graduated" / "index.json").write_text(json.dumps(idx, indent=1) + "\n")
    print(f"built tier layout: router.json, families/ ({len(items)} cvdv seed rules), graduated/ (empty)")


if __name__ == "__main__":
    build(force="--force" in sys.argv[1:])
