"""
Autonomous trading runner.

CLI interface for all trading operations:
  --check    Check account and open positions
  --scan     Scan for best trades
  --execute  Execute best trades (use --dry-run to preview)
  --roll     Check and suggest rolls for expiring positions
  --summary  Portfolio P&L summary

Usage:
  python -m autonomous.runner --scan
  python -m autonomous.runner --execute --dry-run
  python -m autonomous.runner --roll
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


def cmd_scan():
    """Scan for best trades."""
    from strategy.scanner import scan_all, format_scan_results
    redis_client = _get_redis()
    results = scan_all(TOTAL_CAPITAL, redis_client)
    print(format_scan_results(results))
    print(f"\n{DISCLAIMER}")
    return results


def cmd_execute(dry_run: bool = True):
    """Execute best trades."""
    from strategy.scanner import scan_all
    from strategy.portfolio import Portfolio
    from broker.executor import execute_best_trades

    redis_client = _get_redis()
    portfolio = Portfolio(redis_client)

    print("Scanning for trades...")
    scan_results = scan_all(TOTAL_CAPITAL, redis_client)

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


def cmd_roll():
    """Check for positions needing to be rolled."""
    from strategy.portfolio import Portfolio
    from strategy.roller import find_positions_to_roll, suggest_rolls, format_roll_suggestions

    redis_client = _get_redis()
    portfolio = Portfolio(redis_client)

    to_roll = find_positions_to_roll(portfolio)
    if not to_roll:
        print("No positions need rolling at this time.")
        return

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


def main():
    parser = argparse.ArgumentParser(
        description="Financial Strategy Autonomous Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m autonomous.runner --check              Check account and prices
  python -m autonomous.runner --scan               Scan for opportunities
  python -m autonomous.runner --execute --dry-run   Preview trades
  python -m autonomous.runner --execute             Execute trades (LIVE)
  python -m autonomous.runner --roll               Check/suggest rolls
  python -m autonomous.runner --summary            Portfolio P&L
        """,
    )

    parser.add_argument("--check", action="store_true", help="Check account and market data")
    parser.add_argument("--scan", action="store_true", help="Scan for best trades")
    parser.add_argument("--execute", action="store_true", help="Execute best trades")
    parser.add_argument("--roll", action="store_true", help="Check and suggest position rolls")
    parser.add_argument("--summary", action="store_true", help="Show portfolio summary")
    parser.add_argument("--dry-run", action="store_true", help="Preview trades without executing")

    args = parser.parse_args()

    if not any([args.check, args.scan, args.execute, args.roll, args.summary]):
        parser.print_help()
        return

    print(f"Financial Strategy Runner - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Capital: ${TOTAL_CAPITAL:.2f}")
    print()

    if args.check:
        cmd_check()
    if args.scan:
        cmd_scan()
    if args.execute:
        cmd_execute(dry_run=args.dry_run)
    if args.roll:
        cmd_roll()
    if args.summary:
        cmd_summary()


if __name__ == "__main__":
    main()
