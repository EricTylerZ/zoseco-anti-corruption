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
    AGGRESSIVE_MIN_DTE,
    AGGRESSIVE_MAX_DTE,
    AGGRESSIVE_SPREAD_WIDTHS,
    AGGRESSIVE_MIN_VOLUME,
    AGGRESSIVE_MIN_OPEN_INTEREST,
    AGGRESSIVE_MAX_BID_ASK_SPREAD_PCT,
)
from core.models import ScanResult
from core.options_math import put_debit_spread_metrics, call_debit_spread_metrics
from data.market_data import get_options_chain, get_price

# Module-level mode settings (switched by aggressive flag)
_scan_settings = {
    "min_dte": MIN_DTE,
    "max_dte": MAX_DTE,
    "spread_widths": SPREAD_WIDTHS,
    "min_volume": MIN_VOLUME,
    "min_oi": MIN_OPEN_INTEREST,
    "max_bid_ask": MAX_BID_ASK_SPREAD_PCT,
    "min_rr": 0.5,
}

_aggressive_settings = {
    "min_dte": AGGRESSIVE_MIN_DTE,
    "max_dte": AGGRESSIVE_MAX_DTE,
    "spread_widths": AGGRESSIVE_SPREAD_WIDTHS,
    "min_volume": AGGRESSIVE_MIN_VOLUME,
    "min_oi": AGGRESSIVE_MIN_OPEN_INTEREST,
    "max_bid_ask": AGGRESSIVE_MAX_BID_ASK_SPREAD_PCT,
    "min_rr": 0.3,  # accept lower R/R for leverage
}


def scan_all(
    budget: float = TOTAL_CAPITAL,
    redis_client=None,
    aggressive: bool = False,
    allocation_override: Dict[str, float] = None,
) -> Dict[str, List[ScanResult]]:
    """
    Scan all theses for trade opportunities.

    Args:
        budget: Total capital to allocate
        redis_client: Optional Redis client
        aggressive: Use aggressive (weekly) settings
        allocation_override: Dynamic allocation from momentum engine

    Returns dict keyed by thesis_id with list of ScanResult recommendations.
    """
    results = {}
    for thesis_id, thesis in THESES.items():
        alloc_pct = (
            allocation_override.get(thesis_id, thesis["allocation_pct"])
            if allocation_override
            else thesis["allocation_pct"]
        )
        thesis_budget = budget * alloc_pct
        results[thesis_id] = scan_thesis(
            thesis_id, thesis_budget, redis_client, aggressive=aggressive
        )
    return results


def scan_thesis(
    thesis_id: str,
    budget: float = None,
    redis_client=None,
    aggressive: bool = False,
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

    settings = _aggressive_settings if aggressive else _scan_settings
    all_results = []

    for ticker, ticker_info in thesis["tickers"].items():
        ticker_budget = budget * ticker_info["weight"]
        direction = ticker_info["direction"]

        chain = get_options_chain(
            ticker, settings["min_dte"], settings["max_dte"], redis_client
        )
        if not chain.get("current_price"):
            continue

        current_price = chain["current_price"]

        if direction == "bearish":
            spreads = _find_put_spreads(
                ticker, chain, current_price, ticker_budget,
                thesis_id, thesis["name"], settings
            )
        else:  # bullish
            spreads = _find_call_spreads(
                ticker, chain, current_price, ticker_budget,
                thesis_id, thesis["name"], settings
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
    settings: Dict = None,
) -> List[ScanResult]:
    """Find put debit spreads (bearish plays) within budget."""
    if settings is None:
        settings = _scan_settings
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
            if not _passes_liquidity_filter(long_put, settings):
                continue

            for width in settings["spread_widths"]:
                short_strike = long_put["strike"] - width
                # Find matching short put
                short_put = _find_option_at_strike(expiry_puts, short_strike)
                if not short_put or not _passes_liquidity_filter(short_put, settings):
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

                if metrics["risk_reward"] < settings["min_rr"]:
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
    settings: Dict = None,
) -> List[ScanResult]:
    """Find call debit spreads (bullish plays) within budget."""
    if settings is None:
        settings = _scan_settings
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
            if not _passes_liquidity_filter(long_call, settings):
                continue

            for width in settings["spread_widths"]:
                short_strike = long_call["strike"] + width
                short_call = _find_option_at_strike(expiry_calls, short_strike)
                if not short_call or not _passes_liquidity_filter(short_call, settings):
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

                if metrics["risk_reward"] < settings["min_rr"]:
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


def _passes_liquidity_filter(option: dict, settings: Dict = None) -> bool:
    """Check if an option meets minimum liquidity requirements."""
    if settings is None:
        settings = _scan_settings
    if option.get("volume", 0) < settings["min_volume"]:
        return False
    if option.get("open_interest", 0) < settings["min_oi"]:
        return False
    if option.get("mid", 0) > 0:
        bid_ask_spread = option.get("ask", 0) - option.get("bid", 0)
        if bid_ask_spread / option["mid"] > settings["max_bid_ask"]:
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
