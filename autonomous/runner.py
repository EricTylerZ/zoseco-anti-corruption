"""
Autonomous trading runner.

CLI interface for all trading operations:
  --check      Check account and open positions
  --scan       Scan for best trades
  --execute    Execute best trades (use --dry-run to preview)
  --roll       Check and suggest rolls for expiring positions
  --summary    Portfolio P&L summary
  --momentum   Show momentum signals for all tickers
  --cascade    Check for system-wide cascade (all theses moving)
  --aggressive Use aggressive mode (weekly options, momentum-driven)

Usage:
  python -m autonomous.runner --scan
  python -m autonomous.runner --scan --aggressive
  python -m autonomous.runner --momentum
  python -m autonomous.runner --cascade
  python -m autonomous.runner --execute --dry-run --aggressive
"""

import argparse
import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from config.theses import THESES, TOTAL_CAPITAL, ALL_TICKERS
from config.settings import DISCLAIMER


def _get_redis():
    """Get Redis client if REDIS_URL is set."""
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        print("Warning: REDIS_URL not set. Running without persistence.")
        return None
    try:
        import redis
        return redis.from_url(redis_url)
    except Exception as e:
        print(f"Warning: Could not connect to Redis: {e}")
        return None


def cmd_check():
    """Check account status and positions."""
    print("=" * 60)
    print("ACCOUNT CHECK")
    print("=" * 60)

    # Check Alpaca connection
    try:
        from broker.alpaca_client import get_account, get_positions, get_orders
        account = get_account()
        print(f"\nAlpaca Account: {account['id']}")
        print(f"  Status: {account['status']}")
        print(f"  Cash: ${account['cash']:.2f}")
        print(f"  Buying Power: ${account['buying_power']:.2f}")
        print(f"  Portfolio Value: ${account['portfolio_value']:.2f}")

        positions = get_positions()
        print(f"\nOpen Positions ({len(positions)}):")
        for p in positions:
            print(f"  {p['symbol']}: {p['qty']} @ ${p['current_price']:.2f}")
            print(f"    P&L: ${p['unrealized_pl']:.2f} ({p['unrealized_plpc']*100:.1f}%)")

        orders = get_orders("open")
        if orders:
            print(f"\nOpen Orders ({len(orders)}):")
            for o in orders:
                print(f"  {o['order_id'][:8]}... {o['side']} {o['symbol']} x{o['qty']}")

    except Exception as e:
        print(f"\nAlpaca not configured: {e}")
        print("Set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env")

    # Check market data
    print("\nMarket Data Check:")
    from data.market_data import get_price
    redis_client = _get_redis()
    for ticker in ALL_TICKERS:
        price = get_price(ticker, redis_client)
        status = f"${price:.2f}" if price else "FAILED"
        print(f"  {ticker}: {status}")

    print(f"\n{DISCLAIMER}")


def cmd_momentum():
    """Show momentum signals for all tickers."""
    from strategy.momentum import (
        scan_momentum, detect_cascade, get_dynamic_allocation,
        format_momentum_report,
    )
    redis_client = _get_redis()

    print("Scanning momentum across all tickers...")
    momentum_results = scan_momentum(redis_client)
    cascade_info = detect_cascade(momentum_results)
    dynamic_alloc = get_dynamic_allocation(momentum_results, cascade_info)
    print(format_momentum_report(momentum_results, cascade_info, dynamic_alloc))
    print(f"\n{DISCLAIMER}")
    return momentum_results, cascade_info, dynamic_alloc


