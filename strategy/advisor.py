"""
12 Options Strategy Advisor Tools.

Interactive analysis tools for options trading decisions:
  1. IV Environment Scanner
  2. Cash-Secured Put Strike Finder
  3. 30 DTE Theta Decay Optimizer
  4. Covered Call Timing Setup
  5. Wheel Cycle Tracker
  6. LEAP Entry Checklist
  7. Position Sizing Stress Test
  8. Earnings Risk Screener
  9. Strategy Decision Framework
  10. LEAP Tax Timer
  11. Portfolio Correlation Audit
  12. Pre-Trade Exit Plan
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from core.options_math import estimate_delta, estimate_theta, norm_cdf
from data.market_data import get_price, get_options_chain, get_price_history


# ── Sector mapping for correlation and comparison ──────────────────────

SECTOR_MAP = {
    # Technology
    "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
    "GOOG": "Technology", "META": "Technology", "AMZN": "Technology",
    "NVDA": "Technology", "AMD": "Technology", "INTC": "Technology",
    "TSM": "Technology", "CRM": "Technology", "ORCL": "Technology",
    # Consumer Staples / Food
    "TSN": "Consumer Staples", "PPC": "Consumer Staples",
    "BRFS": "Consumer Staples", "CALM": "Consumer Staples",
    "KO": "Consumer Staples", "PEP": "Consumer Staples",
    # Agriculture / Commodities ETFs
    "DBA": "Agriculture", "COW": "Agriculture", "MOO": "Agriculture",
    # Precious Metals
    "GLD": "Precious Metals", "SLV": "Precious Metals",
    "GDX": "Precious Metals", "GDXJ": "Precious Metals",
    "SILJ": "Precious Metals",
    # Dollar / Currencies
    "UUP": "Currency", "UDN": "Currency",
    # Bonds
    "TLT": "Bonds", "TBT": "Bonds",
    # Financials
    "XLF": "Financials", "KRE": "Financials",
    "JPM": "Financials", "BAC": "Financials", "GS": "Financials",
    # Volatility
    "UVXY": "Volatility", "VXX": "Volatility", "VIX": "Volatility",
    # Crypto
    "BITO": "Crypto", "COIN": "Crypto",
    # Real Estate
    "VNO": "Real Estate", "SLG": "Real Estate", "BXP": "Real Estate",
    "PGRE": "Real Estate", "IYR": "Real Estate", "XLRE": "Real Estate",
    "REM": "Real Estate", "XHB": "Real Estate", "DBRG": "Real Estate",
    "NYC": "Real Estate", "ABR": "Real Estate",
    # Energy
    "XLE": "Energy", "XOM": "Energy", "CVX": "Energy",
    # Healthcare
    "XLV": "Healthcare", "JNJ": "Healthcare", "PFE": "Healthcare",
    # Industrials
    "XLI": "Industrials", "CAT": "Industrials", "BA": "Industrials",
    # Broad Market
    "SPY": "Broad Market", "QQQ": "Broad Market", "IWM": "Broad Market",
    "DIA": "Broad Market",
}

# Correlation groups: tickers that move together in stress
CORRELATION_GROUPS = {
    "Risk-On Equities": ["AAPL", "MSFT", "GOOGL", "META", "AMZN", "NVDA", "AMD", "QQQ", "SPY"],
    "Precious Metals": ["GLD", "SLV", "GDX", "GDXJ", "SILJ"],
    "Real Estate / REITs": ["VNO", "SLG", "BXP", "PGRE", "IYR", "XLRE", "REM", "XHB", "DBRG", "NYC", "ABR"],
    "Financials": ["XLF", "KRE", "JPM", "BAC", "GS"],
    "Dollar-Linked": ["UUP", "UDN", "TLT", "TBT"],
    "Volatility": ["UVXY", "VXX"],
    "Food / Agriculture": ["TSN", "PPC", "BRFS", "DBA", "COW", "MOO", "CALM"],
}

# Sector average IV (rough benchmarks for comparison)
SECTOR_IV_BENCHMARKS = {
    "Technology": 0.35, "Consumer Staples": 0.25, "Agriculture": 0.22,
    "Precious Metals": 0.30, "Currency": 0.12, "Bonds": 0.15,
    "Financials": 0.25, "Volatility": 0.90, "Crypto": 0.65,
    "Real Estate": 0.30, "Energy": 0.30, "Healthcare": 0.25,
    "Industrials": 0.25, "Broad Market": 0.18,
}


# ── Shared Helpers ─────────────────────────────────────────────────────

def _calculate_rsi(history: List[Dict], period: int = 14) -> Optional[float]:
    """Calculate RSI from price history close prices."""
    closes = [d["close"] for d in history if d.get("close") is not None]
    if len(closes) < period + 1:
        return None

    gains = []
    losses = []
    for i in range(1, len(closes)):
        change = closes[i] - closes[i - 1]
        gains.append(max(change, 0))
        losses.append(max(-change, 0))

    if len(gains) < period:
        return None

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothing for remaining periods
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def _calculate_iv_rank(options_chain: Dict) -> Dict:
    """
    Calculate IV rank and percentile from options chain data.

    Uses implied_volatility from all options in the chain.
    """
    all_ivs = []
    for opt in options_chain.get("puts", []) + options_chain.get("calls", []):
        iv = opt.get("implied_volatility", 0)
        if iv and iv > 0.01:  # filter out near-zero
            all_ivs.append(iv)

    if not all_ivs:
        return {
            "iv_mean": 0, "iv_high": 0, "iv_low": 0,
            "iv_rank": 0, "iv_percentile": 0,
            "environment": "unknown",
        }

    iv_mean = sum(all_ivs) / len(all_ivs)
    iv_high = max(all_ivs)
    iv_low = min(all_ivs)
    iv_range = iv_high - iv_low

    # IV Rank: where current mean sits in the range
    iv_rank = ((iv_mean - iv_low) / iv_range * 100) if iv_range > 0 else 50.0

    # IV Percentile: % of observations below the mean
    below = sum(1 for iv in all_ivs if iv < iv_mean)
    iv_percentile = (below / len(all_ivs)) * 100

    # Environment classification
    if iv_rank > 66:
        environment = "HIGH"
    elif iv_rank > 33:
        environment = "AVERAGE"
    else:
        environment = "LOW"

    return {
        "iv_mean": round(iv_mean, 4),
        "iv_high": round(iv_high, 4),
        "iv_low": round(iv_low, 4),
        "iv_rank": round(iv_rank, 1),
        "iv_percentile": round(iv_percentile, 1),
        "environment": environment,
        "sample_size": len(all_ivs),
    }


def _find_support_resistance(history: List[Dict]) -> Dict:
    """Find support and resistance levels from price history using swing highs/lows."""
    if not history or len(history) < 5:
        return {"supports": [], "resistances": []}

    highs = [d["high"] for d in history if d.get("high") is not None]
    lows = [d["low"] for d in history if d.get("low") is not None]
    closes = [d["close"] for d in history if d.get("close") is not None]

    if len(highs) < 5:
        return {"supports": [], "resistances": []}

    # Find swing lows (support) and swing highs (resistance)
    supports = []
    resistances = []

    for i in range(2, len(lows) - 2):
        # Swing low: lower than 2 neighbors on each side
        if lows[i] <= min(lows[i-2], lows[i-1], lows[i+1], lows[i+2]):
            supports.append(round(lows[i], 2))
        # Swing high: higher than 2 neighbors on each side
        if highs[i] >= max(highs[i-2], highs[i-1], highs[i+1], highs[i+2]):
            resistances.append(round(highs[i], 2))

    # Deduplicate nearby levels (within 1%)
    supports = _dedupe_levels(sorted(supports))
    resistances = _dedupe_levels(sorted(resistances, reverse=True))

    return {"supports": supports[:5], "resistances": resistances[:5]}


def _dedupe_levels(levels: List[float], threshold: float = 0.01) -> List[float]:
    """Remove price levels that are within threshold % of each other."""
    if not levels:
        return []
    result = [levels[0]]
    for level in levels[1:]:
        if abs(level - result[-1]) / result[-1] > threshold:
            result.append(level)
    return result


def _find_strike_at_delta(
    chain: Dict, target_delta: float, option_type: str,
    stock_price: float, r: float = 0.05, min_dte: int = 25,
) -> Optional[Dict]:
    """Find the option closest to target delta."""
    options = chain.get("puts" if option_type == "put" else "calls", [])
    if not options:
        return None

    best = None
    best_diff = float("inf")

    for opt in options:
        if opt.get("dte", 0) < min_dte:
            continue
        iv = opt.get("implied_volatility", 0.30)
        if iv <= 0:
            iv = 0.30
        T = opt["dte"] / 365.0
        delta = abs(estimate_delta(stock_price, opt["strike"], T, r, iv, option_type))
        diff = abs(delta - target_delta)
        if diff < best_diff:
            best_diff = diff
            best = {**opt, "delta": round(delta, 3)}

    return best


def _get_sector(ticker: str) -> str:
    """Get sector for a ticker."""
    return SECTOR_MAP.get(ticker.upper(), "Unknown")


# ── Tool 1: IV Environment Scanner ────────────────────────────────────

def iv_environment(ticker: str, redis_client=None) -> str:
    """
    Analyze the IV environment for a ticker.

    Determines if IV is high, low, or average and recommends
    selling premium vs buying options.
    """
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    chain = get_options_chain(ticker, 20, 90, redis_client)
    iv_data = _calculate_iv_rank(chain)

    sector = _get_sector(ticker)
    sector_avg = SECTOR_IV_BENCHMARKS.get(sector, 0.25)
    iv_vs_sector = "ABOVE" if iv_data["iv_mean"] > sector_avg else "BELOW"

    lines = []
    lines.append("=" * 60)
    lines.append(f"IV ENVIRONMENT SCANNER: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Sector: {sector}")
    lines.append("")
    lines.append("IV Metrics:")
    lines.append(f"  Current IV (mean):   {iv_data['iv_mean']*100:.1f}%")
    lines.append(f"  IV High (chain):     {iv_data['iv_high']*100:.1f}%")
    lines.append(f"  IV Low (chain):      {iv_data['iv_low']*100:.1f}%")
    lines.append(f"  IV Rank:             {iv_data['iv_rank']:.1f}%")
    lines.append(f"  IV Percentile:       {iv_data['iv_percentile']:.1f}%")
    lines.append(f"  Environment:         {iv_data['environment']}")
    lines.append(f"  Sample Size:         {iv_data.get('sample_size', 0)} contracts")
    lines.append("")
    lines.append(f"Sector Comparison ({sector}):")
    lines.append(f"  Sector Average IV:   {sector_avg*100:.1f}%")
    lines.append(f"  {ticker} vs Sector:  {iv_vs_sector} average")
    lines.append("")

    # Strategy recommendation
    lines.append("RECOMMENDATION:")
    if iv_data["environment"] == "HIGH":
        lines.append("  IV is HIGH - premiums are FAT.")
        lines.append("  -> SELL PREMIUM: Cash-secured puts, covered calls, credit spreads")
        lines.append("  -> Avoid buying options (you're paying inflated prices)")
        lines.append("  -> Consider iron condors if you expect mean reversion")
    elif iv_data["environment"] == "LOW":
        lines.append("  IV is LOW - options are CHEAP.")
        lines.append("  -> BUY OPTIONS: LEAPs, debit spreads, long calls/puts")
        lines.append("  -> Avoid selling premium (not enough juice)")
        lines.append("  -> Great time to establish long-dated directional bets")
    else:
        lines.append("  IV is AVERAGE - no strong edge either way.")
        lines.append("  -> Either strategy can work; lean on your directional conviction")
        lines.append("  -> If unsure, WAIT for IV to reach an extreme")
    lines.append("")

    if iv_data["environment"] == "unknown":
        lines.append("WARNING: Could not calculate IV metrics. Chain data may be thin.")
        lines.append("Consider waiting for better data before acting.")

    return "\n".join(lines)


# ── Tool 2: Cash-Secured Put Strike Finder ─────────────────────────────

def csp_strike_finder(ticker: str, redis_client=None) -> str:
    """Find the optimal strike for a cash-secured put."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    chain = get_options_chain(ticker, 25, 60, redis_client)
    history = get_price_history(ticker, 90, redis_client)

    # Find support levels
    sr = _find_support_resistance(history) if history else {"supports": [], "resistances": []}

    # Find put at ~0.20 delta
    target_put = _find_strike_at_delta(chain, 0.20, "put", price)

    lines = []
    lines.append("=" * 60)
    lines.append(f"CASH-SECURED PUT STRIKE FINDER: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Current Price: ${price:.2f}")
    lines.append("")

    # Support levels
    lines.append("Support Levels (90-day):")
    if sr["supports"]:
        for i, s in enumerate(sr["supports"][:3], 1):
            pct = (s - price) / price * 100
            lines.append(f"  S{i}: ${s:.2f} ({pct:+.1f}% from current)")
    else:
        lines.append("  No clear support levels found in recent history.")
    lines.append("")

    if not target_put:
        lines.append("No suitable puts found at ~0.20 delta in the 25-60 DTE range.")
        lines.append("The options chain may be thin. Consider waiting or trying a different DTE range.")
        return "\n".join(lines)

    # Strike analysis
    premium = target_put.get("mid", target_put.get("last", 0))
    effective_basis = target_put["strike"] - premium
    assignment_cost = target_put["strike"] * 100  # cost for 100 shares

    lines.append("Recommended Strike:")
    lines.append(f"  Strike:          ${target_put['strike']:.2f}")
    lines.append(f"  Delta:           {target_put.get('delta', 0):.3f}")
    lines.append(f"  DTE:             {target_put['dte']} days")
    lines.append(f"  Expiration:      {target_put['expiration']}")
    lines.append(f"  Premium (mid):   ${premium:.2f} per share (${premium*100:.2f} per contract)")
    lines.append(f"  Bid/Ask:         ${target_put['bid']:.2f} / ${target_put['ask']:.2f}")
    lines.append(f"  IV:              {target_put.get('implied_volatility', 0)*100:.1f}%")
    lines.append("")

    lines.append("If Assigned:")
    lines.append(f"  Cost Basis:      ${effective_basis:.2f} per share")
    lines.append(f"  Cash Required:   ${assignment_cost:.2f} (100 shares)")
    lines.append(f"  Discount:        {(1 - effective_basis/price)*100:.1f}% below current price")
    lines.append("")

    # Check if strike is at/below support
    at_support = False
    for s in sr["supports"]:
        if target_put["strike"] <= s * 1.02:  # within 2% of support
            at_support = True
            break

    lines.append("Assessment:")
    if at_support:
        lines.append("  STRIKE IS AT/BELOW SUPPORT - good defensive level")
    else:
        lines.append("  Strike is above nearest support - consider a lower strike for safety")

    # Premium worth it?
    annualized_return = (premium / target_put["strike"]) * (365 / target_put["dte"]) * 100
    lines.append(f"  Annualized Return on Cash: {annualized_return:.1f}%")

    if annualized_return < 8:
        lines.append("")
        lines.append("  WARNING: Premium is thin (<8% annualized).")
        lines.append("  SKIP THIS TRADE - the risk/reward doesn't justify tying up capital.")
    else:
        lines.append("")
        lines.append(f"  Would you want to own 100 shares of {ticker} at ${effective_basis:.2f}")
        lines.append(f"  for the next 2-3 years? If yes, this is a solid entry point.")

    return "\n".join(lines)


