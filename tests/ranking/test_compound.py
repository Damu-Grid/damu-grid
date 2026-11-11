"""DG-19 step 1: the compound Poisson law (Panjer recursion) against known results."""

from __future__ import annotations

import math

import numpy as np
import pytest

from ranking.compound import panjer_pmf

SIZES = [0.5, 0.25, 0.15, 0.05, 0.03, 0.02]


@pytest.mark.parametrize("rate", [0.0, 0.3, 2.5, 12.0])
@pytest.mark.parametrize("cap", [0, 3, 40])
def test_pmf_sums_to_one(rate, cap):
    pmf = panjer_pmf(rate, SIZES, cap)
    assert pmf.shape == (cap + 1,)
    assert pmf.sum() == pytest.approx(1.0, abs=1e-12)
    assert (pmf >= 0).all()


def test_single_unit_requests_give_poisson():
    pmf = panjer_pmf(3.2, [1.0], 30)
    expected = np.array([math.exp(-3.2) * 3.2**n / math.factorial(n) for n in range(30)])
    assert np.allclose(pmf[:30], expected, atol=1e-12)
    assert pmf[30] == pytest.approx(1.0 - expected.sum(), abs=1e-12)  # tail mass in the last cell


def test_mean_and_variance_match_theory():
    rate = 2.4
    pmf = panjer_pmf(rate, SIZES, 400)
    n = np.arange(401)
    k = np.arange(1, len(SIZES) + 1)
    mean_k, second_k = float((k * SIZES).sum()), float((k**2 * SIZES).sum())
    mean = float((n * pmf).sum())
    var = float((n**2 * pmf).sum()) - mean**2
    assert mean == pytest.approx(rate * mean_k, rel=1e-9)
    assert var == pytest.approx(rate * second_k, rel=1e-9)


def test_zero_rate_is_a_point_mass_at_zero():
    pmf = panjer_pmf(0.0, SIZES, 5)
    assert pmf[0] == 1.0 and pmf[1:].sum() == 0.0


def test_tail_mass_lands_in_last_cell():
    full = panjer_pmf(5.0, SIZES, 200)
    short = panjer_pmf(5.0, SIZES, 4)
    assert np.allclose(short[:4], full[:4], atol=1e-12)
    assert short[4] == pytest.approx(full[4:].sum(), abs=1e-12)


@pytest.mark.parametrize(
    "rate, sizes, cap",
    [
        (-1.0, [1.0], 3),
        (float("nan"), [1.0], 3),
        (1.0, [], 3),
        (1.0, [0.5, 0.4], 3),
        (1.0, [1.5, -0.5], 3),
        (1.0, [1.0], -1),
    ],
)
def test_invalid_inputs_are_refused(rate, sizes, cap):
    with pytest.raises(ValueError):
        panjer_pmf(rate, sizes, cap)