def cmd_cascade():
    """Check for system-wide cascade."""
    from strategy.momentum import scan_momentum, detect_cascade
    redis_client = _get_redis()

    print("Checking for cascade conditions...")
    momentum_results = scan_momentum(redis_client)
    cascade_info = detect_cascade(momentum_results)

    print("=" * 60)
    print("CASCADE DETECTION")
    print("=" * 60)

    if cascade_info["cascade"]:
        print("\n*** CASCADE MODE ACTIVE ***")
        print(f"Active theses: {', '.join(cascade_info['active_theses'])}")
        print(f"Strong theses: {', '.join(cascade_info['strong_theses'])}")
    print(f"\n{cascade_info['reason']}")
    print(f"Recommended mode: {cascade_info['recommended_mode'].upper()}")
    print(f"\n{DISCLAIMER}")
    return cascade_info


def cmd_scan(aggressive: bool = False):
    """Scan for best trades."""
    from strategy.scanner import scan_all, format_scan_results

    redis_client = _get_redis()
    allocation_override = None

    if aggressive:
        # Use momentum-driven allocation in aggressive mode
        from strategy.momentum import scan_momentum, detect_cascade, get_dynamic_allocation
        print("Aggressive mode: scanning momentum for dynamic allocation...")
        momentum_results = scan_momentum(redis_client)
        cascade_info = detect_cascade(momentum_results)
        allocation_override = get_dynamic_allocation(momentum_results, cascade_info)

        if cascade_info["cascade"]:
            print("*** CASCADE DETECTED - concentrating capital ***")
        print()

    results = scan_all(
        TOTAL_CAPITAL, redis_client,
        aggressive=aggressive,
        allocation_override=allocation_override,
    )
    mode = "AGGRESSIVE" if aggressive else "CONSERVATIVE"
    print(f"Mode: {mode}")
    print(format_scan_results(results))
    print(f"\n{DISCLAIMER}")
    return results


def cmd_execute(dry_run: bool = True, aggressive: bool = False):
    """Execute best trades."""
    from strategy.scanner import scan_all
    from strategy.portfolio import Portfolio
    from broker.executor import execute_best_trades

    redis_client = _get_redis()
    portfolio = Portfolio(redis_client)
    allocation_override = None

    if aggressive:
        from strategy.momentum import scan_momentum, detect_cascade, get_dynamic_allocation
        momentum_results = scan_momentum(redis_client)
        cascade_info = detect_cascade(momentum_results)
        allocation_override = get_dynamic_allocation(momentum_results, cascade_info)

    print("Scanning for trades...")
    scan_results = scan_all(
        TOTAL_CAPITAL, redis_client,
        aggressive=aggressive,
        allocation_override=allocation_override,
    )

    mode = "DRY RUN" if dry_run else "LIVE"
    print(f"\n{'='*60}")
    print(f"TRADE EXECUTION ({mode})")
    print(f"{'='*60}")

    results = execute_best_trades(scan_results, portfolio, dry_run=dry_run)

    for r in results:
        thesis_name = THESES.get(r.get("thesis_id", ""), {}).get("name", "Unknown")
        print(f"\n{thesis_name}:")

        if r["success"]:
            if dry_run:
                trade = r.get("trade", {})
                print(f"  WOULD EXECUTE: {trade.get('ticker', '?')} {trade.get('spread_type', '?')}")
                print(f"  Cost: ${trade.get('net_debit', 0):.2f}")
                print(f"  Max profit: ${trade.get('max_profit', 0):.2f}")
            else:
                print(f"  EXECUTED: Position {r.get('position_id', '?')}")
                print(f"  Order: {r.get('order', {}).get('order_id', '?')}")
        else:
            print(f"  SKIPPED: {r.get('reason', 'Unknown reason')}")

    if dry_run:
        print(f"\nThis was a dry run. Use --execute without --dry-run to place real orders.")

    print(f"\n{DISCLAIMER}")


