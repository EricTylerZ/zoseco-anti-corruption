# Zoseco Financial Strategy System

This is a live options trading system with $100 capital, built alongside the anti-corruption chatbot.

## Three Market Theses (treated as facts, timing unknown)
1. **Beef imports surge** - Overseas beef will flood the US market
2. **Monetary system collapse** - USD/monetary system will weaken significantly
3. **NYC housing drop** - New York real estate prices will decline

## Quick Commands
- Check positions: `python -m autonomous.runner --check`
- Run scanner: `python -m autonomous.runner --scan`
- Aggressive scan (weeklies): `python -m autonomous.runner --scan --aggressive`
- Momentum signals: `python -m autonomous.runner --momentum`
- Cascade detection: `python -m autonomous.runner --cascade`
- Execute trades: `python -m autonomous.runner --execute`
- Execute aggressive: `python -m autonomous.runner --execute --aggressive`
- View P&L: `python -m autonomous.runner --summary`
- Roll expiring: `python -m autonomous.runner --roll`
- Roll with profit-taking: `python -m autonomous.runner --roll --aggressive`

## Trading Modes
- **Conservative** (default): 30-90 DTE monthly options, strict liquidity, static allocation
- **Aggressive** (`-a`/`--aggressive`): 3-21 DTE weekly options, momentum-driven allocation, profit recycling at 30%

## Strategy Rules
- Only debit spreads (capped risk, no margin needed)
- Auto-roll at 21 DTE (conservative) or 3 DTE (aggressive)
- Never exceed $100 total capital deployed
- Target tickers (expanded universe, scanner picks best deals):
  - Beef: TSN, PPC, BRFS, DBA, COW, MOO, CALM
  - Dollar: UUP, UDN, SLV, GDX, GDXJ, GLD, SILJ, UVXY, VXX, TLT, TBT, XLF, KRE, BITO
  - NYC Housing: VNO, SLG, BXP, PGRE, IYR, XLRE, REM, XHB, DBRG, NYC, ABR
- Momentum engine dynamically shifts allocation toward hot theses
- Cascade mode: when all 3 theses show momentum, concentrate on fastest movers

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