# ── Tool 3: 30 DTE Theta Decay Optimizer ───────────────────────────────

def theta_decay_optimizer(
    ticker: str, option_type: str, premium: float, dte: int = 30,
    redis_client=None,
) -> str:
    """Map theta decay and show why closing at 50% beats holding to expiration."""
    price = get_price(ticker, redis_client)

    lines = []
    lines.append("=" * 60)
    lines.append(f"THETA DECAY OPTIMIZER: {ticker}")
    lines.append("=" * 60)
    if price:
        lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Option Type: {option_type.upper()}")
    lines.append(f"Premium Collected: ${premium:.2f} per share (${premium*100:.2f} per contract)")
    lines.append(f"Days to Expiration: {dte}")
    lines.append("")

    # 50% profit target
    target_50 = premium * 0.50
    buyback_price = premium - target_50
    lines.append(f"50% Profit Target:")
    lines.append(f"  Buy back at: ${buyback_price:.2f} per share")
    lines.append(f"  Profit: ${target_50:.2f} per share (${target_50*100:.2f} per contract)")
    lines.append("")

    # Theta decay schedule (accelerates as expiration approaches)
    # Theta decays proportional to 1/sqrt(T), so most decay is in final days
    lines.append("Theta Decay Schedule:")
    lines.append(f"  {'Day':>4} | {'DTE':>4} | {'% Decayed':>10} | {'Remaining Value':>15}")
    lines.append(f"  {'-'*4}-+-{'-'*4}-+-{'-'*10}-+-{'-'*15}")

    milestones = [0, 5, 7, 10, 14, 21, 25, dte]
    milestones = sorted(set(d for d in milestones if d <= dte))

    for day in milestones:
        remaining_dte = dte - day
        if remaining_dte <= 0:
            pct_decayed = 100.0
        else:
            # Theta decay approximation: value ~ sqrt(remaining_dte / original_dte)
            pct_remaining = math.sqrt(remaining_dte / dte)
            pct_decayed = (1 - pct_remaining) * 100
        remaining_val = premium * (1 - pct_decayed / 100)
        lines.append(f"  {day:>4} | {remaining_dte:>4} | {pct_decayed:>9.1f}% | ${remaining_val:>13.2f}")

    lines.append("")

    # Estimate days to 50% profit
    # 50% decayed when sqrt(remaining/dte) = 0.50 → remaining = 0.25*dte
    days_to_50 = dte - (0.25 * dte)  # = 0.75 * dte
    days_to_50 = round(days_to_50)
    lines.append(f"Estimated Days to 50% Profit: ~{days_to_50} days")
    lines.append(f"  (Assumes stock stays flat and theta decay follows sqrt curve)")
    lines.append("")

    # Annualized return comparison
    # Close at 50% early
    if days_to_50 > 0:
        annual_early = (target_50 / premium) * (365 / days_to_50) * 100
    else:
        annual_early = 0

    # Hold to expiration
    annual_full = (premium / premium) * (365 / dte) * 100 if dte > 0 else 0

    lines.append("Annualized Return Comparison:")
    lines.append(f"  Close at 50% in ~{days_to_50} days: {annual_early:.1f}% annualized")
    lines.append(f"  Hold to full expiration ({dte} days): {annual_full:.1f}% annualized")
    lines.append("")

    if annual_early > annual_full:
        edge = annual_early - annual_full
        lines.append(f"  CLOSING EARLY WINS by {edge:.1f}% annualized")
        lines.append(f"  Why? You capture 50% of the profit in {days_to_50}/{dte} of the time.")
        lines.append(f"  The last 50% of premium takes the LONGEST to decay.")
        lines.append(f"  Close early → redeploy capital → compound faster.")
    else:
        lines.append(f"  Holding to expiration is competitive here.")
    lines.append("")

    # Roll trigger
    roll_trigger_dte = max(7, dte // 4)
    lines.append(f"Roll Trigger:")
    lines.append(f"  If NOT at 50% profit by {dte - roll_trigger_dte} days ({roll_trigger_dte} DTE remaining):")
    lines.append(f"  -> Consider rolling to next month for fresh premium")
    lines.append(f"  -> Especially if the stock has moved against you")
    lines.append(f"  If at a LOSS at {roll_trigger_dte} DTE: ROLL, don't wait and hope")

    return "\n".join(lines)


# ── Tool 4: Covered Call Timing Setup ──────────────────────────────────

def covered_call_timing(ticker: str, cost_basis: float, redis_client=None) -> str:
    """Determine if now is the right time to sell a covered call."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    history = get_price_history(ticker, 90, redis_client)
    chain = get_options_chain(ticker, 25, 45, redis_client)

    # RSI
    rsi = _calculate_rsi(history) if history else None

    # Support/Resistance
    sr = _find_support_resistance(history) if history else {"supports": [], "resistances": []}

    # Find call at ~0.20 delta above cost basis
    target_call = _find_strike_at_delta(chain, 0.20, "call", price)

    lines = []
    lines.append("=" * 60)
    lines.append(f"COVERED CALL TIMING: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Current Price:  ${price:.2f}")
    lines.append(f"Cost Basis:     ${cost_basis:.2f}")
    unrealized = (price - cost_basis)
    unrealized_pct = unrealized / cost_basis * 100 if cost_basis > 0 else 0
    lines.append(f"Unrealized P&L: ${unrealized:.2f} ({unrealized_pct:+.1f}%)")
    lines.append("")

    # RSI Check
    lines.append("RSI Analysis:")
    if rsi is not None:
        lines.append(f"  14-Day RSI: {rsi:.1f}")
        if rsi > 70:
            lines.append(f"  OVERBOUGHT - Good time to sell a call (stock likely to cool off)")
            rsi_signal = "sell"
        elif rsi > 60:
            lines.append(f"  Elevated - Acceptable timing for a call")
            rsi_signal = "neutral"
        elif rsi < 30:
            lines.append(f"  OVERSOLD - WAIT. Stock may bounce; don't cap upside now")
            rsi_signal = "wait"
        else:
            lines.append(f"  Neutral range - No strong timing signal from RSI")
            rsi_signal = "neutral"
    else:
        lines.append("  Could not calculate RSI (insufficient history)")
        rsi_signal = "neutral"
    lines.append("")

    # Resistance levels
    lines.append("Resistance Levels:")
    if sr["resistances"]:
        for i, r in enumerate(sr["resistances"][:3], 1):
            pct = (r - price) / price * 100
            lines.append(f"  R{i}: ${r:.2f} ({pct:+.1f}% from current)")
    else:
        lines.append("  No clear resistance levels found.")
    lines.append("")

    # Strike recommendation
    if target_call:
        premium = target_call.get("mid", target_call.get("last", 0))
        called_away_profit = (target_call["strike"] - cost_basis) + premium
        called_away_pct = called_away_profit / cost_basis * 100 if cost_basis > 0 else 0

        lines.append("Recommended Strike:")
        lines.append(f"  Strike:          ${target_call['strike']:.2f}")
        lines.append(f"  Delta:           {target_call.get('delta', 0):.3f}")
        lines.append(f"  DTE:             {target_call['dte']} days")
        lines.append(f"  Premium (mid):   ${premium:.2f}/share (${premium*100:.2f}/contract)")
        lines.append(f"  IV:              {target_call.get('implied_volatility', 0)*100:.1f}%")
        lines.append("")

        if target_call["strike"] > cost_basis:
            lines.append("If Called Away:")
            lines.append(f"  Capital Gain:    ${target_call['strike'] - cost_basis:.2f}/share")
            lines.append(f"  + Premium:       ${premium:.2f}/share")
            lines.append(f"  Total Profit:    ${called_away_profit:.2f}/share ({called_away_pct:.1f}%)")
            lines.append("")
            lines.append(f"  Happy with {called_away_pct:.1f}% total return? If yes, sell the call.")
        else:
            lines.append(f"  WARNING: Strike ${target_call['strike']:.2f} is BELOW cost basis ${cost_basis:.2f}")
            lines.append(f"  You'd lock in a loss if assigned. Consider a higher strike or WAIT.")
    else:
        lines.append("No suitable calls found near 0.20 delta in 25-45 DTE range.")
    lines.append("")

    # Overall verdict
    lines.append("VERDICT:")
    if rsi_signal == "wait":
        lines.append("  WAIT - Stock is oversold. Don't sell a call into potential upside.")
    elif rsi_signal == "sell" and target_call and target_call["strike"] > cost_basis:
        lines.append("  SELL THE CALL - RSI is overbought, strike is above cost basis.")
    elif target_call and target_call["strike"] <= cost_basis:
        lines.append("  WAIT - Can't find a strike above cost basis with decent premium.")
    else:
        lines.append("  NEUTRAL - Conditions are acceptable but not ideal.")
        lines.append("  If you want income and can accept being called away, go ahead.")
        lines.append("  If the stock is trending strongly, consider waiting.")

    return "\n".join(lines)


# ── Tool 5: Wheel Cycle Tracker ────────────────────────────────────────

def wheel_tracker(ticker: str, cycles: List[Dict], redis_client=None) -> str:
    """
    Track full wheel cycle P&L.

    cycles: list of {type: "csp"|"cc", strike: float, premium: float, assigned: bool}
    """
    price = get_price(ticker, redis_client)

    lines = []
    lines.append("=" * 60)
    lines.append(f"WHEEL CYCLE TRACKER: {ticker}")
    lines.append("=" * 60)
    if price:
        lines.append(f"Current Price: ${price:.2f}")
    lines.append("")

    total_premium = 0.0
    csp_count = 0
    cc_count = 0
    share_cost = 0.0  # cost basis if currently holding shares
    holding_shares = False
    total_cycles = 0

    lines.append("TRADE HISTORY:")
    lines.append(f"  {'#':>3} | {'Type':>4} | {'Strike':>8} | {'Premium':>8} | {'Assigned':>8} | {'Status'}")
    lines.append(f"  {'-'*3}-+-{'-'*4}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*20}")

    for i, cycle in enumerate(cycles, 1):
        ctype = cycle.get("type", "csp").upper()
        strike = cycle.get("strike", 0)
        premium = cycle.get("premium", 0)
        assigned = cycle.get("assigned", False)
        total_premium += premium

        if ctype == "CSP":
            csp_count += 1
            if assigned:
                share_cost = strike
                holding_shares = True
                status = f"Assigned @ ${strike:.2f}"
            else:
                status = "Expired/Closed"
                total_cycles += 1
        else:  # CC
            cc_count += 1
            if assigned:
                holding_shares = False
                status = f"Called away @ ${strike:.2f}"
                total_cycles += 1
            else:
                status = "Expired/Closed"

        lines.append(f"  {i:>3} | {ctype:>4} | ${strike:>7.2f} | ${premium:>7.2f} | {'YES' if assigned else 'NO':>8} | {status}")

    lines.append("")
    lines.append("SUMMARY:")
    lines.append(f"  Total CSPs Sold:       {csp_count}")
    lines.append(f"  Total CCs Sold:        {cc_count}")
    lines.append(f"  Complete Cycles:       {total_cycles}")
    lines.append(f"  Total Premium:         ${total_premium:.2f}/share (${total_premium*100:.2f}/contract)")
    lines.append("")

    if holding_shares:
        adjusted_basis = share_cost - total_premium
        lines.append(f"  Currently Holding:     100 shares")
        lines.append(f"  Original Assignment:   ${share_cost:.2f}")
        lines.append(f"  Adjusted Cost Basis:   ${adjusted_basis:.2f}")
        if price:
            unrealized = (price - adjusted_basis)
            lines.append(f"  Unrealized P&L:        ${unrealized:.2f}/share")
            lines.append(f"  Total Return:          ${unrealized + total_premium:.2f}/share")
    else:
        lines.append(f"  No shares held - ready for next CSP")
        lines.append(f"  Net Profit (all cycles): ${total_premium:.2f}/share (${total_premium*100:.2f}/contract)")

    # Annualized return estimate (rough, assumes ~30 days per trade)
    total_trades = csp_count + cc_count
    if total_trades > 0 and share_cost > 0:
        est_days = total_trades * 30
        annualized = (total_premium / share_cost) * (365 / est_days) * 100
        lines.append(f"  Est. Annualized Return: {annualized:.1f}% (assuming ~30d per trade)")

    lines.append("")
    lines.append("NEXT STEP:")
    if holding_shares:
        lines.append(f"  You're holding shares. Time to sell a covered call.")
        lines.append(f"  Use Advisor Tool #4 (Covered Call Timing) for strike selection.")
    else:
        lines.append(f"  No shares. Time to sell another cash-secured put.")
        lines.append(f"  Use Advisor Tool #2 (CSP Strike Finder) for strike selection.")

    return "\n".join(lines)


# ── Tool 6: LEAP Entry Checklist ───────────────────────────────────────

def leap_checklist(ticker: str, thesis: str, redis_client=None) -> str:
    """Run the LEAP entry conditions checklist."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    history = get_price_history(ticker, 180, redis_client)
    chain = get_options_chain(ticker, 300, 730, redis_client)
    iv_data = _calculate_iv_rank(chain)

    # RSI
    rsi_daily = _calculate_rsi(history) if history else None

    # Weekly RSI approximation (use every 5th day)
    rsi_weekly = None
    if history and len(history) >= 70:
        weekly_data = history[::5]  # sample every 5 trading days
        rsi_weekly = _calculate_rsi(weekly_data, period=14)

    # Support levels
    sr = _find_support_resistance(history) if history else {"supports": [], "resistances": []}

    lines = []
    lines.append("=" * 60)
    lines.append(f"LEAP ENTRY CHECKLIST: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Thesis: {thesis}")
    lines.append("")

    checks = []

    # Check 1: Conviction (can't measure, remind user)
    lines.append("1. CONVICTION CHECK:")
    lines.append(f"   Would you want MORE if {ticker} dropped 10% after buying?")
    lines.append(f"   That means buying at ${price * 0.90:.2f}. Your thesis: \"{thesis}\"")
    lines.append(f"   -> Only YOU can answer this. Be honest.")
    checks.append(None)  # user-evaluated
    lines.append("")

    # Check 2: RSI oversold
    lines.append("2. RSI OVERSOLD CHECK:")
    daily_pass = False
    weekly_pass = False
    if rsi_daily is not None:
        daily_pass = rsi_daily < 40
        status = "PASS" if daily_pass else "FAIL"
        lines.append(f"   Daily RSI:  {rsi_daily:.1f} {'(<40 = oversold zone)' if daily_pass else '(>40 = not oversold)'} [{status}]")
    else:
        lines.append("   Daily RSI:  Could not calculate")
    if rsi_weekly is not None:
        weekly_pass = rsi_weekly < 40
        status = "PASS" if weekly_pass else "FAIL"
        lines.append(f"   Weekly RSI: {rsi_weekly:.1f} {'(<40 = oversold zone)' if weekly_pass else '(>40 = not oversold)'} [{status}]")
    else:
        lines.append("   Weekly RSI: Could not calculate (need 6+ months history)")
    rsi_pass = daily_pass or weekly_pass
    checks.append(rsi_pass)
    lines.append("")

    # Check 3: Near support
    lines.append("3. PRICE NEAR SUPPORT:")
    near_support = False
    if sr["supports"]:
        nearest_support = min(sr["supports"], key=lambda s: abs(s - price))
        pct_from_support = (price - nearest_support) / price * 100
        near_support = pct_from_support < 5
        status = "PASS" if near_support else "FAIL"
        lines.append(f"   Nearest Support: ${nearest_support:.2f} ({pct_from_support:.1f}% above)")
        lines.append(f"   Within 5% of support: {status}")
    else:
        lines.append("   No support levels found in 180-day history")
    checks.append(near_support)
    lines.append("")

    # Check 4: IV low
    lines.append("4. IV ENVIRONMENT:")
    iv_low = iv_data["environment"] == "LOW"
    iv_avg = iv_data["environment"] == "AVERAGE"
    status = "PASS" if iv_low else ("BORDERLINE" if iv_avg else "FAIL")
    lines.append(f"   IV Rank: {iv_data['iv_rank']:.1f}%")
    lines.append(f"   Environment: {iv_data['environment']}")
    lines.append(f"   Low IV = cheap LEAPs: {status}")
    checks.append(iv_low or iv_avg)
    lines.append("")

    # Check 5: Optimal LEAP strike
    lines.append("5. OPTIMAL LEAP STRIKE:")
    # For LEAPs, look for 0.60-0.70 delta (slightly ITM for leverage + probability)
    leap_option = _find_strike_at_delta(chain, 0.65, "call", price, min_dte=300)
    if leap_option:
        lines.append(f"   Strike: ${leap_option['strike']:.2f} ({leap_option.get('delta', 0):.2f} delta)")
        lines.append(f"   DTE: {leap_option['dte']} days")
        lines.append(f"   Premium: ${leap_option.get('mid', 0):.2f}/share")
        lines.append(f"   IV: {leap_option.get('implied_volatility', 0)*100:.1f}%")
        lines.append(f"   Expiration: {leap_option['expiration']}")
        checks.append(True)
    else:
        lines.append("   No LEAP options found in 300-730 DTE range.")
        lines.append("   Chain may not have expirations that far out.")
        checks.append(False)
    lines.append("")

    # Verdict
    measurable_checks = [c for c in checks if c is not None]
    passing = sum(1 for c in measurable_checks if c)
    total = len(measurable_checks)

    lines.append("=" * 60)
    lines.append(f"VERDICT: {passing}/{total} conditions met")
    lines.append("=" * 60)
    if passing >= 3:
        lines.append("YES - Conditions are aligned for a LEAP entry.")
        lines.append("Confirm your conviction (check #1) and proceed.")
    elif passing >= 2:
        lines.append("BORDERLINE - Some conditions met, some not.")
        waiting_for = []
        if not checks[1]:
            waiting_for.append("RSI to reach oversold (<40)")
        if not checks[2]:
            waiting_for.append("price to pull back toward support")
        if not checks[3]:
            waiting_for.append("IV to drop (cheaper premiums)")
        if waiting_for:
            lines.append(f"Waiting for: {', '.join(waiting_for)}")
    else:
        lines.append("NO - Conditions are NOT aligned. WAIT.")
        lines.append("Don't buy expensive LEAPs in a bad environment.")

    return "\n".join(lines)


# ── Tool 7: Position Sizing Stress Test ────────────────────────────────

def position_size_stress(
    ticker: str, portfolio_value: float,
    existing_positions: Optional[List[Dict]] = None,
    redis_client=None,
) -> str:
    """Stress test a potential options position for proper sizing."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    if existing_positions is None:
        existing_positions = []

    sector = _get_sector(ticker)
    assignment_cost = price * 100  # 100 shares if assigned
    assignment_pct = (assignment_cost / portfolio_value) * 100

    lines = []
    lines.append("=" * 60)
    lines.append(f"POSITION SIZING STRESS TEST: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Portfolio Value: ${portfolio_value:,.2f}")
    lines.append(f"Sector: {sector}")
    lines.append("")

    # Scenario: 30% drop and assignment
    drop_price = price * 0.70
    drop_assignment = drop_price * 100
    loss_per_contract = (price - drop_price) * 100
    loss_pct = (loss_per_contract / portfolio_value) * 100

    lines.append("STRESS SCENARIO: 30% Stock Drop + Assignment")
    lines.append(f"  Stock drops to:    ${drop_price:.2f}")
    lines.append(f"  Assignment cost:   ${assignment_cost:,.2f} per contract (at current price)")
    lines.append(f"  Portfolio locked:  {assignment_pct:.1f}% of portfolio per contract")
    lines.append(f"  Loss per contract: ${loss_per_contract:,.2f}")
    lines.append(f"  Loss as % of portfolio: {loss_pct:.1f}%")
    lines.append("")

    # Sector overlap
    lines.append("SECTOR OVERLAP:")
    sector_exposure = 0.0
    overlapping = []
    for pos in existing_positions:
        pos_sector = _get_sector(pos.get("ticker", ""))
        if pos_sector == sector:
            sector_exposure += pos.get("allocation_pct", 0)
            overlapping.append(pos.get("ticker", "?"))

    if overlapping:
        lines.append(f"  Already exposed to {sector}: {', '.join(overlapping)}")
        lines.append(f"  Current sector allocation: {sector_exposure:.1f}%")
        new_total = sector_exposure + assignment_pct
        lines.append(f"  After adding {ticker}: {new_total:.1f}% in {sector}")
        if new_total > 30:
            lines.append(f"  WARNING: Over 30% in one sector. Concentration risk!")
    else:
        lines.append(f"  No existing {sector} exposure. Good diversification.")
    lines.append("")

    # Max contracts
    max_loss_pct = 5.0  # max 5% portfolio loss on total loss
    max_contracts_by_loss = int(portfolio_value * (max_loss_pct / 100) / assignment_cost)
    max_contracts_by_cash = int(portfolio_value * 0.20 / assignment_cost)  # keep 80% available
    max_contracts = max(1, min(max_contracts_by_loss, max_contracts_by_cash))

    lines.append("POSITION SIZING:")
    lines.append(f"  Max contracts (5% max loss rule):  {max_contracts_by_loss}")
    lines.append(f"  Max contracts (20% cash rule):     {max_contracts_by_cash}")
    lines.append(f"  Recommended max:                   {max_contracts}")
    lines.append(f"  Capital deployed:                  ${max_contracts * assignment_cost:,.2f}")
    lines.append(f"  Remaining available:               ${portfolio_value - max_contracts * assignment_cost:,.2f}")
    lines.append("")

    # Pushback
    lines.append("ASSESSMENT:")
    if assignment_pct > 25:
        lines.append(f"  A single contract puts {assignment_pct:.1f}% at risk.")
        lines.append(f"  This is a LARGE position relative to your portfolio.")
        lines.append(f"  Consider: Is {ticker} your highest-conviction idea?")
        lines.append(f"  If not, look for a cheaper underlying or use spreads.")
    elif assignment_pct > 10:
        lines.append(f"  Manageable at {assignment_pct:.1f}% per contract. Standard sizing.")
    else:
        lines.append(f"  Small relative to portfolio at {assignment_pct:.1f}%. Room for multiple contracts.")

    return "\n".join(lines)


# ── Tool 8: Earnings Risk Screener ─────────────────────────────────────

def earnings_risk_screen(
    ticker: str, earnings_date: str,
    position_info: Optional[Dict] = None,
    redis_client=None,
) -> str:
    """Screen earnings risk for an open options position."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    history = get_price_history(ticker, 365, redis_client)
    chain = get_options_chain(ticker, 5, 60, redis_client)
    iv_data = _calculate_iv_rank(chain)

    lines = []
    lines.append("=" * 60)
    lines.append(f"EARNINGS RISK SCREENER: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Earnings Date: {earnings_date}")
    lines.append("")

    # Expected move from IV
    # Expected move ≈ price * IV * sqrt(DTE/365)
    try:
        earnings_dt = datetime.strptime(earnings_date, "%Y-%m-%d")
        days_to_earnings = (earnings_dt - datetime.now()).days
    except ValueError:
        days_to_earnings = 7  # default

    if iv_data["iv_mean"] > 0:
        expected_move = price * iv_data["iv_mean"] * math.sqrt(max(1, days_to_earnings) / 365.0)
        expected_move_pct = expected_move / price * 100
    else:
        expected_move = price * 0.05  # default 5%
        expected_move_pct = 5.0

    lines.append("EXPECTED MOVE (market-implied):")
    lines.append(f"  Expected Move: +/- ${expected_move:.2f} ({expected_move_pct:.1f}%)")
    lines.append(f"  Expected Range: ${price - expected_move:.2f} - ${price + expected_move:.2f}")
    lines.append(f"  Current IV: {iv_data['iv_mean']*100:.1f}%")
    lines.append(f"  Days to Earnings: {days_to_earnings}")
    lines.append("")

    # Historical earnings moves (analyze quarterly gaps in price history)
    lines.append("HISTORICAL EARNINGS REACTIONS:")
    if history and len(history) > 60:
        # Look for large overnight gaps (proxy for earnings)
        gaps = []
        for i in range(1, len(history)):
            prev_close = history[i-1].get("close", 0)
            curr_open = history[i].get("open", 0)
            if prev_close and curr_open and prev_close > 0:
                gap_pct = (curr_open - prev_close) / prev_close * 100
                if abs(gap_pct) > 2:  # significant gap
                    gaps.append({
                        "date": history[i].get("date", "?"),
                        "gap_pct": round(gap_pct, 1),
                        "direction": "UP" if gap_pct > 0 else "DOWN",
                    })

        if gaps:
            recent_gaps = gaps[-4:]  # last 4 significant gaps
            for g in recent_gaps:
                lines.append(f"  {g['date']}: {g['direction']} {abs(g['gap_pct']):.1f}%")
            avg_gap = sum(abs(g["gap_pct"]) for g in recent_gaps) / len(recent_gaps)
            lines.append(f"  Average gap magnitude: {avg_gap:.1f}%")
        else:
            lines.append("  No significant gaps (>2%) found in the past year.")
    else:
        lines.append("  Insufficient history for gap analysis.")
    lines.append("")

    # Position analysis
    if position_info:
        strike = position_info.get("strike", 0)
        premium = position_info.get("premium", 0)
        strategy = position_info.get("strategy", "unknown")

        lines.append("YOUR POSITION:")
        lines.append(f"  Strategy: {strategy}")
        lines.append(f"  Strike: ${strike:.2f}")
        lines.append(f"  Premium: ${premium:.2f}")
        lines.append("")

        # Can a bad earnings gap the stock past the strike?
        if "put" in strategy.lower() or "csp" in strategy.lower():
            worst_case = price - expected_move
            cushion = strike - worst_case
            lines.append(f"  Worst-case stock price: ${worst_case:.2f}")
            if worst_case < strike:
                lines.append(f"  GAP RISK: Stock could gap below your ${strike:.2f} strike!")
                if premium > (strike - worst_case):
                    lines.append(f"  Premium cushion covers the gap (${premium:.2f} > ${strike - worst_case:.2f})")
                else:
                    lines.append(f"  Premium does NOT cover the gap! Risk: ${strike - worst_case - premium:.2f}/share loss")
            else:
                lines.append(f"  Strike is below worst-case price. You should be safe.")
        lines.append("")

    # Recommendation
    lines.append("RECOMMENDATION:")
    if days_to_earnings <= 2:
        lines.append("  CLOSE BEFORE EARNINGS - binary event too close.")
        lines.append("  You can re-enter after the dust settles.")
    elif expected_move_pct > 8:
        lines.append("  HIGH RISK - expected move is large (>8%).")
        lines.append("  Consider closing or rolling past earnings.")
    elif position_info and position_info.get("premium", 0) > expected_move:
        lines.append("  Premium cushion is larger than expected move.")
        lines.append("  Can HOLD through if conviction is high.")
    else:
        lines.append("  CLOSE or ROLL past earnings date.")
        lines.append("  Don't gamble on binary events.")
    lines.append("")
    lines.append("  Remember: You don't gamble on binary events.")
    lines.append("  If risk/reward doesn't work, CLOSE.")

    return "\n".join(lines)


# ── Tool 9: Strategy Decision Framework ────────────────────────────────

def strategy_decision(
    ticker: str, conviction: str, capital: float, redis_client=None,
) -> str:
    """Flowchart to pick the right options strategy."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    chain = get_options_chain(ticker, 20, 90, redis_client)
    iv_data = _calculate_iv_rank(chain)

    lines = []
    lines.append("=" * 60)
    lines.append(f"STRATEGY DECISION FRAMEWORK: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Stock Price: ${price:.2f}")
    lines.append(f"Conviction: {conviction.upper()}")
    lines.append(f"Available Capital: ${capital:,.2f}")
    lines.append(f"IV Environment: {iv_data['environment']} (rank: {iv_data['iv_rank']:.1f}%)")
    lines.append("")

    # Can afford 100 shares?
    can_afford_shares = capital >= price * 100
    assignment_pct = (price * 100 / capital * 100) if capital > 0 else 999

    lines.append("DECISION FLOWCHART:")
    lines.append("")

    # Step 1: IV Environment
    lines.append("Step 1: IV Environment")
    if iv_data["environment"] == "HIGH":
        lines.append(f"  IV is HIGH ({iv_data['iv_rank']:.0f}%) -> SELL premium")
        iv_direction = "sell"
    elif iv_data["environment"] == "LOW":
        lines.append(f"  IV is LOW ({iv_data['iv_rank']:.0f}%) -> BUY options")
        iv_direction = "buy"
    else:
        lines.append(f"  IV is AVERAGE ({iv_data['iv_rank']:.0f}%) -> Either direction works")
        iv_direction = "either"
    lines.append("")

    # Step 2: Conviction
    lines.append("Step 2: Conviction Level")
    conv = conviction.lower().replace("_", " ")
    if conv in ("very high", "very_high"):
        lines.append(f"  VERY HIGH conviction -> Larger position, directional bet")
        conv_level = 3
    elif conv == "high":
        lines.append(f"  HIGH conviction -> Standard position")
        conv_level = 2
    else:
        lines.append(f"  MODERATE conviction -> Smaller position, hedged")
        conv_level = 1
    lines.append("")

    # Step 3: Capital
    lines.append("Step 3: Capital Check")
    lines.append(f"  100 shares @ ${price:.2f} = ${price*100:,.2f}")
    lines.append(f"  Can afford shares: {'YES' if can_afford_shares else 'NO'}")
    lines.append(f"  Would use {assignment_pct:.1f}% of capital")
    lines.append("")

    # Decision
    lines.append("=" * 40)
    lines.append("RECOMMENDED STRATEGY:")
    lines.append("=" * 40)
    lines.append("")

    if iv_direction == "sell" and can_afford_shares and conv_level >= 2:
        lines.append("  -> SELL A CASH-SECURED PUT")
        lines.append(f"  IV is high = fat premiums. You can afford assignment.")
        lines.append(f"  Use Advisor #2 (CSP Strike Finder) to pick the strike.")
        if conv_level == 3:
            lines.append(f"  High conviction: consider selling at a higher strike for more premium.")

    elif iv_direction == "buy" and conv_level >= 2:
        lines.append("  -> BUY A LEAP (long-dated option)")
        lines.append(f"  IV is low = options are cheap. High conviction justifies the bet.")
        lines.append(f"  Use Advisor #6 (LEAP Checklist) to confirm entry conditions.")
        if can_afford_shares and conv_level == 3:
            lines.append(f"  Alternative: Buy shares directly + sell covered calls later.")

    elif iv_direction == "sell" and not can_afford_shares:
        lines.append("  -> SELL A PUT CREDIT SPREAD (defined risk)")
        lines.append(f"  IV is high but can't afford assignment.")
        lines.append(f"  A spread caps your risk to the width of the spread.")

    elif iv_direction == "either" and conv_level >= 2 and can_afford_shares:
        lines.append("  -> SELL A CASH-SECURED PUT (slight edge)")
        lines.append(f"  IV is average - no strong edge either way.")
        lines.append(f"  CSP gives you income while waiting for a better entry.")
        lines.append(f"  If assigned, you own at a discount. Win either way.")

    elif conv_level == 1:
        lines.append("  -> WAIT or use a small debit spread")
        lines.append(f"  Moderate conviction = don't overcommit.")
        lines.append(f"  If you must act, use a small defined-risk position.")

    else:
        lines.append("  -> WAIT for better conditions")
        lines.append(f"  Conditions don't clearly favor any strategy.")
        lines.append(f"  Watch for IV to reach an extreme or conviction to increase.")

    return "\n".join(lines)


# ── Tool 10: LEAP Tax Timer ───────────────────────────────────────────

def leap_tax_timer(
    ticker: str, open_date: str, unrealized_gain: float,
    tax_bracket: float, redis_client=None,
) -> str:
    """Analyze LEAP tax timing: short-term vs long-term cap gains."""
    price = get_price(ticker, redis_client)
    history = get_price_history(ticker, 90, redis_client)

    try:
        open_dt = datetime.strptime(open_date, "%Y-%m-%d")
    except ValueError:
        return f"ERROR: Invalid date format '{open_date}'. Use YYYY-MM-DD."

    one_year_mark = open_dt + timedelta(days=365)
    now = datetime.now()
    days_held = (now - open_dt).days
    days_to_ltcg = (one_year_mark - now).days

    # Tax rates
    short_term_rate = tax_bracket / 100
    long_term_rate = 0.15 if tax_bracket <= 37 else 0.20  # simplified LTCG rates
    if tax_bracket <= 12:
        long_term_rate = 0.0

    short_term_tax = unrealized_gain * short_term_rate
    long_term_tax = unrealized_gain * long_term_rate
    tax_savings = short_term_tax - long_term_tax

    lines = []
    lines.append("=" * 60)
    lines.append(f"LEAP TAX TIMER: {ticker}")
    lines.append("=" * 60)
    if price:
        lines.append(f"Current Price: ${price:.2f}")
    lines.append(f"Position Opened: {open_date}")
    lines.append(f"Days Held: {days_held}")
    lines.append(f"Unrealized Gain: ${unrealized_gain:,.2f}")
    lines.append(f"Tax Bracket: {tax_bracket}%")
    lines.append("")

    # Tax timeline
    lines.append("TAX TIMELINE:")
    if days_to_ltcg > 0:
        lines.append(f"  One-Year Mark: {one_year_mark.strftime('%Y-%m-%d')}")
        lines.append(f"  Days Until LTCG: {days_to_ltcg}")
        lines.append("")
        lines.append(f"  If sold TODAY (short-term):")
        lines.append(f"    Tax Rate: {tax_bracket}%")
        lines.append(f"    Tax Owed: ${short_term_tax:,.2f}")
        lines.append(f"    Net After Tax: ${unrealized_gain - short_term_tax:,.2f}")
        lines.append("")
        lines.append(f"  If sold AFTER {one_year_mark.strftime('%Y-%m-%d')} (long-term):")
        lines.append(f"    Tax Rate: {long_term_rate*100:.0f}%")
        lines.append(f"    Tax Owed: ${long_term_tax:,.2f}")
        lines.append(f"    Net After Tax: ${unrealized_gain - long_term_tax:,.2f}")
        lines.append("")
        lines.append(f"  TAX SAVINGS FROM WAITING: ${tax_savings:,.2f}")
    else:
        lines.append(f"  You've PASSED the one-year mark!")
        lines.append(f"  Any gains are already LONG-TERM capital gains ({long_term_rate*100:.0f}%).")
        lines.append(f"  Tax on current gain: ${long_term_tax:,.2f}")
    lines.append("")

    # Theta decay analysis
    # Estimate weekly theta loss (rough approximation)
    chain = get_options_chain(ticker, 30, 730, redis_client)
    options = chain.get("calls", [])
    theta_weekly = None
    if options:
        # Find the longest-dated option as proxy
        longest = max(options, key=lambda o: o.get("dte", 0))
        if longest.get("dte", 0) > 0 and longest.get("implied_volatility", 0) > 0:
            T = longest["dte"] / 365.0
            daily_theta = estimate_theta(
                price or 100, longest["strike"], T, 0.05,
                longest["implied_volatility"], "call"
            )
            theta_weekly = abs(daily_theta) * 5 * 100  # per contract, per week

    lines.append("THETA DECAY VS TAX SAVINGS:")
    if theta_weekly and theta_weekly > 0:
        lines.append(f"  Estimated Weekly Theta Loss: ~${theta_weekly:.2f}/contract")
        if days_to_ltcg > 0:
            weeks_to_wait = days_to_ltcg / 7
            total_theta_cost = theta_weekly * weeks_to_wait
            lines.append(f"  Weeks to Wait: {weeks_to_wait:.1f}")
            lines.append(f"  Total Theta Cost of Waiting: ~${total_theta_cost:,.2f}")
            lines.append("")
            if tax_savings > total_theta_cost:
                net_benefit = tax_savings - total_theta_cost
                lines.append(f"  HOLD: Tax savings (${tax_savings:,.2f}) > Theta cost (${total_theta_cost:,.2f})")
                lines.append(f"  Net benefit of waiting: ${net_benefit:,.2f}")
            else:
                net_cost = total_theta_cost - tax_savings
                lines.append(f"  SELL NOW: Theta cost (${total_theta_cost:,.2f}) > Tax savings (${tax_savings:,.2f})")
                lines.append(f"  Net cost of waiting: ${net_cost:,.2f}")
    else:
        lines.append("  Could not estimate theta decay (insufficient chain data).")
        if days_to_ltcg > 0 and tax_savings > 0:
            lines.append(f"  Tax savings of ${tax_savings:,.2f} is the key factor.")
    lines.append("")

    # RSI check
    rsi = _calculate_rsi(history) if history else None
    lines.append("TECHNICAL CHECK:")
    if rsi:
        lines.append(f"  RSI: {rsi:.1f}")
        if rsi > 70 and days_to_ltcg > 30:
            lines.append("  OVERBOUGHT - stock may pull back before your 1-year mark.")
            lines.append("  Consider taking profits if theta cost > tax savings.")
        elif rsi > 70 and days_to_ltcg <= 30:
            lines.append("  Overbought, but only {days_to_ltcg} days to LTCG. Hold tight.")
        else:
            lines.append("  Not overbought. No urgency to sell early.")
    else:
        lines.append("  Could not calculate RSI.")

    return "\n".join(lines)


# ── Tool 11: Portfolio Correlation Audit ───────────────────────────────

def portfolio_correlation_audit(positions: List[Dict]) -> str:
    """
    Audit portfolio for hidden correlations and concentration risk.

    positions: list of {ticker: str, allocation_pct: float}
    """
    lines = []
    lines.append("=" * 60)
    lines.append("PORTFOLIO CORRELATION AUDIT")
    lines.append("=" * 60)
    lines.append("")

    if not positions:
        return "\n".join(lines + ["No positions provided."])

    # Map positions to sectors
    lines.append("POSITION BREAKDOWN:")
    lines.append(f"  {'Ticker':>8} | {'Allocation':>10} | {'Sector'}")
    lines.append(f"  {'-'*8}-+-{'-'*10}-+-{'-'*20}")
    sector_totals = {}
    for pos in positions:
        ticker = pos.get("ticker", "?")
        alloc = pos.get("allocation_pct", 0)
        sector = _get_sector(ticker)
        lines.append(f"  {ticker:>8} | {alloc:>9.1f}% | {sector}")
        sector_totals[sector] = sector_totals.get(sector, 0) + alloc
    lines.append("")

    # Sector concentration
    lines.append("SECTOR CONCENTRATION:")
    for sector, total in sorted(sector_totals.items(), key=lambda x: -x[1]):
        bar = "#" * int(total / 2)
        warning = " <-- CONCENTRATED!" if total > 30 else ""
        lines.append(f"  {sector:>20}: {total:>5.1f}% {bar}{warning}")
    lines.append("")

    # Correlation groups
    lines.append("CORRELATION GROUPS (move together in stress):")
    portfolio_tickers = {pos.get("ticker", "").upper() for pos in positions}

    found_correlations = False
    for group_name, group_tickers in CORRELATION_GROUPS.items():
        overlap = portfolio_tickers.intersection(set(group_tickers))
        if len(overlap) >= 2:
            found_correlations = True
            overlap_alloc = sum(
                pos.get("allocation_pct", 0)
                for pos in positions
                if pos.get("ticker", "").upper() in overlap
            )
            lines.append(f"  {group_name}:")
            lines.append(f"    Positions: {', '.join(sorted(overlap))}")
            lines.append(f"    Combined allocation: {overlap_alloc:.1f}%")
            lines.append(f"    These would ALL drop together in a selloff.")

    if not found_correlations:
        lines.append("  No significant correlations found between your holdings.")
        lines.append("  Good diversification!")
    lines.append("")

    # Hidden bets analysis
    lines.append("HIDDEN BETS:")
    # Check if making same directional bet multiple times
    sector_counts = {}
    for pos in positions:
        sector = _get_sector(pos.get("ticker", ""))
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    for sector, count in sector_counts.items():
        if count >= 3:
            lines.append(f"  You have {count} positions in {sector}.")
            lines.append(f"  You're making the same bet {count} times.")
    lines.append("")

    # Most vulnerable position
    lines.append("MOST VULNERABLE POSITION:")
    if positions:
        # Largest allocation = most risk
        largest = max(positions, key=lambda p: p.get("allocation_pct", 0))
        lines.append(f"  {largest.get('ticker', '?')} at {largest.get('allocation_pct', 0):.1f}% allocation")
        lines.append(f"  A 30% drop here impacts {largest.get('allocation_pct', 0) * 0.30:.1f}% of your portfolio")
    lines.append("")

    # Cut recommendation
    lines.append("IF YOU MUST CUT 2 POSITIONS:")
    if len(positions) >= 3:
        # Sort by: highest sector concentration + smallest allocation (cut the weakest overlapping)
        scored = []
        for pos in positions:
            sector = _get_sector(pos.get("ticker", ""))
            sector_weight = sector_totals.get(sector, 0)
            # Higher score = more redundant (high sector weight, small position)
            score = sector_weight / max(pos.get("allocation_pct", 1), 0.1)
            scored.append((pos, score))

        scored.sort(key=lambda x: -x[1])
        cuts = scored[:2]
        for pos, score in cuts:
            ticker = pos.get("ticker", "?")
            sector = _get_sector(ticker)
            lines.append(f"  CUT: {ticker} ({sector}) - redundant sector exposure")
    else:
        lines.append("  Not enough positions to recommend cuts.")

    return "\n".join(lines)


# ── Tool 12: Pre-Trade Exit Plan ───────────────────────────────────────

def pre_trade_exit_plan(
    ticker: str, strategy: str, strike: float,
    expiration: str, premium: float, redis_client=None,
) -> str:
    """Build a 3-scenario exit plan before entering a trade."""
    price = get_price(ticker, redis_client)
    if price is None:
        return f"ERROR: Could not fetch price for {ticker}."

    history = get_price_history(ticker, 90, redis_client)
    sr = _find_support_resistance(history) if history else {"supports": [], "resistances": []}

    try:
        exp_dt = datetime.strptime(expiration, "%Y-%m-%d")
        dte = (exp_dt - datetime.now()).days
    except ValueError:
        dte = 30

    lines = []
    lines.append("=" * 60)
    lines.append(f"PRE-TRADE EXIT PLAN: {ticker}")
    lines.append("=" * 60)
    lines.append(f"Strategy: {strategy.upper()}")
    lines.append(f"Strike: ${strike:.2f}")
    lines.append(f"Premium: ${premium:.2f}/share")
    lines.append(f"Expiration: {expiration} ({dte} DTE)")
    lines.append(f"Current Price: ${price:.2f}")
    lines.append("")

    is_short = strategy.lower() in ("csp", "cc", "covered_call", "cash_secured_put", "short_put", "short_call")

    # ── Scenario 1: It Works ──
    lines.append("=" * 40)
    lines.append("SCENARIO 1: IT WORKS")
    lines.append("=" * 40)
    if is_short:
        target_50 = premium * 0.50
        buyback = premium - target_50
        lines.append(f"  Close at 50% profit: buy back at ${buyback:.2f}/share")
        lines.append(f"  Profit: ${target_50:.2f}/share (${target_50*100:.2f}/contract)")
        lines.append(f"  Do NOT hold for the last 50% - it takes the longest to decay.")
        lines.append(f"  Close and redeploy capital.")
    else:
        # Long option
        target_100 = premium * 2.0  # 100% gain
        target_50 = premium * 1.5
        lines.append(f"  Target 1 (50% gain): sell at ${target_50:.2f}/share")
        lines.append(f"  Target 2 (100% gain): sell at ${target_100:.2f}/share")
        lines.append(f"  Scale out: sell half at 50% gain, let the rest ride to 100%.")
    lines.append("")

    # ── Scenario 2: It Goes Against You ──
    lines.append("=" * 40)
    lines.append("SCENARIO 2: IT GOES AGAINST ME")
    lines.append("=" * 40)
    if is_short:
        roll_trigger = premium * 2.0  # 100% loss on premium = roll
        max_loss = premium * 3.0  # 200% = absolute stop
        lines.append(f"  ROLL TRIGGER: option doubles to ${roll_trigger:.2f}/share")
        lines.append(f"    -> Roll out to next month for a credit")
        lines.append(f"  STOP LOSS: option triples to ${max_loss:.2f}/share")
        lines.append(f"    -> Close the position. Thesis is broken.")
        lines.append("")
        lines.append(f"  What breaks the thesis?")
        lines.append(f"    - Stock moves {('above' if 'put' in strategy.lower() else 'below')} ${strike:.2f} with momentum")
        lines.append(f"    - Fundamental shift (earnings miss, sector rotation)")
    else:
        stop_loss = premium * 0.50  # 50% loss on a long option
        lines.append(f"  STOP LOSS: option drops to ${stop_loss:.2f}/share (50% loss)")
        lines.append(f"    -> Close. Don't let a long option go to zero.")
        if sr["supports"]:
            lines.append(f"  If stock hits support at ${sr['supports'][0]:.2f}, reassess.")
        else:
            lines.append(f"  If stock hits key support levels, reassess.")
    lines.append("")

    # ── Scenario 3: Nothing Happens ──
    lines.append("=" * 40)
    lines.append("SCENARIO 3: NOTHING HAPPENS (SIDEWAYS)")
    lines.append("=" * 40)
    if is_short:
        lines.append(f"  This is the BEST scenario for sellers.")
        lines.append(f"  Theta works in your favor every day.")
        lines.append(f"  Hold until 50% profit target, then close.")
        if dte > 14:
            lines.append(f"  If not at 50% by {dte // 2} days, evaluate rolling.")
    else:
        lines.append(f"  Sideways is BAD for long options - theta eats you alive.")
        lines.append(f"  If no movement by {dte // 3} days ({dte - dte // 3} DTE):")
        lines.append(f"    -> Close to salvage remaining time value")
        lines.append(f"    -> Don't hold a long option hoping for a last-minute move")
    lines.append("")

    # Catalysts
    lines.append("UPCOMING CATALYSTS:")
    lines.append(f"  Check for:")
    lines.append(f"  - Earnings dates between now and {expiration}")
    lines.append(f"  - Ex-dividend dates (assignment risk for short calls)")
    lines.append(f"  - Fed meetings / economic data releases")
    lines.append(f"  - Sector-specific events")
    lines.append(f"  (Use Advisor #8 Earnings Risk Screener if earnings are near)")
    lines.append("")

    lines.append("=" * 60)
    lines.append("SAVE THIS PLAN. Reference it when emotional.")
    lines.append("The plan was made with a clear head. Trust it.")
    lines.append("=" * 60)

    return "\n".join(lines)


# ── Advisor Name Map ───────────────────────────────────────────────────

ADVISOR_NAMES = {
    1: "IV Environment Scanner",
    2: "Cash-Secured Put Strike Finder",
    3: "30 DTE Theta Decay Optimizer",
    4: "Covered Call Timing Setup",
    5: "Wheel Cycle Tracker",
    6: "LEAP Entry Checklist",
    7: "Position Sizing Stress Test",
    8: "Earnings Risk Screener",
    9: "Strategy Decision Framework",
    10: "LEAP Tax Timer",
    11: "Portfolio Correlation Audit",
    12: "Pre-Trade Exit Plan",
}


def list_advisors() -> str:
    """List all available advisor tools."""
    lines = ["", "AVAILABLE ADVISOR TOOLS:", ""]
    for num, name in ADVISOR_NAMES.items():
        lines.append(f"  {num:>2}. {name}")
    lines.append("")
    lines.append("Usage: python -m autonomous.runner --advisor <number> --ticker <TICKER> [options]")
    return "\n".join(lines)
