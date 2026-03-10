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

## Advisor Tools (1-12)
Interactive analysis tools for options strategy decisions:
- IV scan: `python -m autonomous.runner --advisor 1 --ticker AAPL`
- CSP strike finder: `python -m autonomous.runner --advisor 2 --ticker TSN`
- Theta decay: `python -m autonomous.runner --advisor 3 --ticker AAPL --premium 2.50 --dte 30 --put`
- Covered call timing: `python -m autonomous.runner --advisor 4 --ticker AAPL --cost-basis 150`
- Wheel tracker: `python -m autonomous.runner --advisor 5 --ticker AAPL --cycles '[{"type":"csp","strike":50,"premium":1.50,"assigned":true}]'`
- LEAP checklist: `python -m autonomous.runner --advisor 6 --ticker AAPL --thesis "AI growth"`
- Position sizing: `python -m autonomous.runner --advisor 7 --ticker AAPL --capital 50000`
- Earnings risk: `python -m autonomous.runner --advisor 8 --ticker AAPL --earnings-date 2026-04-15`
- Strategy decision: `python -m autonomous.runner --advisor 9 --ticker AAPL --conviction high --capital 5000`
- LEAP tax timer: `python -m autonomous.runner --advisor 10 --ticker AAPL --open-date 2025-03-15 --gain 500 --tax-bracket 24`
- Correlation audit: `python -m autonomous.runner --advisor 11 --positions '[{"ticker":"AAPL","allocation_pct":20},{"ticker":"MSFT","allocation_pct":15}]'`
- Exit plan: `python -m autonomous.runner --advisor 12 --ticker AAPL --strategy csp --strike 150 --expiration 2026-04-17 --premium 3.20`
- List all: `python -m autonomous.runner --advisor 0`

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
- `strategy/` - Scanner, portfolio tracking, rolling logic, advisor tools
- `autonomous/` - CLI runner for all operations
- `tests/` - Unit tests

## Testing
```bash
python -m pytest tests/ -v
```
