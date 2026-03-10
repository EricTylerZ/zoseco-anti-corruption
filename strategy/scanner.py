"""
Strategy scanner: finds the best option trades given budget and theses.

Scans live options chains for each thesis ticker and recommends
debit spreads that fit within the allocated budget.
"""

from typing import List, Dict, Optional
from datetime import datetime

from config.theses import THESES, TOTAL_CAPITAL
from config.settings import (
    MIN_DTE,
    MAX_DTE,
    TARGET_DTE,
    SPREAD_WIDTHS,
    MIN_VOLUME,
    MIN_OPEN_INTEREST,
    MAX_BID_ASK_SPREAD_PCT,
)
from core.models import ScanResult
from core.options_math import put_debit_spread_metrics, call_debit_spread_metrics
from data.market_data import get_options_chain, get_price


def scan_all(budget: float = TOTAL_CAPITAL, redis_client=None) -> Dict[str, List[ScanResult]]:
    """
    Scan all theses for trade opportunities.

    Returns dict keyed by thesis_id with list of ScanResult recommendations.
    """
    results = {}
    for thesis_id, thesis in THESES.items():
        thesis_budget = budget * thesis["allocation_pct"]
        results[thesis_id] = scan_thesis(thesis_id, thesis_budget, redis_client)
    return results


def scan_thesis(
    thesis_id: str,
    budget: float = None,
    redis_client=None,
) -> List[ScanResult]:
    """
    Scan a single thesis for the best trades within budget.

    Returns list of ScanResult sorted by risk/reward ratio (best first).
    """
    thesis = THESES.get(thesis_id)
    if not thesis:
        return []

    if budget is None:
        budget = TOTAL_CAPITAL * thesis["allocation_pct"]

    all_results = []

    for ticker, ticker_info in thesis["tickers"].items():
        ticker_budget = budget * ticker_info["weight"]
        direction = ticker_info["direction"]

        chain = get_options_chain(ticker, MIN_DTE, MAX_DTE, redis_client)
        if not chain.get("current_price"):
            continue

        current_price = chain["current_price"]

        if direction == "bearish":
            spreads = _find_put_spreads(
                ticker, chain, current_price, ticker_budget, thesis_id, thesis["name"]
            )
        else:  # bullish
            spreads = _find_call_spreads(
                ticker, chain, current_price, ticker_budget, thesis_id, thesis["name"]
            )

        all_results.extend(spreads)

    # Sort by risk/reward ratio descending
    all_results.sort(key=lambda r: r.risk_reward, reverse=True)
    return all_results


def _find_put_spreads(
    ticker: str,
    chain: Dict,
    current_price: float,
    max_budget: float,
    thesis_id: str,
    thesis_name: str,
) -> List[ScanResult]:
    """Find put debit spreads (bearish plays) within budget."""
    results = []
    puts = chain.get("puts", [])

    if not puts:
        return results

    # Group puts by expiration
    by_expiry = {}
    for put in puts:
        exp = put["expiration"]
        if exp not in by_expiry:
            by_expiry[exp] = []
        by_expiry[exp].append(put)

    for expiry, expiry_puts in by_expiry.items():
        # Sort by strike descending
        expiry_puts.sort(key=lambda p: p["strike"], reverse=True)

        for i, long_put in enumerate(expiry_puts):
            # Long put: buy this one (higher strike)
            if not _passes_liquidity_filter(long_put):
                continue

            for width in SPREAD_WIDTHS:
                short_strike = long_put["strike"] - width
                # Find matching short put
                short_put = _find_option_at_strike(expiry_puts, short_strike)
                if not short_put or not _passes_liquidity_filter(short_put):
                    continue

                # Calculate net debit using mid prices
                net_debit_per_share = long_put["mid"] - short_put["mid"]
                if net_debit_per_share <= 0:
                    continue

                net_debit_total = net_debit_per_share * 100  # per contract

                if net_debit_total > max_budget:
                    continue

                metrics = put_debit_spread_metrics(
                    long_put["strike"], short_put["strike"], net_debit_per_share
                )

                if metrics["risk_reward"] < 0.5:
                    continue

                results.append(ScanResult(
                    thesis_id=thesis_id,
                    thesis_name=thesis_name,
                    ticker=ticker,
                    spread_type="put_debit_spread",
                    long_strike=long_put["strike"],
                    short_strike=short_put["strike"],
                    expiration=expiry,
                    net_debit=net_debit_total,
                    max_profit=metrics["max_profit"],
                    breakeven=metrics["breakeven"],
                    risk_reward=metrics["risk_reward"],
                    current_price=current_price,
                    dte=long_put["dte"],
                    direction="bearish",
                ))

    return results


