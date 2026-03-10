"""
Tests for the strategy scanner.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import ScanResult, SpreadTrade, OptionLeg, Position
from broker.executor import validate_trade, build_trade_from_scan
from strategy.portfolio import Portfolio


def test_scan_result_creation():
    """Test ScanResult dataclass."""
    result = ScanResult(
        thesis_id="nyc_housing",
        thesis_name="NYC Housing Drop",
        ticker="VNO",
        spread_type="put_debit_spread",
        long_strike=26.0,
        short_strike=24.0,
        expiration="2026-05-15",
        net_debit=25.0,
        max_profit=175.0,
        breakeven=25.75,
        risk_reward=7.0,
        current_price=28.50,
        dte=66,
        direction="bearish",
    )

    assert result.ticker == "VNO"
    assert result.net_debit == 25.0
    d = result.to_dict()
    assert d["thesis_id"] == "nyc_housing"


def test_build_trade_from_bearish_scan():
    """Test building a put debit spread trade from scan result."""
    scan = ScanResult(
        thesis_id="beef_imports",
        thesis_name="Beef Import Surge",
        ticker="TSN",
        spread_type="put_debit_spread",
        long_strike=50.0,
        short_strike=47.5,
        expiration="2026-05-15",
        net_debit=30.0,
        max_profit=220.0,
        breakeven=49.70,
        risk_reward=7.33,
        current_price=55.0,
        dte=66,
        direction="bearish",
    )

    trade = build_trade_from_scan(scan)

    assert trade.ticker == "TSN"
    assert trade.spread_type == "put_debit_spread"
    assert len(trade.legs) == 2
    assert trade.legs[0].option_type == "put"
    assert trade.legs[0].action == "buy"
    assert trade.legs[0].strike == 50.0
    assert trade.legs[1].action == "sell"
    assert trade.legs[1].strike == 47.5


def test_build_trade_from_bullish_scan():
    """Test building a call debit spread trade from scan result."""
    scan = ScanResult(
        thesis_id="dollar_collapse",
        thesis_name="Monetary System Collapse",
        ticker="SLV",
        spread_type="call_debit_spread",
        long_strike=31.0,
        short_strike=33.0,
        expiration="2026-05-15",
        net_debit=20.0,
        max_profit=180.0,
        breakeven=31.20,
        risk_reward=9.0,
        current_price=29.0,
        dte=66,
        direction="bullish",
    )

    trade = build_trade_from_scan(scan)

    assert trade.legs[0].option_type == "call"
    assert trade.legs[0].action == "buy"
    assert trade.legs[0].strike == 31.0
    assert trade.legs[1].action == "sell"
    assert trade.legs[1].strike == 33.0


def test_position_serialization():
    """Test Position to/from JSON."""
    trade = SpreadTrade(
        thesis_id="nyc_housing",
        ticker="VNO",
        legs=[
            OptionLeg("VNO", "put", 26.0, "2026-05-15", "buy", 0.50, 1),
            OptionLeg("VNO", "put", 24.0, "2026-05-15", "sell", 0.25, 1),
        ],
        spread_type="put_debit_spread",
        net_debit=25.0,
        max_profit=175.0,
        breakeven=25.75,
        risk_reward=7.0,
    )

    position = Position(
        trade=trade,
        entry_cost=25.0,
        notes="Test position",
    )

    json_str = position.to_json()
    restored = Position.from_json(json_str)

    assert restored.entry_cost == 25.0
    assert restored.trade.ticker == "VNO"
    assert len(restored.trade.legs) == 2
    assert restored.trade.legs[0].strike == 26.0


def test_option_leg_cost():
    """Test OptionLeg total cost calculation."""
    buy_leg = OptionLeg("TSN", "put", 50.0, "2026-05-15", "buy", 2.10, 1)
    sell_leg = OptionLeg("TSN", "put", 47.5, "2026-05-15", "sell", 0.80, 1)

    assert buy_leg.total_cost == -210.0  # buying costs money (negative)
    assert sell_leg.total_cost == 80.0   # selling receives credit (positive)

    net = buy_leg.total_cost + sell_leg.total_cost
    assert net == -130.0  # net debit of $130 per contract


if __name__ == "__main__":
    tests = [
        test_scan_result_creation,
        test_build_trade_from_bearish_scan,
        test_build_trade_from_bullish_scan,
        test_position_serialization,
        test_option_leg_cost,
    ]
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
