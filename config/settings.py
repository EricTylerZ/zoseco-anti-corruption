"""
Trading settings and rules.

Two modes:
- Conservative (default): monthly options, strict liquidity
- Aggressive (--aggressive): weekly options, momentum-driven, fast rotation
"""

# === Conservative mode (default) ===

# Days to expiration targets
MIN_DTE = 30
MAX_DTE = 90
TARGET_DTE = 45  # preferred DTE for new positions

# Roll trigger: close and re-open when DTE falls below this
ROLL_DTE_TRIGGER = 21

# Spread width options (strike distance)
SPREAD_WIDTHS = [2.5, 5.0]

# Minimum liquidity filters for options
MIN_VOLUME = 5
MIN_OPEN_INTEREST = 20
MAX_BID_ASK_SPREAD_PCT = 0.50  # 50% of mid price

# Position limits
MAX_POSITIONS_PER_THESIS = 2
MAX_TOTAL_POSITIONS = 6

# === Aggressive mode (--aggressive) ===
# Weekly options, faster rotation, momentum-driven allocation

AGGRESSIVE_MIN_DTE = 3
AGGRESSIVE_MAX_DTE = 21
AGGRESSIVE_TARGET_DTE = 10
AGGRESSIVE_ROLL_DTE_TRIGGER = 3

AGGRESSIVE_SPREAD_WIDTHS = [1.0, 2.5, 5.0]

# Relaxed liquidity - accept thinner markets for leverage
AGGRESSIVE_MIN_VOLUME = 1
AGGRESSIVE_MIN_OPEN_INTEREST = 5
AGGRESSIVE_MAX_BID_ASK_SPREAD_PCT = 0.75

AGGRESSIVE_MAX_POSITIONS_PER_THESIS = 3
AGGRESSIVE_MAX_TOTAL_POSITIONS = 9

# === Profit-taking ===
PROFIT_TAKE_PCT = 0.50           # close at 50% of max profit
AGGRESSIVE_PROFIT_TAKE_PCT = 0.30  # faster exit in aggressive mode

# === Momentum detection ===
MOMENTUM_THRESHOLD = 0.03       # 3% move triggers momentum signal
MOMENTUM_LOOKBACK_DAYS = 5      # over 5 trading days
MOMENTUM_STRONG_THRESHOLD = 0.07  # 7% = strong momentum, concentrate

# Yahoo Finance API base URL
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
YAHOO_OPTIONS_URL = "https://query1.finance.yahoo.com/v7/finance/options/{ticker}"

# Cache TTLs (seconds)
PRICE_CACHE_TTL = 3600       # 1 hour
OPTIONS_CACHE_TTL = 900      # 15 minutes

DISCLAIMER = (
    "Automated trading system. Not financial advice. "
    "Options involve risk of total loss of invested capital."
)