def _find_call_spreads(
    ticker: str,
    chain: Dict,
    current_price: float,
    max_budget: float,
    thesis_id: str,
    thesis_name: str,
) -> List[ScanResult]:
    """Find call debit spreads (bullish plays) within budget."""
    results = []
    calls = chain.get("calls", [])

    if not calls:
        return results

    by_expiry = {}
    for call in calls:
        exp = call["expiration"]
        if exp not in by_expiry:
            by_expiry[exp] = []
        by_expiry[exp].append(call)

    for expiry, expiry_calls in by_expiry.items():
        expiry_calls.sort(key=lambda c: c["strike"])

        for i, long_call in enumerate(expiry_calls):
            if not _passes_liquidity_filter(long_call):
                continue

            for width in SPREAD_WIDTHS:
                short_strike = long_call["strike"] + width
                short_call = _find_option_at_strike(expiry_calls, short_strike)
                if not short_call or not _passes_liquidity_filter(short_call):
                    continue

                net_debit_per_share = long_call["mid"] - short_call["mid"]
                if net_debit_per_share <= 0:
                    continue

                net_debit_total = net_debit_per_share * 100

                if net_debit_total > max_budget:
                    continue

                metrics = call_debit_spread_metrics(
                    long_call["strike"], short_call["strike"], net_debit_per_share
                )

                if metrics["risk_reward"] < 0.5:
                    continue

                results.append(ScanResult(
                    thesis_id=thesis_id,
                    thesis_name=thesis_name,
                    ticker=ticker,
                    spread_type="call_debit_spread",
                    long_strike=long_call["strike"],
                    short_strike=short_call["strike"],
                    expiration=expiry,
                    net_debit=net_debit_total,
                    max_profit=metrics["max_profit"],
                    breakeven=metrics["breakeven"],
                    risk_reward=metrics["risk_reward"],
                    current_price=current_price,
                    dte=long_call["dte"],
                    direction="bullish",
                ))

    return results


def _passes_liquidity_filter(option: dict) -> bool:
    """Check if an option meets minimum liquidity requirements."""
    if option.get("volume", 0) < MIN_VOLUME:
        return False
    if option.get("open_interest", 0) < MIN_OPEN_INTEREST:
        return False
    if option.get("mid", 0) > 0:
        bid_ask_spread = option.get("ask", 0) - option.get("bid", 0)
        if bid_ask_spread / option["mid"] > MAX_BID_ASK_SPREAD_PCT:
            return False
    return True


def _find_option_at_strike(options: list, target_strike: float) -> Optional[dict]:
    """Find an option at a specific strike price (with tolerance)."""
    for opt in options:
        if abs(opt["strike"] - target_strike) < 0.01:
            return opt
    return None


def format_scan_results(results: Dict[str, List[ScanResult]]) -> str:
    """Format scan results as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("STRATEGY SCANNER RESULTS")
    lines.append(f"Scan time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Total budget: ${TOTAL_CAPITAL:.2f}")
    lines.append("=" * 60)

    for thesis_id, scan_results in results.items():
        thesis = THESES[thesis_id]
        budget = TOTAL_CAPITAL * thesis["allocation_pct"]
        lines.append(f"\n--- {thesis['name']} (Budget: ${budget:.2f}) ---")

        if not scan_results:
            lines.append("  No trades found within budget/liquidity constraints.")
            continue

        for i, r in enumerate(scan_results[:3]):  # Top 3 per thesis
            lines.append(f"\n  #{i+1} {r.ticker} {r.spread_type.replace('_', ' ').title()}")
            lines.append(f"      Strikes: {r.long_strike}/{r.short_strike}")
            lines.append(f"      Expiry: {r.expiration} ({r.dte} DTE)")
            lines.append(f"      Cost: ${r.net_debit:.2f} | Max Profit: ${r.max_profit:.2f}")
            lines.append(f"      Breakeven: ${r.breakeven:.2f} | Risk/Reward: {r.risk_reward:.1f}x")
            lines.append(f"      Current price: ${r.current_price:.2f}")

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
