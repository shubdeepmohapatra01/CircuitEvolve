"""P1 gate: the verifier must classify every acceptance case correctly (verdict and level)."""
import pytest

from circuitevolve.acceptance import cases
from circuitevolve.spec import AdderSpec
from circuitevolve.verify import verify


@pytest.mark.parametrize("case", cases(), ids=lambda c: c.name)
def test_acceptance_case(case):
    r = verify(case.construct, AdderSpec(), case.n_values, case.vocab)
    assert r.ok == case.expect_ok, r.reason
    assert r.level == case.expect_level, (r.level, r.reason)


def test_suite_size():
    cs = cases()
    assert sum(not c.expect_ok for c in cs) >= 12


@pytest.mark.parametrize("case", cases(), ids=lambda c: c.name)
def test_acceptance_case_with_gadget_lemma(case):
    """The search-loop shortcut must not change any verdict on the acceptance suite."""
    from circuitevolve.verify import Limits
    r = verify(case.construct, AdderSpec(), case.n_values, case.vocab, Limits(trust_gadget_lemma=True))
    assert r.ok == case.expect_ok, r.reason
    assert r.level == case.expect_level, (r.level, r.reason)
