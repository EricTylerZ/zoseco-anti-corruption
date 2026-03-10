"""
Options pricing and spread metric calculations.

Uses Python stdlib math.erf for normal CDF (no scipy needed).
"""

import math
from typing import Dict


def norm_cdf(x: float) -> float:
    """Standard normal cumulative distribution function using math.erf."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Black-Scholes put option price.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration in years
        r: Risk-free rate (annualized)
        sigma: Volatility (annualized)

    Returns:
        Theoretical put price per share
    """
    if T <= 0 or sigma <= 0:
        return max(K - S, 0.0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    put_price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
    return max(put_price, 0.0)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """
    Black-Scholes call option price.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiration in years
        r: Risk-free rate (annualized)
        sigma: Volatility (annualized)

    Returns:
        Theoretical call price per share
    """
    if T <= 0 or sigma <= 0:
        return max(S - K, 0.0)

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    call_price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    return max(call_price, 0.0)


def put_debit_spread_metrics(
    long_strike: float,
    short_strike: float,
    net_debit: float,
) -> Dict[str, float]:
    """
    Calculate metrics for a put debit spread (bearish).

    Buy higher strike put, sell lower strike put.

    Args:
        long_strike: Strike of the put you BUY (higher)
        short_strike: Strike of the put you SELL (lower)
        net_debit: Net premium paid per share

    Returns:
        Dict with max_loss, max_profit, breakeven, risk_reward
    """
    spread_width = long_strike - short_strike
    max_loss = net_debit * 100  # per contract
    max_profit = (spread_width - net_debit) * 100
    breakeven = long_strike - net_debit
    risk_reward = max_profit / max_loss if max_loss > 0 else 0.0

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(breakeven, 2),
        "risk_reward": round(risk_reward, 2),
        "spread_width": spread_width,
    }


def call_debit_spread_metrics(
    long_strike: float,
    short_strike: float,
    net_debit: float,
) -> Dict[str, float]:
    """
    Calculate metrics for a call debit spread (bullish).

    Buy lower strike call, sell higher strike call.

    Args:
        long_strike: Strike of the call you BUY (lower)
        short_strike: Strike of the call you SELL (higher)
        net_debit: Net premium paid per share

    Returns:
        Dict with max_loss, max_profit, breakeven, risk_reward
    """
    spread_width = short_strike - long_strike
    max_loss = net_debit * 100
    max_profit = (spread_width - net_debit) * 100
    breakeven = long_strike + net_debit
    risk_reward = max_profit / max_loss if max_loss > 0 else 0.0

    return {
        "max_loss": round(max_loss, 2),
        "max_profit": round(max_profit, 2),
        "breakeven": round(breakeven, 2),
        "risk_reward": round(risk_reward, 2),
        "spread_width": spread_width,
    }


def estimate_delta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Approximate delta for position monitoring."""
    if T <= 0 or sigma <= 0:
        if option_type == "call":
            return 1.0 if S > K else 0.0
        else:
            return -1.0 if S < K else 0.0

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))

    if option_type == "call":
        return norm_cdf(d1)
    else:
        return norm_cdf(d1) - 1.0


def estimate_theta(S: float, K: float, T: float, r: float, sigma: float, option_type: str) -> float:
    """Approximate daily theta (time decay) per share."""
    if T <= 0 or sigma <= 0:
        return 0.0

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    # Standard normal PDF
    nd1 = math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi)

    if option_type == "call":
        theta = (-(S * nd1 * sigma) / (2 * math.sqrt(T))
                 - r * K * math.exp(-r * T) * norm_cdf(d2))
    else:
        theta = (-(S * nd1 * sigma) / (2 * math.sqrt(T))
                 + r * K * math.exp(-r * T) * norm_cdf(-d2))

    return theta / 365.0  # daily theta