def cmd_roll(aggressive: bool = False):
    """Check for positions needing to be rolled and profit-taking opportunities."""
    from strategy.portfolio import Portfolio
    from strategy.roller import (
        find_positions_to_roll, suggest_rolls, format_roll_suggestions,
        find_positions_to_take_profit, format_profit_take_suggestions,
    )

    redis_client = _get_redis()
    portfolio = Portfolio(redis_client)

    # Check profit-taking first
    profit_suggestions = find_positions_to_take_profit(portfolio, aggressive=aggressive)
    if profit_suggestions:
        print(format_profit_take_suggestions(profit_suggestions))
        print()

    # Then check rolls
    to_roll = find_positions_to_roll(portfolio)
    if not to_roll and not profit_suggestions:
        print("No positions need rolling or profit-taking at this time.")
        return

    if to_roll:
        suggestions = suggest_rolls(to_roll, portfolio, redis_client)
        print(format_roll_suggestions(suggestions))
    print(f"\n{DISCLAIMER}")


def cmd_summary():
    """Show portfolio summary."""
    from strategy.portfolio import Portfolio

    redis_client = _get_redis()
    portfolio = Portfolio(redis_client)
    print(portfolio.format_summary())
    print(f"\n{DISCLAIMER}")


def cmd_advisor(args):
    """Run an advisor tool."""
    from strategy.advisor import (
        iv_environment, csp_strike_finder, theta_decay_optimizer,
        covered_call_timing, wheel_tracker, leap_checklist,
        position_size_stress, earnings_risk_screen, strategy_decision,
        leap_tax_timer, portfolio_correlation_audit, pre_trade_exit_plan,
        list_advisors, ADVISOR_NAMES,
    )

    tool_num = args.advisor
    if tool_num < 1 or tool_num > 12:
        print(list_advisors())
        return

    redis_client = _get_redis()
    ticker = getattr(args, "ticker", None)

    print(f"Running Advisor #{tool_num}: {ADVISOR_NAMES[tool_num]}")
    print()

    if tool_num == 1:
        if not ticker:
            print("ERROR: --ticker required for IV Environment Scanner")
            return
        print(iv_environment(ticker, redis_client))

    elif tool_num == 2:
        if not ticker:
            print("ERROR: --ticker required for CSP Strike Finder")
            return
        print(csp_strike_finder(ticker, redis_client))

    elif tool_num == 3:
        if not ticker:
            print("ERROR: --ticker required for Theta Decay Optimizer")
            return
        premium = getattr(args, "premium", None)
        if premium is None:
            print("ERROR: --premium required for Theta Decay Optimizer")
            return
        dte = getattr(args, "dte", 30) or 30
        opt_type = "put" if getattr(args, "put", False) else "call"
        print(theta_decay_optimizer(ticker, opt_type, premium, dte, redis_client))

    elif tool_num == 4:
        if not ticker:
            print("ERROR: --ticker required for Covered Call Timing")
            return
        cost_basis = getattr(args, "cost_basis", None)
        if cost_basis is None:
            print("ERROR: --cost-basis required for Covered Call Timing")
            return
        print(covered_call_timing(ticker, cost_basis, redis_client))

    elif tool_num == 5:
        if not ticker:
            print("ERROR: --ticker required for Wheel Tracker")
            return
        cycles_json = getattr(args, "cycles", None)
        if not cycles_json:
            print("ERROR: --cycles required (JSON array)")
            print('Example: --cycles \'[{"type":"csp","strike":50,"premium":1.50,"assigned":true}]\'')
            return
        try:
            cycles = json.loads(cycles_json)
        except json.JSONDecodeError:
            print("ERROR: --cycles must be valid JSON")
            return
        print(wheel_tracker(ticker, cycles, redis_client))

    elif tool_num == 6:
        if not ticker:
            print("ERROR: --ticker required for LEAP Checklist")
            return
        thesis = getattr(args, "thesis", None) or "No thesis provided"
        print(leap_checklist(ticker, thesis, redis_client))

    elif tool_num == 7:
        if not ticker:
            print("ERROR: --ticker required for Position Sizing")
            return
        capital = getattr(args, "capital", None)
        if capital is None:
            print("ERROR: --capital required for Position Sizing Stress Test")
            return
        positions_json = getattr(args, "positions", None)
        existing = json.loads(positions_json) if positions_json else None
        print(position_size_stress(ticker, capital, existing, redis_client))

    elif tool_num == 8:
        if not ticker:
            print("ERROR: --ticker required for Earnings Risk Screen")
            return
        earnings_date = getattr(args, "earnings_date", None)
        if not earnings_date:
            print("ERROR: --earnings-date required (YYYY-MM-DD)")
            return
        position_info = {}
        if getattr(args, "strategy_type", None):
            position_info["strategy"] = args.strategy_type
        if getattr(args, "strike", None):
            position_info["strike"] = args.strike
        if getattr(args, "premium", None):
            position_info["premium"] = args.premium
        print(earnings_risk_screen(ticker, earnings_date, position_info or None, redis_client))

    elif tool_num == 9:
        if not ticker:
            print("ERROR: --ticker required for Strategy Decision")
            return
        conviction = getattr(args, "conviction", None) or "moderate"
        capital = getattr(args, "capital", None)
        if capital is None:
            print("ERROR: --capital required for Strategy Decision")
            return
        print(strategy_decision(ticker, conviction, capital, redis_client))

    elif tool_num == 10:
        if not ticker:
            print("ERROR: --ticker required for LEAP Tax Timer")
            return
        open_date = getattr(args, "open_date", None)
        gain = getattr(args, "gain", None)
        tax_bracket = getattr(args, "tax_bracket", None)
        if not all([open_date, gain is not None, tax_bracket is not None]):
            print("ERROR: --open-date, --gain, and --tax-bracket all required")
            return
        print(leap_tax_timer(ticker, open_date, gain, tax_bracket, redis_client))

    elif tool_num == 11:
        positions_json = getattr(args, "positions", None)
        if not positions_json:
            print("ERROR: --positions required (JSON array)")
            print('Example: --positions \'[{"ticker":"AAPL","allocation_pct":20}]\'')
            return
        try:
            positions = json.loads(positions_json)
        except json.JSONDecodeError:
            print("ERROR: --positions must be valid JSON")
            return
        print(portfolio_correlation_audit(positions))

    elif tool_num == 12:
        if not ticker:
            print("ERROR: --ticker required for Pre-Trade Exit Plan")
            return
        strategy_type = getattr(args, "strategy_type", None)
        strike = getattr(args, "strike", None)
        expiration = getattr(args, "expiration", None)
        premium = getattr(args, "premium", None)
        if not all([strategy_type, strike, expiration, premium]):
            print("ERROR: --strategy, --strike, --expiration, --premium all required")
            return
        print(pre_trade_exit_plan(ticker, strategy_type, strike, expiration, premium, redis_client))

    print(f"\n{DISCLAIMER}")


