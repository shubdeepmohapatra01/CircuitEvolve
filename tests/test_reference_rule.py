"""End to end on a real benchmark: a hand-written Gidney rule must be accepted and must lower the final T-count.
Guards the whole acceptance path (prepare -> worker subprocess -> verifier with clean ancillas -> score)."""
import json
import os

from circuitevolve import loop

RULE = os.path.join(os.path.dirname(__file__), "fixtures", "gidney_pairs.py")


def test_gidney_pairs_on_tof_4():
    e = [x for x in json.load(open(os.path.join(loop.ROOT, "splits.json")))["train"] if x["name"] == "tof_4"][0]
    c, eps = loop.prepare(e, "L0")
    c.zero_init = tuple(e["zero_init"])
    sc = lambda x, ep: loop.score("L1", "toffoli", x, ep)
    rec = loop.apply_once(RULE, c, eps, 0.0, sc, e["zero_init"])
    assert rec["verdict"] == "ok" and rec["mode"] != "nochange", rec
    assert rec["t_before"] == 23 and rec["t_after"] == 15
