"""
Market thesis definitions and ticker mappings.

Three events treated as certainties with unknown timing:
1. Beef imports surge into the US
2. Monetary system / USD collapse
3. NYC housing market drops
"""

THESES = {
    "beef_imports": {
        "name": "Beef Import Surge",
        "direction": "bearish",
        "description": (
            "Overseas beef imports will flood the US market, "
            "hurting domestic cattle prices and rancher profitability"
        ),
        "tickers": {
            "TSN": {
                "name": "Tyson Foods",
                "direction": "bearish",
                "reason": "Largest US meat processor - domestic pricing pressure",
                "weight": 0.6,
            },
            "DBA": {
                "name": "Invesco DB Agriculture Fund",
                "direction": "bearish",
                "reason": "Broad agriculture ETF with livestock exposure",
                "weight": 0.4,
            },
        },
        "allocation_pct": 0.25,
    },
    "dollar_collapse": {
        "name": "Monetary System Collapse",
        "direction": "bearish_usd",
        "description": (
            "The US dollar and monetary system will weaken significantly. "
            "Precious metals and hard assets rise as dollar falls."
        ),
        "tickers": {
            "UUP": {
                "name": "Invesco DB US Dollar Index Bullish Fund",
                "direction": "bearish",
                "reason": "Direct dollar index tracking - buy puts to short USD",
                "weight": 0.40,
            },
            "SLV": {
                "name": "iShares Silver Trust",
                "direction": "bullish",
                "reason": "Silver rises when dollar collapses - buy calls",
                "weight": 0.30,
            },
            "GDX": {
                "name": "VanEck Gold Miners ETF",
                "direction": "bullish",
                "reason": "Gold miners profit when gold rises on dollar weakness",
                "weight": 0.20,
            },
            "UVXY": {
                "name": "ProShares Ultra VIX Short-Term Futures",
                "direction": "bullish",
                "reason": "2x leveraged VIX - spikes 5-10x in systemic crisis",
                "weight": 0.15,
            },
            "TLT": {
                "name": "iShares 20+ Year Treasury Bond ETF",
                "direction": "bearish",
                "reason": "Long bonds collapse if rates spike during monetary crisis",
                "weight": 0.05,
            },
        },
        "allocation_pct": 0.45,
    },
    "nyc_housing": {
        "name": "NYC Housing Drop",
        "direction": "bearish",
        "description": (
            "New York City real estate prices will decline significantly. "
            "NYC-concentrated REITs will be hit hardest."
        ),
        "tickers": {
            "VNO": {
                "name": "Vornado Realty Trust",
                "direction": "bearish",
                "reason": "Major NYC-concentrated REIT, office and retail",
                "weight": 0.50,
            },
            "SLG": {
                "name": "SL Green Realty",
                "direction": "bearish",
                "reason": "NYC's largest office landlord",
                "weight": 0.50,
            },
        },
        "allocation_pct": 0.30,
    },
}

TOTAL_CAPITAL = 100.00

# All tickers we track across all theses
ALL_TICKERS = []
for thesis in THESES.values():
    for ticker in thesis["tickers"]:
        if ticker not in ALL_TICKERS:
            ALL_TICKERS.append(ticker)
