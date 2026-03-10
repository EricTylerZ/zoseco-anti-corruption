"""Tests for strategy advisor tools."""

import pytest
from strategy.advisor import (
    _calculate_rsi,
    _calculate_iv_rank,
    _find_support_resistance,
    _dedupe_levels,
    _get_sector,
    theta_decay_optimizer,
    wheel_tracker,
    position_size_stress,
    portfolio_correlation_audit,
    leap_tax_timer,
    ADVISOR_NAMES,
    list_advisors,
)


# ── Helper function tests ──────────────────────────────────────────────


class TestCalculateRSI:
    def test_insufficient_data(self):
        history = [{"close": 100}] * 10
        assert _calculate_rsi(history) is None

    def test_all_gains(self):
        # 20 consecutive up days → RSI near 100
        history = [{"close": 100 + i} for i in range(20)]
        rsi = _calculate_rsi(history, period=14)
        assert rsi is not None
        assert rsi > 90

    def test_all_losses(self):
        # 20 consecutive down days → RSI near 0
        history = [{"close": 120 - i} for i in range(20)]
        rsi = _calculate_rsi(history, period=14)
        assert rsi is not None
        assert rsi < 10

    def test_mixed_returns(self):
        # Alternating up/down → RSI near 50
        history = []
        price = 100
        for i in range(30):
            price += 1 if i % 2 == 0 else -1
            history.append({"close": price})
        rsi = _calculate_rsi(history, period=14)
        assert rsi is not None
        assert 40 < rsi < 60

    def test_none_closes_filtered(self):
        history = [{"close": None}] * 5 + [{"close": 100 + i} for i in range(20)]
        rsi = _calculate_rsi(history, period=14)
        assert rsi is not None


class TestCalculateIVRank:
    def test_empty_chain(self):
        result = _calculate_iv_rank({"puts": [], "calls": []})
        assert result["environment"] == "unknown"
        assert result["iv_rank"] == 0

    def test_high_iv(self):
        # All IVs clustered high
        options = [{"implied_volatility": 0.80 + i * 0.01} for i in range(10)]
        result = _calculate_iv_rank({"puts": options, "calls": []})
        assert result["iv_mean"] > 0.5
        assert result["sample_size"] == 10

    def test_low_iv(self):
        options = [{"implied_volatility": 0.10 + i * 0.005} for i in range(10)]
        result = _calculate_iv_rank({"puts": [], "calls": options})
        assert result["iv_mean"] < 0.20

    def test_filters_zero_iv(self):
        options = [
            {"implied_volatility": 0.0},
            {"implied_volatility": 0.005},
            {"implied_volatility": 0.30},
            {"implied_volatility": 0.35},
        ]
        result = _calculate_iv_rank({"puts": options, "calls": []})
        assert result["sample_size"] == 2  # only 0.30 and 0.35 pass filter


class TestSupportResistance:
    def test_insufficient_data(self):
        result = _find_support_resistance([])
        assert result == {"supports": [], "resistances": []}

    def test_finds_swing_low(self):
        # Create a V-shaped pattern
        history = [
            {"high": 110, "low": 105, "close": 108},
            {"high": 108, "low": 103, "close": 105},
            {"high": 103, "low": 98, "close": 100},  # swing low
            {"high": 105, "low": 100, "close": 103},
            {"high": 108, "low": 104, "close": 107},
        ]
        result = _find_support_resistance(history)
        assert len(result["supports"]) >= 1
        assert result["supports"][0] == 98

    def test_finds_swing_high(self):
        # Create an inverted V pattern
        history = [
            {"high": 100, "low": 95, "close": 98},
            {"high": 105, "low": 100, "close": 103},
            {"high": 110, "low": 106, "close": 108},  # swing high
            {"high": 105, "low": 100, "close": 102},
            {"high": 100, "low": 96, "close": 98},
        ]
        result = _find_support_resistance(history)
        assert len(result["resistances"]) >= 1
        assert result["resistances"][0] == 110


class TestDedupeLevels:
    def test_empty(self):
        assert _dedupe_levels([]) == []

    def test_no_duplicates(self):
        assert _dedupe_levels([100, 110, 120]) == [100, 110, 120]

    def test_removes_close_levels(self):
        # 100 and 100.5 are within 1% → keep only first
        result = _dedupe_levels([100, 100.5, 110])
        assert len(result) == 2
        assert result[0] == 100
        assert result[1] == 110


class TestGetSector:
    def test_known_ticker(self):
        assert _get_sector("AAPL") == "Technology"
        assert _get_sector("TSN") == "Consumer Staples"
        assert _get_sector("VNO") == "Real Estate"

    def test_unknown_ticker(self):
        assert _get_sector("ZZZZZ") == "Unknown"

    def test_case_insensitive(self):
        assert _get_sector("aapl") == "Technology"


