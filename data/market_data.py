"""
Market data fetching via Yahoo Finance JSON API.

Uses direct HTTP calls (no yfinance dependency) to stay lightweight
and compatible with Vercel's 15MB lambda limit.
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import requests

from config.settings import (
    YAHOO_CHART_URL,
    YAHOO_OPTIONS_URL,
    MIN_DTE,
    MAX_DTE,
    PRICE_CACHE_TTL,
    OPTIONS_CACHE_TTL,
    MOMENTUM_THRESHOLD,
    MOMENTUM_LOOKBACK_DAYS,
    MOMENTUM_STRONG_THRESHOLD,
)


# Yahoo Finance requires a user-agent header
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# In-memory cache fallback when Redis is unavailable
_mem_cache: Dict[str, Tuple[float, any]] = {}


def _cache_get(key: str, redis_client=None) -> Optional[str]:
    """Get from Redis or memory cache."""
    if redis_client:
        try:
            val = redis_client.get(key)
            if val:
                return val.decode() if isinstance(val, bytes) else val
        except Exception:
            pass

    entry = _mem_cache.get(key)
    if entry and time.time() < entry[0]:
        return entry[1]
    return None


def _cache_set(key: str, value: str, ttl: int, redis_client=None):
    """Set in Redis and memory cache."""
    _mem_cache[key] = (time.time() + ttl, value)
    if redis_client:
        try:
            redis_client.setex(key, ttl, value)
        except Exception:
            pass


def get_price(ticker: str, redis_client=None) -> Optional[float]:
    """
    Fetch current price for a ticker.

    Returns None if the request fails.
    """
    cache_key = f"fin:price:{ticker}"
    cached = _cache_get(cache_key, redis_client)
    if cached:
        return float(cached)

    url = YAHOO_CHART_URL.format(ticker=ticker)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        result = data["chart"]["result"][0]
        price = result["meta"]["regularMarketPrice"]

        _cache_set(cache_key, str(price), PRICE_CACHE_TTL, redis_client)
        return float(price)
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
        return None


def get_prices(tickers: List[str], redis_client=None) -> Dict[str, Optional[float]]:
    """Fetch prices for multiple tickers."""
    return {ticker: get_price(ticker, redis_client) for ticker in tickers}


def get_options_chain(
    ticker: str,
    min_dte: int = MIN_DTE,
    max_dte: int = MAX_DTE,
    redis_client=None,
) -> Dict:
    """
    Fetch options chain for a ticker, filtered by DTE range.

    Returns dict with:
        - expirations: list of valid expiration dates
        - puts: list of put option dicts
        - calls: list of call option dicts
        - current_price: underlying price
    """
    # First, get available expirations
    cache_key = f"fin:options:{ticker}:{min_dte}:{max_dte}"
    cached = _cache_get(cache_key, redis_client)
    if cached:
        return json.loads(cached)

    url = YAHOO_OPTIONS_URL.format(ticker=ticker)
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        option_chain = data["optionChain"]["result"][0]
        current_price = option_chain["quote"]["regularMarketPrice"]
        expiration_timestamps = option_chain.get("expirationDates", [])

        now = datetime.now()
        min_date = now + timedelta(days=min_dte)
        max_date = now + timedelta(days=max_dte)

        valid_expirations = []
        for ts in expiration_timestamps:
            exp_date = datetime.fromtimestamp(ts)
            if min_date <= exp_date <= max_date:
                valid_expirations.append(ts)

        all_puts = []
        all_calls = []

        # Fetch options for each valid expiration
        for exp_ts in valid_expirations:
            exp_url = f"{url}?date={exp_ts}"
            try:
                exp_resp = requests.get(exp_url, headers=_HEADERS, timeout=10)
                exp_resp.raise_for_status()
                exp_data = exp_resp.json()

                options = exp_data["optionChain"]["result"][0].get("options", [{}])[0]
                exp_date_str = datetime.fromtimestamp(exp_ts).strftime("%Y-%m-%d")
                dte = (datetime.fromtimestamp(exp_ts) - now).days

                for put in options.get("puts", []):
                    all_puts.append(_parse_option(put, exp_date_str, dte, "put"))

                for call in options.get("calls", []):
                    all_calls.append(_parse_option(call, exp_date_str, dte, "call"))

            except Exception as e:
                print(f"Error fetching options for {ticker} exp {exp_ts}: {e}")
                continue

        result = {
            "ticker": ticker,
            "current_price": current_price,
            "expirations": [
                datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                for ts in valid_expirations
            ],
            "puts": all_puts,
            "calls": all_calls,
        }

        _cache_set(cache_key, json.dumps(result), OPTIONS_CACHE_TTL, redis_client)
        return result

    except Exception as e:
        print(f"Error fetching options chain for {ticker}: {e}")
        return {"ticker": ticker, "current_price": None, "expirations": [], "puts": [], "calls": []}


def _parse_option(option: dict, expiration: str, dte: int, option_type: str) -> dict:
    """Parse a Yahoo Finance option into a clean dict."""
    return {
        "type": option_type,
        "strike": option.get("strike", 0),
        "expiration": expiration,
        "dte": dte,
        "bid": option.get("bid", 0),
        "ask": option.get("ask", 0),
        "mid": round((option.get("bid", 0) + option.get("ask", 0)) / 2, 4),
        "last": option.get("lastPrice", 0),
        "volume": option.get("volume", 0),
        "open_interest": option.get("openInterest", 0),
        "implied_volatility": option.get("impliedVolatility", 0),
        "in_the_money": option.get("inTheMoney", False),
    }


def get_price_history(
    ticker: str, days: int = 30, redis_client=None
) -> Optional[List[Dict]]:
    """
    Fetch daily OHLC price history for a ticker.

    Returns list of dicts with date, open, high, low, close, volume.
    """
    cache_key = f"fin:history:{ticker}:{days}"
    cached = _cache_get(cache_key, redis_client)
    if cached:
        return json.loads(cached)

    url = YAHOO_CHART_URL.format(ticker=ticker)
    params = {
        "range": f"{days}d",
        "interval": "1d",
    }
    try:
        resp = requests.get(url, headers=_HEADERS, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        result = data["chart"]["result"][0]
        timestamps = result.get("timestamp", [])
        indicators = result.get("indicators", {}).get("quote", [{}])[0]

        history = []
        for i, ts in enumerate(timestamps):
            history.append({
                "date": datetime.fromtimestamp(ts).strftime("%Y-%m-%d"),
                "open": indicators.get("open", [None])[i],
                "high": indicators.get("high", [None])[i],
                "low": indicators.get("low", [None])[i],
                "close": indicators.get("close", [None])[i],
                "volume": indicators.get("volume", [None])[i],
            })

        _cache_set(cache_key, json.dumps(history), PRICE_CACHE_TTL, redis_client)
        return history
    except Exception as e:
        print(f"Error fetching price history for {ticker}: {e}")
        return None


def detect_momentum(
    ticker: str,
    direction: str = "bearish",
    lookback_days: int = MOMENTUM_LOOKBACK_DAYS,
    redis_client=None,
) -> Dict:
    """
    Detect price momentum for a ticker.

    Args:
        ticker: Stock/ETF ticker
        direction: Expected thesis direction ("bearish" or "bullish")
        lookback_days: Number of days to measure momentum
        redis_client: Optional Redis client

    Returns dict with:
        - ticker: str
        - pct_change: float (% change over lookback)
        - signal: "strong", "weak", or "none"
        - aligned: bool (True if momentum matches thesis direction)
        - strength: float (0.0 to 1.0)
    """
    history = get_price_history(ticker, lookback_days + 5, redis_client)

    if not history or len(history) < 2:
        return {
            "ticker": ticker,
            "pct_change": 0.0,
            "signal": "none",
            "aligned": False,
            "strength": 0.0,
        }

    # Use the last `lookback_days` of data
    recent = history[-lookback_days:] if len(history) >= lookback_days else history
    first_close = recent[0].get("close")
    last_close = recent[-1].get("close")

    if not first_close or not last_close or first_close == 0:
        return {
            "ticker": ticker,
            "pct_change": 0.0,
            "signal": "none",
            "aligned": False,
            "strength": 0.0,
        }

    pct_change = (last_close - first_close) / first_close
    abs_change = abs(pct_change)

    # Determine if momentum aligns with thesis direction
    if direction == "bearish":
        aligned = pct_change < 0  # price dropping = good for bearish thesis
    else:
        aligned = pct_change > 0  # price rising = good for bullish thesis

    # Signal strength
    if abs_change >= MOMENTUM_STRONG_THRESHOLD:
        signal = "strong"
        strength = min(abs_change / MOMENTUM_STRONG_THRESHOLD, 2.0) / 2.0
    elif abs_change >= MOMENTUM_THRESHOLD:
        signal = "weak"
        strength = abs_change / MOMENTUM_STRONG_THRESHOLD
    else:
        signal = "none"
        strength = 0.0

    # If not aligned, strength is negative (working against us)
    if not aligned and signal != "none":
        strength = -strength

    return {
        "ticker": ticker,
        "pct_change": round(pct_change, 4),
        "signal": signal,
        "aligned": aligned,
        "strength": round(strength, 3),
    }


def get_quote_summary(ticker: str, redis_client=None) -> Optional[Dict]:
    """Get basic quote info for a ticker."""
    price = get_price(ticker, redis_client)
    if price is None:
        return None

    return {
        "ticker": ticker,
        "price": price,
        "fetched_at": datetime.now().isoformat(),
    }
