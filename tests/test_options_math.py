"""
Tests for options math calculations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import math
from core.options_math import (
    norm_cdf,
    black_scholes_put,
    black_scholes_call,
    put_debit_spread_metrics,
    call_debit_spread_metrics,
    estimate_delta,
)


def test_norm_cdf():
    """Test normal CDF against known values."""
    assert abs(norm_cdf(0) - 0.5) < 1e-10
    assert abs(norm_cdf(1.96) - 0.975) < 0.001
    assert abs(norm_cdf(-1.96) - 0.025) < 0.001
    assert abs(norm_cdf(3.0) - 0.99865) < 0.001


def test_put_call_parity():
    """Test that put-call parity holds: C - P = S - K*e^(-rT)."""
    S, K, T, r, sigma = 50.0, 50.0, 0.25, 0.05, 0.30

    call = black_scholes_call(S, K, T, r, sigma)
    put = black_scholes_put(S, K, T, r, sigma)
    parity = S - K * math.exp(-r * T)

    assert abs((call - put) - parity) < 0.01, f"Put-call parity violated: {call - put} vs {parity}"


def test_black_scholes_put_atm():
    """Test BS put price for at-the-money option."""
    S, K, T, r, sigma = 50.0, 50.0, 0.25, 0.05, 0.30
    put = black_scholes_put(S, K, T, r, sigma)
    # ATM put should be roughly S * sigma * sqrt(T) / sqrt(2*pi) for small r
    approx = S * sigma * math.sqrt(T) / math.sqrt(2 * math.pi)
    assert abs(put - approx) < 1.0, f"ATM put {put} too far from approximation {approx}"
    assert put > 0


def test_black_scholes_deep_itm_put():
    """Deep ITM put should be close to intrinsic value."""
    S, K = 30.0, 50.0  # deep ITM put
    put = black_scholes_put(S, K, 0.01, 0.05, 0.30)
    intrinsic = K - S
    assert abs(put - intrinsic) < 1.0


def test_black_scholes_expired():
    """Expired option should return intrinsic value."""
    assert black_scholes_put(50, 60, 0, 0.05, 0.30) == 10.0
    assert black_scholes_put(60, 50, 0, 0.05, 0.30) == 0.0
    assert black_scholes_call(60, 50, 0, 0.05, 0.30) == 10.0
    assert black_scholes_call(50, 60, 0, 0.05, 0.30) == 0.0


def test_put_debit_spread_metrics():
    """Test put debit spread calculations."""
    # Buy $50 put, sell $45 put, net debit $2.00 per share
    metrics = put_debit_spread_metrics(50.0, 45.0, 2.0)

    assert metrics["max_loss"] == 200.0       # $2.00 * 100 shares
    assert metrics["max_profit"] == 300.0     # ($5 width - $2 debit) * 100
    assert metrics["breakeven"] == 48.0       # $50 - $2
    assert metrics["risk_reward"] == 1.5      # $300 / $200
    assert metrics["spread_width"] == 5.0


def test_call_debit_spread_metrics():
    """Test call debit spread calculations."""
    # Buy $30 call, sell $35 call, net debit $1.50 per share
    metrics = call_debit_spread_metrics(30.0, 35.0, 1.5)

    assert metrics["max_loss"] == 150.0       # $1.50 * 100
    assert metrics["max_profit"] == 350.0     # ($5 width - $1.50 debit) * 100
    assert metrics["breakeven"] == 31.5       # $30 + $1.50
    assert round(metrics["risk_reward"], 2) == 2.33


def test_delta_atm_call():
    """ATM call delta should be roughly 0.5."""
    delta = estimate_delta(50, 50, 0.25, 0.05, 0.30, "call")
    assert 0.45 < delta < 0.60


def test_delta_atm_put():
    """ATM put delta should be roughly -0.5."""
    delta = estimate_delta(50, 50, 0.25, 0.05, 0.30, "put")
    assert -0.60 < delta < -0.40


def test_spread_within_budget():
    """Verify a realistic $100 budget spread scenario."""
    # VNO put spread: buy $26P, sell $24P, net debit $0.25/share = $25/contract
    metrics = put_debit_spread_metrics(26.0, 24.0, 0.25)

    assert metrics["max_loss"] == 25.0   # fits in $30 thesis budget
    assert metrics["max_profit"] == 175.0  # ($2 width - $0.25) * 100
    assert metrics["breakeven"] == 25.75
    assert metrics["risk_reward"] == 7.0  # great risk/reward


if __name__ == "__main__":
    tests = [
        test_norm_cdf,
        test_put_call_parity,
        test_black_scholes_put_atm,
        test_black_scholes_deep_itm_put,
        test_black_scholes_expired,
        test_put_debit_spread_metrics,
        test_call_debit_spread_metrics,
        test_delta_atm_call,
        test_delta_atm_put,
        test_spread_within_budget,
    ]
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
