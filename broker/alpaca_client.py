"""
Alpaca API client for live options trading.

Wraps the alpaca-trade-api SDK for placing spreads,
checking positions, and managing orders.
"""

import os
from typing import List, Dict, Optional
from datetime import datetime

try:
    import alpaca_trade_api as tradeapi
    HAS_ALPACA = True
except ImportError:
    HAS_ALPACA = False

from core.models import OptionLeg, SpreadTrade


def _get_api():
    """Initialize Alpaca API connection."""
    if not HAS_ALPACA:
        raise RuntimeError(
            "alpaca-trade-api not installed. Run: pip install alpaca-trade-api"
        )

    api_key = os.environ.get("ALPACA_API_KEY")
    secret_key = os.environ.get("ALPACA_SECRET_KEY")
    paper = os.environ.get("ALPACA_PAPER", "false").lower() == "true"

    if not api_key or not secret_key:
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in environment"
        )

    base_url = (
        "https://paper-api.alpaca.markets"
        if paper
        else "https://api.alpaca.markets"
    )

    return tradeapi.REST(api_key, secret_key, base_url, api_version="v2")


def get_account() -> Dict:
    """Get account info (balance, buying power, etc)."""
    api = _get_api()
    account = api.get_account()
    return {
        "id": account.id,
        "status": account.status,
        "cash": float(account.cash),
        "buying_power": float(account.buying_power),
        "portfolio_value": float(account.portfolio_value),
        "equity": float(account.equity),
        "currency": account.currency,
    }


def place_option_order(
    ticker: str,
    option_type: str,      # "put" or "call"
    strike: float,
    expiration: str,        # YYYY-MM-DD
    action: str,            # "buy" or "sell"
    quantity: int = 1,
    order_type: str = "limit",
    limit_price: Optional[float] = None,
) -> Dict:
    """
    Place a single-leg option order.

    Returns order details dict.
    """
    api = _get_api()

    # Alpaca option symbol format: e.g., "AAPL250321C00150000"
    symbol = _format_option_symbol(ticker, expiration, option_type, strike)

    side = "buy" if action == "buy" else "sell"

    order_params = {
        "symbol": symbol,
        "qty": quantity,
        "side": side,
        "type": order_type,
        "time_in_force": "day",
    }

    if limit_price and order_type == "limit":
        order_params["limit_price"] = str(limit_price)

    order = api.submit_order(**order_params)
    return {
        "order_id": order.id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "status": order.status,
        "submitted_at": str(order.submitted_at),
    }


def place_spread_order(trade: SpreadTrade) -> Dict:
    """
    Place a multi-leg spread order (debit spread).

    For a put debit spread: buy the higher strike put, sell the lower strike put.
    For a call debit spread: buy the lower strike call, sell the higher strike call.

    Returns order details.
    """
    api = _get_api()

    if len(trade.legs) != 2:
        raise ValueError("Spread must have exactly 2 legs")

    legs = []
    for leg in trade.legs:
        symbol = _format_option_symbol(
            leg.ticker, leg.expiration, leg.option_type, leg.strike
        )
        legs.append({
            "symbol": symbol,
            "side": "buy" if leg.action == "buy" else "sell",
            "qty": str(leg.quantity),
        })

    # Net debit as limit price
    limit_price = trade.net_debit / 100  # per-share price

    try:
        order = api.submit_order(
            symbol=trade.ticker,
            qty=1,
            side="buy",
            type="limit",
            time_in_force="day",
            limit_price=str(round(limit_price, 2)),
            order_class="bracket" if len(legs) > 1 else "simple",
            legs=legs,
        )
        return {
            "order_id": order.id,
            "status": order.status,
            "legs": legs,
            "limit_price": limit_price,
            "submitted_at": str(order.submitted_at),
        }
    except Exception as e:
        return {
            "error": str(e),
            "legs": legs,
            "limit_price": limit_price,
        }


def get_positions() -> List[Dict]:
    """Get all open positions from Alpaca."""
    api = _get_api()
    positions = api.list_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": int(p.qty),
            "side": p.side,
            "market_value": float(p.market_value),
            "cost_basis": float(p.cost_basis),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
            "current_price": float(p.current_price),
        }
        for p in positions
    ]


def get_orders(status: str = "open") -> List[Dict]:
    """Get orders by status."""
    api = _get_api()
    orders = api.list_orders(status=status)
    return [
        {
            "order_id": o.id,
            "symbol": o.symbol,
            "side": o.side,
            "qty": o.qty,
            "type": o.type,
            "status": o.status,
            "limit_price": o.limit_price,
            "submitted_at": str(o.submitted_at),
            "filled_at": str(o.filled_at) if o.filled_at else None,
        }
        for o in orders
    ]


def cancel_order(order_id: str) -> bool:
    """Cancel an open order."""
    api = _get_api()
    try:
        api.cancel_order(order_id)
        return True
    except Exception:
        return False


def _format_option_symbol(
    ticker: str,
    expiration: str,
    option_type: str,
    strike: float,
) -> str:
    """
    Format OCC option symbol.

    Format: TICKER + YYMMDD + C/P + strike*1000 (8 digits, zero-padded)
    Example: TSN250418P00050000 = TSN put, $50 strike, exp 2025-04-18
    """
    exp_date = datetime.strptime(expiration, "%Y-%m-%d")
    date_str = exp_date.strftime("%y%m%d")
    type_char = "C" if option_type == "call" else "P"
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    return f"{ticker}{date_str}{type_char}{strike_str}"
