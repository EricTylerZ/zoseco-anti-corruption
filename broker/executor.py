"""
Trade execution logic.

Takes scanner recommendations and executes them through Alpaca,
with validation and safety checks.
"""

import json
from datetime import datetime
from typing import List, Dict, Optional

from core.models import SpreadTrade, OptionLeg, Position, ScanResult
from strategy.portfolio import Portfolio
from config.theses import TOTAL_CAPITAL
from config.settings import MAX_POSITIONS_PER_THESIS, MAX_TOTAL_POSITIONS


def validate_trade(
    scan_result: ScanResult,
    portfolio: Portfolio,
) -> Dict:
    """
    Validate a trade before execution.

    Checks:
    - Budget available
    - Position limits not exceeded
    - Not a duplicate of existing position
    """
    summary = portfolio.get_summary()
    remaining = summary["remaining_budget"]

    if scan_result.net_debit > remaining:
        return {
            "valid": False,
            "reason": f"Insufficient budget. Need ${scan_result.net_debit:.2f}, have ${remaining:.2f}",
        }

    open_positions = portfolio.get_open_positions()

    if len(open_positions) >= MAX_TOTAL_POSITIONS:
        return {
            "valid": False,
            "reason": f"Max total positions ({MAX_TOTAL_POSITIONS}) reached",
        }

    thesis_positions = [
        p for p in open_positions
        if p.trade and p.trade.thesis_id == scan_result.thesis_id
    ]
    if len(thesis_positions) >= MAX_POSITIONS_PER_THESIS:
        return {
            "valid": False,
            "reason": f"Max positions for {scan_result.thesis_name} ({MAX_POSITIONS_PER_THESIS}) reached",
        }

    # Check for duplicate (same ticker + same strikes + same expiry)
    for p in open_positions:
        if not p.trade:
            continue
        if (p.trade.ticker == scan_result.ticker
                and len(p.trade.legs) >= 2
                and p.trade.legs[0].strike == scan_result.long_strike
                and p.trade.legs[1].strike == scan_result.short_strike
                and p.trade.legs[0].expiration == scan_result.expiration):
            return {
                "valid": False,
                "reason": f"Duplicate position: {scan_result.ticker} {scan_result.long_strike}/{scan_result.short_strike} exp {scan_result.expiration}",
            }

    return {"valid": True, "reason": "OK"}


def build_trade_from_scan(scan_result: ScanResult) -> SpreadTrade:
    """Convert a ScanResult into a SpreadTrade ready for execution."""
    if scan_result.direction == "bearish":
        # Put debit spread: buy higher strike, sell lower strike
        long_leg = OptionLeg(
            ticker=scan_result.ticker,
            option_type="put",
            strike=scan_result.long_strike,
            expiration=scan_result.expiration,
            action="buy",
            premium=0,  # will be filled at execution
            quantity=1,
        )
        short_leg = OptionLeg(
            ticker=scan_result.ticker,
            option_type="put",
            strike=scan_result.short_strike,
            expiration=scan_result.expiration,
            action="sell",
            premium=0,
            quantity=1,
        )
    else:
        # Call debit spread: buy lower strike, sell higher strike
        long_leg = OptionLeg(
            ticker=scan_result.ticker,
            option_type="call",
            strike=scan_result.long_strike,
            expiration=scan_result.expiration,
            action="buy",
            premium=0,
            quantity=1,
        )
        short_leg = OptionLeg(
            ticker=scan_result.ticker,
            option_type="call",
            strike=scan_result.short_strike,
            expiration=scan_result.expiration,
            action="sell",
            premium=0,
            quantity=1,
        )

    return SpreadTrade(
        thesis_id=scan_result.thesis_id,
        ticker=scan_result.ticker,
        legs=[long_leg, short_leg],
        spread_type=scan_result.spread_type,
        net_debit=scan_result.net_debit,
        max_profit=scan_result.max_profit,
        breakeven=scan_result.breakeven,
        risk_reward=scan_result.risk_reward,
        status="planned",
    )


def execute_trade(
    scan_result: ScanResult,
    portfolio: Portfolio,
    dry_run: bool = False,
) -> Dict:
    """
    Execute a trade: validate, build, place order, record position.

    Args:
        scan_result: The recommended trade from scanner
        portfolio: Portfolio for tracking
        dry_run: If True, validate and build but don't place order

    Returns:
        Dict with execution result
    """
    # Validate
    validation = validate_trade(scan_result, portfolio)
    if not validation["valid"]:
        return {
            "success": False,
            "stage": "validation",
            "reason": validation["reason"],
        }

    # Build trade
    trade = build_trade_from_scan(scan_result)

    if dry_run:
        return {
            "success": True,
            "stage": "dry_run",
            "trade": trade.to_dict(),
            "message": "Trade validated. Set dry_run=False to execute.",
        }

    # Execute via Alpaca
    try:
        from broker.alpaca_client import place_spread_order
        order_result = place_spread_order(trade)

        if "error" in order_result:
            return {
                "success": False,
                "stage": "execution",
                "reason": order_result["error"],
                "trade": trade.to_dict(),
            }

        # Record position
        trade.status = "open"
        position = Position(
            trade=trade,
            entry_cost=scan_result.net_debit,
            notes=f"Auto-executed. Order: {order_result.get('order_id', 'unknown')}",
        )
        portfolio.add_position(position)

        return {
            "success": True,
            "stage": "executed",
            "position_id": position.id,
            "order": order_result,
            "trade": trade.to_dict(),
        }

    except Exception as e:
        return {
            "success": False,
            "stage": "execution",
            "reason": str(e),
            "trade": trade.to_dict(),
        }


def execute_best_trades(
    scan_results: Dict[str, List[ScanResult]],
    portfolio: Portfolio,
    dry_run: bool = False,
) -> List[Dict]:
    """
    Execute the best trade for each thesis (if budget allows).

    Takes the top recommendation per thesis and tries to execute.
    """
    results = []

    for thesis_id, thesis_results in scan_results.items():
        if not thesis_results:
            results.append({
                "thesis_id": thesis_id,
                "success": False,
                "reason": "No trades found for this thesis",
            })
            continue

        # Take the best (highest risk/reward) result
        best = thesis_results[0]
        result = execute_trade(best, portfolio, dry_run=dry_run)
        result["thesis_id"] = thesis_id
        results.append(result)

    return results
