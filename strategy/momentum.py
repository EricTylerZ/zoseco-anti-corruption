"""
Momentum engine: detects which theses are actively moving and recommends
dynamic allocation shifts.

When a thesis is "hot" (price moving in predicted direction), concentrate
capital there. When all theses align, we're in cascade/collapse mode.
"""

from typing import Dict, List, Optional

from config.theses import THESES, TOTAL_CAPITAL
from data.market_data import detect_momentum


def scan_momentum(redis_client=None) -> Dict[str, Dict]:
    """
    Scan all thesis tickers for momentum signals.

    Returns dict keyed by thesis_id with:
    - thesis_name: str
    - tickers: dict of ticker momentum signals
    - thesis_signal: "strong", "weak", or "none"
    - thesis_strength: float (-1.0 to 1.0)
    """
    results = {}

    for thesis_id, thesis in THESES.items():
        ticker_signals = {}
        total_strength = 0.0
        aligned_count = 0

        for ticker, ticker_info in thesis["tickers"].items():
            signal = detect_momentum(
                ticker,
                direction=ticker_info["direction"],
                redis_client=redis_client,
            )
            ticker_signals[ticker] = signal
            total_strength += signal["strength"] * ticker_info["weight"]
            if signal["aligned"] and signal["signal"] != "none":
                aligned_count += 1

        # Thesis-level signal
        ticker_count = len(thesis["tickers"])
        if aligned_count == ticker_count and total_strength > 0.3:
            thesis_signal = "strong"
        elif aligned_count >= ticker_count / 2 and total_strength > 0:
            thesis_signal = "weak"
        else:
            thesis_signal = "none"

        results[thesis_id] = {
            "thesis_name": thesis["name"],
            "tickers": ticker_signals,
            "thesis_signal": thesis_signal,
            "thesis_strength": round(total_strength, 3),
            "aligned_count": aligned_count,
            "total_tickers": ticker_count,
        }

    return results


def detect_cascade(momentum_results: Dict[str, Dict]) -> Dict:
    """
    Detect if all theses are showing momentum simultaneously (cascade mode).

    A cascade means the entire system is under stress - all three pillars
    (food supply, monetary, housing) are moving at once. This is the
    big event we're positioning for.

    Returns:
    - cascade: bool
    - active_theses: list of thesis_ids with momentum
    - recommended_mode: "conservative", "aggressive", or "maximum"
    - reason: str
    """
    active = []
    strong = []

    for thesis_id, data in momentum_results.items():
        if data["thesis_signal"] in ("strong", "weak"):
            active.append(thesis_id)
        if data["thesis_signal"] == "strong":
            strong.append(thesis_id)

    if len(strong) >= 2 or len(active) == len(THESES):
        return {
            "cascade": True,
            "active_theses": active,
            "strong_theses": strong,
            "recommended_mode": "maximum",
            "reason": (
                f"CASCADE DETECTED: {len(active)}/{len(THESES)} theses active, "
                f"{len(strong)} showing strong momentum. "
                "System-wide stress - concentrate on fastest movers."
            ),
        }
    elif len(active) >= 2:
        return {
            "cascade": False,
            "active_theses": active,
            "strong_theses": strong,
            "recommended_mode": "aggressive",
            "reason": (
                f"{len(active)} theses showing momentum. "
                "Consider aggressive mode for faster rotation."
            ),
        }
    elif len(active) == 1:
        return {
            "cascade": False,
            "active_theses": active,
            "strong_theses": strong,
            "recommended_mode": "aggressive",
            "reason": (
                f"Single thesis active: {active[0]}. "
                "Shift allocation toward this thesis."
            ),
        }
    else:
        return {
            "cascade": False,
            "active_theses": [],
            "strong_theses": [],
            "recommended_mode": "conservative",
            "reason": "No momentum detected. Stay in conservative mode.",
        }


