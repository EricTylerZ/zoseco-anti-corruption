"""
Trading settings and rules.
"""

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