def main():
    parser = argparse.ArgumentParser(
        description="Financial Strategy Autonomous Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m autonomous.runner --check                     Check account and prices
  python -m autonomous.runner --scan                      Scan for opportunities
  python -m autonomous.runner --scan --aggressive         Aggressive scan (weeklies)
  python -m autonomous.runner --momentum                  Show momentum signals
  python -m autonomous.runner --cascade                   Check cascade conditions
  python -m autonomous.runner --execute --dry-run         Preview trades
  python -m autonomous.runner --execute --aggressive      Execute aggressive trades
  python -m autonomous.runner --roll                      Check/suggest rolls
  python -m autonomous.runner --roll --aggressive         Roll with profit-taking
  python -m autonomous.runner --summary                   Portfolio P&L
  python -m autonomous.runner --advisor 0                  List all advisor tools
  python -m autonomous.runner --advisor 1 --ticker AAPL    IV Environment Scanner
  python -m autonomous.runner --advisor 2 --ticker TSN     CSP Strike Finder
  python -m autonomous.runner --advisor 9 --ticker AAPL --conviction high --capital 5000
        """,
    )

    parser.add_argument("--check", action="store_true", help="Check account and market data")
    parser.add_argument("--scan", action="store_true", help="Scan for best trades")
    parser.add_argument("--execute", action="store_true", help="Execute best trades")
    parser.add_argument("--roll", action="store_true", help="Check and suggest position rolls")
    parser.add_argument("--summary", action="store_true", help="Show portfolio summary")
    parser.add_argument("--momentum", action="store_true", help="Show momentum signals for all tickers")
    parser.add_argument("--cascade", action="store_true", help="Check for system-wide cascade")
    parser.add_argument("--dry-run", action="store_true", help="Preview trades without executing")
    parser.add_argument("-a", "--aggressive", action="store_true",
                        help="Use aggressive mode (weekly options, momentum-driven)")

    # Advisor tools (1-12)
    parser.add_argument("--advisor", type=int, metavar="N",
                        help="Run advisor tool N (1-12). Use --advisor 0 to list all tools")
    parser.add_argument("--ticker", type=str, help="Target ticker symbol")
    parser.add_argument("--premium", type=float, help="Premium collected (advisor 3, 8, 12)")
    parser.add_argument("--cost-basis", type=float, dest="cost_basis",
                        help="Cost basis per share (advisor 4)")
    parser.add_argument("--dte", type=int, help="Days to expiration (advisor 3)")
    parser.add_argument("--put", action="store_true", help="Put option (advisor 3)")
    parser.add_argument("--call", action="store_true", help="Call option (advisor 3)")
    parser.add_argument("--cycles", type=str, help="Wheel cycles JSON (advisor 5)")
    parser.add_argument("--thesis", type=str, help="Investment thesis (advisor 6)")
    parser.add_argument("--capital", type=float, help="Available capital (advisor 7, 9)")
    parser.add_argument("--positions", type=str, help="Portfolio positions JSON (advisor 7, 11)")
    parser.add_argument("--earnings-date", type=str, dest="earnings_date",
                        help="Earnings date YYYY-MM-DD (advisor 8)")
    parser.add_argument("--conviction", type=str, help="Conviction level: moderate/high/very_high (advisor 9)")
    parser.add_argument("--open-date", type=str, dest="open_date",
                        help="Position open date YYYY-MM-DD (advisor 10)")
    parser.add_argument("--gain", type=float, help="Unrealized gain amount (advisor 10)")
    parser.add_argument("--tax-bracket", type=float, dest="tax_bracket",
                        help="Tax bracket percentage (advisor 10)")
    parser.add_argument("--strategy", type=str, dest="strategy_type",
                        help="Strategy type: csp/cc/leap (advisor 12)")
    parser.add_argument("--strike", type=float, help="Strike price (advisor 12)")
    parser.add_argument("--expiration", type=str, help="Expiration date YYYY-MM-DD (advisor 12)")

    args = parser.parse_args()

    commands = [args.check, args.scan, args.execute, args.roll,
                args.summary, args.momentum, args.cascade,
                args.advisor is not None]
    if not any(commands):
        parser.print_help()
        return

    mode = "AGGRESSIVE" if args.aggressive else "CONSERVATIVE"
    print(f"Financial Strategy Runner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Capital: ${TOTAL_CAPITAL:.2f} | Mode: {mode}")
    print()

    if args.check:
        cmd_check()
    if args.momentum:
        cmd_momentum()
    if args.cascade:
        cmd_cascade()
    if args.scan:
        cmd_scan(aggressive=args.aggressive)
    if args.execute:
        cmd_execute(dry_run=args.dry_run, aggressive=args.aggressive)
    if args.roll:
        cmd_roll(aggressive=args.aggressive)
    if args.summary:
        cmd_summary()
    if args.advisor is not None:
        cmd_advisor(args)


if __name__ == "__main__":
    main()
