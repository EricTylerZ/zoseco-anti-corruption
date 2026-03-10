"""
Auto-roll logic for expiring positions.

When a position reaches 21 DTE (days to expiration), evaluate whether to:
1. Roll forward (close and re-open at later expiry)
2. Hold (if thesis is triggering and position is profitable)
3. Close (if thesis is invalidated or budget is exhausted)
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple

from config.settings import ROLL_DTE_TRIGGER, TARGET_DTE, MIN_DTE, MAX_DTE
from core.models import Position, SpreadTrade, ScanResult
from strategy.scanner import scan_thesis
from strategy.portfolio import Portfolio


def find_positions_to_roll(portfolio: Portfolio) -> List[Position]:
    """Find open positions that need rolling (DTE <= ROLL_DTE_TRIGGER)."""
    open_positions = portfolio.get_open_positions()
    to_roll = []

    now = datetime.now()
    for position in open_positions:
        if not position.trade or not position.trade.legs:
            continue

        # Get expiration from the first leg
        expiry_str = position.trade.legs[0].expiration
        try:
            expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
        except (ValueError, TypeError):
            continue

        dte = (expiry - now).days
        if dte <= ROLL_DTE_TRIGGER:
            to_roll.append(position)

    return to_roll


def suggest_rolls(
    positions_to_roll: List[Position],
    portfolio: Portfolio,
    redis_client=None,
) -> List[Dict]:
    """
    For each position that needs rolling, suggest a replacement trade.

    Returns list of roll suggestions with:
    - position: the expiring position
    - recommendation: "roll", "hold", or "close"
    - new_trade: ScanResult for the replacement (if rolling)
    - reason: explanation
    """
    suggestions = []
    summary = portfolio.get_summary()
    remaining_budget = summary["remaining_budget"]

    for position in positions_to_roll:
        if not position.trade:
            continue

        thesis_id = position.trade.thesis_id
        now = datetime.now()
        expiry_str = position.trade.legs[0].expiration
        expiry = datetime.strptime(expiry_str, "%Y-%m-%d")
        dte = (expiry - now).days

        # Scan for replacement trades
        # Budget for roll = what we might recover from closing + remaining budget
        # Conservative: assume we recover 20% of original debit on close
        recovery_estimate = position.entry_cost * 0.20
        roll_budget = recovery_estimate + min(remaining_budget, 10)  # allow $10 extra

        new_trades = scan_thesis(thesis_id, roll_budget, redis_client)

        if dte <= 0:
            # Expired or expiring today
            suggestions.append({
                "position": position,
                "recommendation": "close",
                "new_trade": new_trades[0] if new_trades else None,
                "reason": f"Position expired/expiring (DTE={dte})",
            })
        elif new_trades:
            suggestions.append({
                "position": position,
                "recommendation": "roll",
                "new_trade": new_trades[0],
                "reason": (
                    f"DTE={dte} <= {ROLL_DTE_TRIGGER}. "
                    f"Best replacement: {new_trades[0].ticker} "
                    f"{new_trades[0].long_strike}/{new_trades[0].short_strike} "
                    f"exp {new_trades[0].expiration} "
                    f"(cost ${new_trades[0].net_debit:.2f}, "
                    f"R/R {new_trades[0].risk_reward:.1f}x)"
                ),
            })
        else:
            suggestions.append({
                "position": position,
                "recommendation": "hold",
                "new_trade": None,
                "reason": (
                    f"DTE={dte} <= {ROLL_DTE_TRIGGER} but no suitable "
                    f"replacement found within budget"
                ),
            })

    return suggestions


def format_roll_suggestions(suggestions: List[Dict]) -> str:
    """Format roll suggestions as readable text."""
    if not suggestions:
        return "No positions need rolling at this time."

    lines = []
    lines.append("=" * 60)
    lines.append("ROLL SUGGESTIONS")
    lines.append(f"Positions needing attention: {len(suggestions)}")
    lines.append("=" * 60)

    for s in suggestions:
        pos = s["position"]
        trade = pos.trade
        lines.append(f"\nPosition {pos.id}: {trade.ticker} {trade.spread_type}")
        lines.append(f"  Entry cost: ${pos.entry_cost:.2f}")
        lines.append(f"  Recommendation: {s['recommendation'].upper()}")
        lines.append(f"  Reason: {s['reason']}")

        if s["new_trade"]:
            nt = s["new_trade"]
            lines.append(f"  Replacement: {nt.ticker} {nt.long_strike}/{nt.short_strike}")
            lines.append(f"    Expiry: {nt.expiration} ({nt.dte} DTE)")
            lines.append(f"    Cost: ${nt.net_debit:.2f} | R/R: {nt.risk_reward:.1f}x")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
