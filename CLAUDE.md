# Zoseco Financial Strategy System

This is a live options trading system with $100 capital, built alongside the anti-corruption chatbot.

## Three Market Theses (treated as facts, timing unknown)
1. **Beef imports surge** - Overseas beef will flood the US market
2. **Monetary system collapse** - USD/monetary system will weaken significantly
3. **NYC housing drop** - New York real estate prices will decline

## Quick Commands
- Check positions: `python -m autonomous.runner --check`
- Run scanner: `python -m autonomous.runner --scan`
- Execute trades: `python -m autonomous.runner --execute`
- View P&L: `python -m autonomous.runner --summary`
- Roll expiring: `python -m autonomous.runner --roll`

## Strategy Rules
- Only debit spreads (capped risk, no margin needed)
- Auto-roll at 21 DTE if thesis hasn't triggered
- Never exceed $100 total capital deployed
- Target tickers: TSN, DBA (beef), UUP, SLV, GDX (dollar), VNO, SLG (NYC housing)

## When to Update Strategy
- If a thesis triggers (prices move significantly), take profits
- If new information changes a thesis, update config/theses.py
- If budget allows after rolls/profits, add new positions
- Always verify with --scan before --execute
- Update strategy/journal.md after every action

## Project Structure
- `config/` - Strategy configuration (theses, settings)
- `core/` - Data models and options math
- `data/` - Market data fetching (Yahoo Finance)
- `broker/` - Alpaca API integration
- `strategy/` - Scanner, portfolio tracking, rolling logic
- `autonomous/` - CLI runner for all operations
- `tests/` - Unit tests

## Testing
```bash
python -m pytest tests/ -v
```
