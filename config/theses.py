"""
Market thesis definitions and ticker mappings.

Three events treated as certainties with unknown timing:
1. Beef imports surge into the US
2. Monetary system / USD collapse
3. NYC housing market drops

Expanded ticker universe: scanner scans ALL tickers but only allocates
budget to the best deals found (ranked by risk/reward ratio).
Weights are used as tie-breakers, not budget pre-splits.
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
            # --- Major Meat Processors (bearish - pricing pressure) ---
            "TSN": {
                "name": "Tyson Foods",
                "direction": "bearish",
                "reason": "Largest US meat processor - domestic pricing pressure",
                "weight": 0.20,
            },
            "PPC": {
                "name": "Pilgrim's Pride",
                "direction": "bearish",
                "reason": "Major US chicken/meat processor, pricing pressure from cheap imports",
                "weight": 0.15,
            },
            "BRFS": {
                "name": "BRF S.A.",
                "direction": "bullish",
                "reason": "Brazilian meat giant - benefits from exporting to US",
                "weight": 0.15,
            },
            # --- Agriculture ETFs ---
            "DBA": {
                "name": "Invesco DB Agriculture Fund",
                "direction": "bearish",
                "reason": "Broad agriculture ETF with livestock exposure",
                "weight": 0.10,
            },
            "COW": {
                "name": "iPath Series B Bloomberg Livestock ETN",
                "direction": "bearish",
                "reason": "Direct livestock commodity exposure - cattle futures",
                "weight": 0.15,
            },
            "MOO": {
                "name": "VanEck Agribusiness ETF",
                "direction": "bearish",
                "reason": "Agribusiness ETF with meat/livestock company exposure",
                "weight": 0.10,
            },
            # --- Smaller/Regional Processors ---
            "CALM": {
                "name": "Cal-Maine Foods",
                "direction": "bearish",
                "reason": "Largest US egg producer - protein pricing pressure",
                "weight": 0.15,
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
            # --- Direct Dollar Short ---
            "UUP": {
                "name": "Invesco DB US Dollar Index Bullish Fund",
                "direction": "bearish",
                "reason": "Direct dollar index tracking - buy puts to short USD",
                "weight": 0.12,
            },
            "UDN": {
                "name": "Invesco DB US Dollar Index Bearish Fund",
                "direction": "bullish",
                "reason": "Inverse dollar ETF - rises as USD falls",
                "weight": 0.08,
            },
            # --- Precious Metals (bullish - safe haven) ---
            "SLV": {
                "name": "iShares Silver Trust",
                "direction": "bullish",
                "reason": "Silver rises when dollar collapses",
                "weight": 0.10,
            },
            "GDX": {
                "name": "VanEck Gold Miners ETF",
                "direction": "bullish",
                "reason": "Gold miners profit when gold rises on dollar weakness",
                "weight": 0.10,
            },
            "GDXJ": {
                "name": "VanEck Junior Gold Miners ETF",
                "direction": "bullish",
                "reason": "Junior gold miners - more leverage to gold price moves",
                "weight": 0.08,
            },
            "GLD": {
                "name": "SPDR Gold Shares",
                "direction": "bullish",
                "reason": "Direct gold exposure - primary safe haven",
                "weight": 0.05,
            },
            "SILJ": {
                "name": "ETFMG Prime Junior Silver Miners ETF",
                "direction": "bullish",
                "reason": "Junior silver miners - high leverage to silver price",
                "weight": 0.05,
            },
            # --- Volatility / Crisis ---
            "UVXY": {
                "name": "ProShares Ultra VIX Short-Term Futures",
                "direction": "bullish",
                "reason": "2x leveraged VIX - spikes 5-10x in systemic crisis",
                "weight": 0.10,
            },
            "VXX": {
                "name": "iPath Series B S&P 500 VIX Short-Term Futures ETN",
                "direction": "bullish",
                "reason": "1x VIX exposure - cheaper entry for crisis spike",
                "weight": 0.05,
            },
            # --- Interest Rates / Bonds ---
            "TLT": {
                "name": "iShares 20+ Year Treasury Bond ETF",
                "direction": "bearish",
                "reason": "Long bonds collapse if rates spike during monetary crisis",
                "weight": 0.05,
            },
            "TBT": {
                "name": "ProShares UltraShort 20+ Year Treasury",
                "direction": "bullish",
                "reason": "2x inverse long bonds - profits from rate spikes",
                "weight": 0.05,
            },
            # --- Financials (bearish - crisis hits banks) ---
            "XLF": {
                "name": "Financial Select Sector SPDR Fund",
                "direction": "bearish",
                "reason": "Financial sector ETF - banks hammered in monetary crisis",
                "weight": 0.05,
            },
            "KRE": {
                "name": "SPDR S&P Regional Banking ETF",
                "direction": "bearish",
                "reason": "Regional banks most vulnerable to monetary crisis",
                "weight": 0.07,
            },
            # --- Crypto-adjacent (bullish - alternative to fiat) ---
            "BITO": {
                "name": "ProShares Bitcoin Strategy ETF",
                "direction": "bullish",
                "reason": "Bitcoin futures ETF - alternative monetary system play",
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
            # --- NYC-Concentrated REITs ---
            "VNO": {
                "name": "Vornado Realty Trust",
                "direction": "bearish",
                "reason": "Major NYC-concentrated REIT, office and retail",
                "weight": 0.15,
            },
            "SLG": {
                "name": "SL Green Realty",
                "direction": "bearish",
                "reason": "NYC's largest office landlord",
                "weight": 0.15,
            },
            "BXP": {
                "name": "BXP Inc (formerly Boston Properties)",
                "direction": "bearish",
                "reason": "Major office REIT with significant NYC exposure",
                "weight": 0.10,
            },
            "PGRE": {
                "name": "Paramount Group",
                "direction": "bearish",
                "reason": "NYC and SF focused Class A office REIT",
                "weight": 0.10,
            },
            # --- Broader Real Estate ETFs ---
            "IYR": {
                "name": "iShares U.S. Real Estate ETF",
                "direction": "bearish",
                "reason": "Broad US real estate ETF - NYC downturn drags sector",
                "weight": 0.08,
            },
            "XLRE": {
                "name": "Real Estate Select Sector SPDR Fund",
                "direction": "bearish",
                "reason": "Real estate sector ETF with major REIT holdings",
                "weight": 0.07,
            },
            "REM": {
                "name": "iShares Mortgage Real Estate ETF",
                "direction": "bearish",
                "reason": "Mortgage REITs - leveraged to real estate decline",
                "weight": 0.10,
            },
            # --- Homebuilders (indirect NYC exposure) ---
            "XHB": {
                "name": "SPDR S&P Homebuilders ETF",
                "direction": "bearish",
                "reason": "Homebuilder ETF - NYC decline signals broader weakness",
                "weight": 0.05,
            },
            # --- NYC-Exposed Companies ---
            "DBRG": {
                "name": "DigitalBridge Group",
                "direction": "bearish",
                "reason": "Digital infrastructure REIT, NYC-area exposure",
                "weight": 0.05,
            },
            "NYC": {
                "name": "New York Mortgage Trust",
                "direction": "bearish",
                "reason": "NYC-focused mortgage REIT - direct housing market exposure",
                "weight": 0.10,
            },
            "ABR": {
                "name": "Arbor Realty Trust",
                "direction": "bearish",
                "reason": "NYC-area multifamily lending - exposed to housing decline",
                "weight": 0.05,
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