def get_dynamic_allocation(
    momentum_results: Dict[str, Dict],
    cascade_info: Dict,
) -> Dict[str, float]:
    """
    Calculate dynamic allocation percentages based on momentum.

    In normal mode, uses static allocation from theses config.
    When momentum is detected, shifts capital toward hot theses.
    In cascade mode, concentrates heavily on the strongest movers.
    """
    base_alloc = {
        tid: thesis["allocation_pct"] for tid, thesis in THESES.items()
    }

    if cascade_info["recommended_mode"] == "conservative":
        return base_alloc

    # Start with base allocation
    dynamic = dict(base_alloc)

    # Calculate momentum boost factor
    active = cascade_info["active_theses"]
    inactive = [t for t in THESES if t not in active]

    if not active:
        return dynamic

    # Steal allocation from inactive theses
    if cascade_info["recommended_mode"] == "maximum":
        steal_pct = 0.70  # take 70% from inactive theses
    else:
        steal_pct = 0.40  # take 40% from inactive theses

    stolen = 0.0
    for tid in inactive:
        amount = dynamic[tid] * steal_pct
        dynamic[tid] -= amount
        stolen += amount

    # Distribute stolen allocation to active theses weighted by strength
    total_strength = sum(
        max(momentum_results[tid]["thesis_strength"], 0.01) for tid in active
    )
    for tid in active:
        strength = max(momentum_results[tid]["thesis_strength"], 0.01)
        dynamic[tid] += stolen * (strength / total_strength)

    # Normalize to ensure we sum to 1.0
    total = sum(dynamic.values())
    if total > 0:
        dynamic = {tid: v / total for tid, v in dynamic.items()}

    return {tid: round(v, 3) for tid, v in dynamic.items()}


def format_momentum_report(
    momentum_results: Dict[str, Dict],
    cascade_info: Dict,
    dynamic_alloc: Dict[str, float],
) -> str:
    """Format momentum analysis as readable text."""
    lines = []
    lines.append("=" * 60)
    lines.append("MOMENTUM ANALYSIS")
    lines.append("=" * 60)

    for thesis_id, data in momentum_results.items():
        signal_icon = {
            "strong": ">>>",
            "weak": " >>",
            "none": "  -",
        }[data["thesis_signal"]]

        lines.append(
            f"\n{signal_icon} {data['thesis_name']} "
            f"[{data['thesis_signal'].upper()}] "
            f"(strength: {data['thesis_strength']:+.3f})"
        )
        lines.append(
            f"    Aligned: {data['aligned_count']}/{data['total_tickers']} tickers"
        )

        for ticker, sig in data["tickers"].items():
            aligned_mark = "+" if sig["aligned"] else "-"
            lines.append(
                f"    {aligned_mark} {ticker}: "
                f"{sig['pct_change']:+.2%} over lookback "
                f"[{sig['signal']}]"
            )

    lines.append(f"\n{'=' * 60}")
    lines.append("CASCADE STATUS")
    lines.append(f"{'=' * 60}")

    if cascade_info["cascade"]:
        lines.append("\n*** CASCADE MODE ACTIVE ***")
    lines.append(f"\n{cascade_info['reason']}")
    lines.append(f"Recommended mode: {cascade_info['recommended_mode'].upper()}")

    lines.append(f"\n{'=' * 60}")
    lines.append("DYNAMIC ALLOCATION")
    lines.append(f"{'=' * 60}")

    for thesis_id, alloc in dynamic_alloc.items():
        thesis = THESES[thesis_id]
        base = thesis["allocation_pct"]
        diff = alloc - base
        diff_str = f" ({diff:+.1%})" if abs(diff) > 0.001 else ""
        lines.append(
            f"  {thesis['name']}: {alloc:.1%} "
            f"(${TOTAL_CAPITAL * alloc:.2f}){diff_str}"
        )

    lines.append("\n" + "=" * 60)
    return "\n".join(lines)
