"""
Portfolio tracking and P&L calculation.
"""

import json
from typing import List, Dict, Optional
from datetime import datetime

from core.models import Position, SpreadTrade
from config.theses import THESES, TOTAL_CAPITAL


class Portfolio:
    """Manages positions and tracks P&L."""

    def __init__(self, redis_client=None, portfolio_id: str = "default"):
        self.redis = redis_client
        self.portfolio_id = portfolio_id
        self._positions_key = f"fin:positions:{portfolio_id}"
        self._trades_key = f"fin:trades:{portfolio_id}"
        self._meta_key = f"fin:portfolio:{portfolio_id}"

    def add_position(self, position: Position):
        """Add a new position to the portfolio."""
        if self.redis:
            self.redis.hset(
                self._positions_key,
                position.id,
                position.to_json(),
            )
            self.redis.rpush(
                self._trades_key,
                json.dumps({
                    "action": "open",
                    "position_id": position.id,
                    "timestamp": datetime.now().isoformat(),
                    "details": position.to_dict(),
                }),
            )

    def close_position(self, position_id: str, exit_value: float, notes: str = ""):
        """Close an open position."""
        position = self.get_position(position_id)
        if not position:
            return None

        position.closed_at = datetime.now().isoformat()
        position.close_value = exit_value
        position.pnl = exit_value - position.entry_cost
        position.pnl_pct = (position.pnl / position.entry_cost * 100) if position.entry_cost > 0 else 0
        position.notes = notes

        if position.trade:
            position.trade.status = "closed"

        if self.redis:
            self.redis.hset(
                self._positions_key,
                position.id,
                position.to_json(),
            )
            self.redis.rpush(
                self._trades_key,
                json.dumps({
                    "action": "close",
                    "position_id": position.id,
                    "timestamp": datetime.now().isoformat(),
                    "exit_value": exit_value,
                    "pnl": position.pnl,
                }),
            )

        return position

    def get_position(self, position_id: str) -> Optional[Position]:
        """Get a single position by ID."""
        if not self.redis:
            return None
        data = self.redis.hget(self._positions_key, position_id)
        if data:
            return Position.from_json(data.decode() if isinstance(data, bytes) else data)
        return None

    def get_all_positions(self) -> List[Position]:
        """Get all positions (open and closed)."""
        if not self.redis:
            return []
        all_data = self.redis.hgetall(self._positions_key)
        positions = []
        for pos_id, pos_json in all_data.items():
            pos_str = pos_json.decode() if isinstance(pos_json, bytes) else pos_json
            positions.append(Position.from_json(pos_str))
        return positions

    def get_open_positions(self) -> List[Position]:
        """Get only open positions."""
        return [p for p in self.get_all_positions() if p.closed_at is None]

    def get_closed_positions(self) -> List[Position]:
        """Get only closed positions."""
        return [p for p in self.get_all_positions() if p.closed_at is not None]

    def get_summary(self) -> Dict:
        """Get portfolio summary with P&L breakdown."""
        positions = self.get_all_positions()
        open_positions = [p for p in positions if p.closed_at is None]
        closed_positions = [p for p in positions if p.closed_at is not None]

        total_deployed = sum(p.entry_cost for p in open_positions)
        total_realized_pnl = sum(p.pnl for p in closed_positions)
        total_cost_basis = sum(p.entry_cost for p in positions)

        # Per-thesis breakdown
        thesis_breakdown = {}
        for thesis_id in THESES:
            thesis_positions = [
                p for p in positions
                if p.trade and p.trade.thesis_id == thesis_id
            ]
            thesis_open = [p for p in thesis_positions if p.closed_at is None]
            thesis_closed = [p for p in thesis_positions if p.closed_at is not None]

            thesis_breakdown[thesis_id] = {
                "name": THESES[thesis_id]["name"],
                "open_positions": len(thesis_open),
                "closed_positions": len(thesis_closed),
                "deployed": sum(p.entry_cost for p in thesis_open),
                "realized_pnl": sum(p.pnl for p in thesis_closed),
            }

        return {
            "total_capital": TOTAL_CAPITAL,
            "total_deployed": round(total_deployed, 2),
            "remaining_budget": round(TOTAL_CAPITAL - total_deployed, 2),
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "total_realized_pnl": round(total_realized_pnl, 2),
            "total_cost_basis": round(total_cost_basis, 2),
            "thesis_breakdown": thesis_breakdown,
            "as_of": datetime.now().isoformat(),
        }

    def format_summary(self) -> str:
        """Format portfolio summary as readable text."""
        s = self.get_summary()
        lines = []
        lines.append("=" * 60)
        lines.append("PORTFOLIO SUMMARY")
        lines.append(f"As of: {s['as_of'][:19]}")
        lines.append("=" * 60)
        lines.append(f"Total Capital:      ${s['total_capital']:.2f}")
        lines.append(f"Deployed:           ${s['total_deployed']:.2f}")
        lines.append(f"Remaining Budget:   ${s['remaining_budget']:.2f}")
        lines.append(f"Open Positions:     {s['open_positions']}")
        lines.append(f"Closed Positions:   {s['closed_positions']}")
        lines.append(f"Realized P&L:       ${s['total_realized_pnl']:.2f}")
        lines.append("")

        for thesis_id, tb in s["thesis_breakdown"].items():
            lines.append(f"  {tb['name']}:")
            lines.append(f"    Open: {tb['open_positions']} | Closed: {tb['closed_positions']}")
            lines.append(f"    Deployed: ${tb['deployed']:.2f} | Realized P&L: ${tb['realized_pnl']:.2f}")

        lines.append("=" * 60)
        return "\n".join(lines)
