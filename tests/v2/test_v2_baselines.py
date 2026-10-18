"""v2 baselines: reused numbers, validity rules, eps keys, merge hook for results/v2/baselines_new.csv."""
import pandas as pd
import pytest

from circuitevolve.v2 import baselines as bl

STAGE1 = ("qft_8", "qpe_8", "qae_13", "heisenberg_6", "tfim_6", "hubbard_8", "qml_13", "hhl_8")


@pytest.fixture(scope="module")
def tab():
    return bl.table(include_new=False)


def test_sources_and_row_counts(tab):
    raw = pd.read_csv(bl.STAGE1_CSV)
    assert (tab.source == "stage1_v2").sum() == len(raw) == 112
    assert (tab.source == "reference_pipelines").sum() == len(pd.read_csv(bl.REFERENCE_CSV))
    assert not tab[tab.source == "published"]["comparable"].any()


def test_stage1_validity_rules(tab):
    s = tab[tab.source == "stage1_v2"]
    valid = s.groupby("arm")["valid"].all().to_dict()
    assert valid == {"B0": True, "B1": True, "B2": True, "B2ft": False, "B3": False, "B3g": True, "B3m": True}


def test_best_matches_csv(tab):
    raw = pd.read_csv(bl.STAGE1_CSV)
    ok = raw[raw.measured_within_eps & ((raw.bound_over_eps <= 1 + 1e-9) | (raw.arm == "B2"))]
    for c in STAGE1:
        for eps in (1e-3, 1e-5):
            b = bl.best_classical(c, eps, tab=tab)
            sub = ok[(ok.circuit == c) & (ok.eps_total == eps)]
            assert b["t_count"] == sub.t_count_canon.min() and b["arm"] != "B3"
            p = bl.best_classical(c, eps, arms="primary", tab=tab)
            assert p["t_count"] == sub[sub.primary_arm].t_count_canon.min()
            assert b["t_count"] <= p["t_count"]


def test_b3_never_wins_at_1e5(tab):
    # B3's 1e-5 rows are 21.5 x over budget (stage-1 README); the bar must come from a valid arm
    for c in ("heisenberg_6", "qml_13"):
        b = bl.best_classical(c, 1e-5, tab=tab)
        b3 = tab[(tab.circuit == c) & (tab.arm == "B3") & (tab.eps_setting == "1e-05")].t_count.iloc[0]
        assert b["arm"] != "B3" and b["t_count"] > b3


def test_eps_settings_never_mix(tab):
    assert bl.best_classical("add_17", 1e-3, tab=tab) is None
    b = bl.best_classical("add_17", bl.LEGACY_RZ_1E9, tab=tab)
    raw = pd.read_csv(bl.REFERENCE_CSV)
    assert b["t_count"] == raw[raw.circuit == "add_17"].t_count.min()
    assert bl.best_classical("qft_8", 1e-4, tab=tab) is None


def test_new_rows_merge(tmp_path):
    p = tmp_path / "baselines_new.csv"
    pd.DataFrame([dict(circuit="adder_8", source="pyzx 0.10.7", arm="pyzx", eps=1e-3, t_count=100, qubits=24,
                       notes="exact Clifford+T"),
                  dict(circuit="adder_8", source="tket", arm="tket", eps=1e-3, t_count=90, qubits=24,
                       notes="INVALID: failed check"),
                  dict(circuit="qft_8", source="tket", arm="X", eps=1e-3, t_count=10, qubits=8,
                       notes="")]).to_csv(p, index=False)
    t = bl.table(new_path=p)
    b = bl.best_classical("adder_8", 1e-3, tab=t)
    assert b["t_count"] == 100 and b["source"] == "v2_new"           # the INVALID row is skipped
    assert bl.best_classical("qft_8", 1e-3, tab=t)["arm"] == "X"     # new rows compete with stage-1 arms
    bad = tmp_path / "bad.csv"
    pd.DataFrame([dict(circuit="a", eps=1e-3)]).to_csv(bad, index=False)
    with pytest.raises(ValueError):
        bl.load_new(bad)
    assert len(bl.load_new(tmp_path / "missing.csv")) == 0


def test_canonical_names():
    assert bl.canonical_name("Add-17") == "add_17"
    assert bl.canonical_name("Heisenberg-7q") == "heisenberg_7"
    assert bl.canonical_name("QFTAdd8 (16q)") == "qftadd8"
