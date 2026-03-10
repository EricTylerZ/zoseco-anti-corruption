"""
Data models for the financial strategy system.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json
import uuid
from datetime import datetime


@dataclass
class OptionLeg:
    """A single leg of an options trade."""
    ticker: str
    option_type: str          # "put" or "call"
    strike: float
    expiration: str           # ISO date string YYYY-MM-DD
    action: str               # "buy" or "sell"
    premium: float            # per-share premium
    quantity: int = 1         # number of contracts

    @property
    def total_cost(self) -> float:
        """Total cost/credit for this leg (per contract = 100 shares)."""
        multiplier = -1 if self.action == "buy" else 1
        return multiplier * self.premium * 100 * self.quantity

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OptionLeg":
        return cls(**data)


@dataclass
class SpreadTrade:
    """A debit spread trade (2 legs)."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    thesis_id: str = ""
    ticker: str = ""
    legs: List[OptionLeg] = field(default_factory=list)
    spread_type: str = ""     # "put_debit_spread" or "call_debit_spread"
    net_debit: float = 0.0    # what you pay (max loss)
    max_profit: float = 0.0
    breakeven: float = 0.0
    risk_reward: float = 0.0
    entry_date: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "planned"   # "planned", "open", "closed", "rolled", "expired"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["legs"] = [leg.to_dict() if isinstance(leg, OptionLeg) else leg for leg in self.legs]
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "SpreadTrade":
        legs = [OptionLeg.from_dict(l) if isinstance(l, dict) else l for l in data.pop("legs", [])]
        return cls(legs=legs, **data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> "SpreadTrade":
        return cls.from_dict(json.loads(s))


@dataclass
class Position:
    """A live position tracked in the portfolio."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    trade: Optional[SpreadTrade] = None
    entry_cost: float = 0.0       # actual fill (net debit paid)
    current_value: float = 0.0    # mark-to-market value
    pnl: float = 0.0
    pnl_pct: float = 0.0
    opened_at: str = field(default_factory=lambda: datetime.now().isoformat())
    closed_at: Optional[str] = None
    close_value: Optional[float] = None
    notes: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        if self.trade:
            d["trade"] = self.trade.to_dict() if isinstance(self.trade, SpreadTrade) else self.trade
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Position":
        trade_data = data.pop("trade", None)
        trade = SpreadTrade.from_dict(trade_data) if isinstance(trade_data, dict) else trade_data
        return cls(trade=trade, **data)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, s: str) -> "Position":
        return cls.from_dict(json.loads(s))


@dataclass
class ScanResult:
    """A recommended trade from the scanner."""
    thesis_id: str
    thesis_name: str
    ticker: str
    spread_type: str
    long_strike: float
    short_strike: float
    expiration: str
    net_debit: float        # cost per contract (100 shares)
    max_profit: float
    breakeven: float
    risk_reward: float
    current_price: float
    dte: int
    direction: str          # "bearish" or "bullish"

    def to_dict(self) -> dict:
        return asdict(self)