# ── Calculation-heavy tool tests ───────────────────────────────────────


class TestThetaDecayOptimizer:
    def test_basic_output(self):
        result = theta_decay_optimizer("TEST", "put", 2.50, 30)
        assert "THETA DECAY OPTIMIZER" in result
        assert "50% Profit Target" in result
        assert "$1.25" in result  # 50% of 2.50
        assert "Annualized Return" in result

    def test_custom_dte(self):
        result = theta_decay_optimizer("TEST", "call", 1.00, 45)
        assert "45" in result


class TestWheelTracker:
    def test_single_csp_expired(self):
        cycles = [{"type": "csp", "strike": 50, "premium": 1.50, "assigned": False}]
        result = wheel_tracker("TEST", cycles)
        assert "WHEEL CYCLE TRACKER" in result
        assert "$1.50" in result
        assert "Complete Cycles:       1" in result

    def test_full_wheel_cycle(self):
        cycles = [
            {"type": "csp", "strike": 50, "premium": 1.50, "assigned": True},
            {"type": "cc", "strike": 55, "premium": 1.00, "assigned": True},
        ]
        result = wheel_tracker("TEST", cycles)
        assert "Total Premium:         $2.50" in result
        assert "Complete Cycles:       1" in result  # CSP+CC = 1 full wheel cycle

    def test_holding_shares(self):
        cycles = [
            {"type": "csp", "strike": 50, "premium": 1.50, "assigned": True},
        ]
        result = wheel_tracker("TEST", cycles)
        assert "Currently Holding:     100 shares" in result
        assert "Adjusted Cost Basis:" in result


class TestPositionSizeStress:
    def test_output_format(self):
        result = position_size_stress("TEST", 50000, redis_client=None)
        # Will fail to get price, but should handle gracefully
        assert "ERROR" in result or "POSITION SIZING" in result

    def test_with_existing_positions(self):
        positions = [
            {"ticker": "AAPL", "allocation_pct": 20},
            {"ticker": "MSFT", "allocation_pct": 15},
        ]
        result = position_size_stress("TEST", 50000, positions)
        assert "ERROR" in result or "SECTOR OVERLAP" in result


class TestPortfolioCorrelationAudit:
    def test_empty_positions(self):
        result = portfolio_correlation_audit([])
        assert "No positions" in result

    def test_sector_concentration(self):
        positions = [
            {"ticker": "AAPL", "allocation_pct": 25},
            {"ticker": "MSFT", "allocation_pct": 20},
            {"ticker": "GOOGL", "allocation_pct": 15},
        ]
        result = portfolio_correlation_audit(positions)
        assert "CONCENTRATED" in result  # 60% in Technology
        assert "Technology" in result

    def test_finds_correlations(self):
        positions = [
            {"ticker": "AAPL", "allocation_pct": 20},
            {"ticker": "MSFT", "allocation_pct": 15},
            {"ticker": "QQQ", "allocation_pct": 10},
        ]
        result = portfolio_correlation_audit(positions)
        assert "Risk-On Equities" in result
        assert "move together" in result.lower() or "ALL drop together" in result

    def test_diversified_portfolio(self):
        positions = [
            {"ticker": "AAPL", "allocation_pct": 10},
            {"ticker": "GLD", "allocation_pct": 10},
            {"ticker": "VNO", "allocation_pct": 10},
        ]
        result = portfolio_correlation_audit(positions)
        # Should not flag concentration
        assert "CONCENTRATED" not in result

    def test_cut_recommendation(self):
        positions = [
            {"ticker": "VNO", "allocation_pct": 15},
            {"ticker": "SLG", "allocation_pct": 15},
            {"ticker": "BXP", "allocation_pct": 15},
            {"ticker": "GLD", "allocation_pct": 10},
        ]
        result = portfolio_correlation_audit(positions)
        assert "CUT:" in result


class TestLeapTaxTimer:
    def test_basic_output(self):
        result = leap_tax_timer("TEST", "2025-06-15", 500, 24)
        # Will fail price fetch, but should handle error
        assert "ERROR" in result or "LEAP TAX TIMER" in result


# ── Metadata tests ─────────────────────────────────────────────────────


class TestAdvisorMetadata:
    def test_all_12_advisors_named(self):
        assert len(ADVISOR_NAMES) == 12
        for i in range(1, 13):
            assert i in ADVISOR_NAMES

    def test_list_advisors(self):
        result = list_advisors()
        assert "IV Environment Scanner" in result
        assert "Pre-Trade Exit Plan" in result
        assert "12." in result
