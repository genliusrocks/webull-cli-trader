import argparse

from app.adapter import WebullApiAdapter
from app.commands.account import (
    handle_account_balance,
    handle_account_list,
    handle_account_positions,
)
from app.commands.orders import handle_orders
from app.commands.trade import handle_trade
from app.config import load_config


def main():
    api = WebullApiAdapter(load_config())
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("account", help="Account").add_argument(
        "action", choices=["list", "balance", "positions"]
    )

    orders_parser = subparsers.add_parser("orders", help="Orders")
    orders_parser.add_argument("status", nargs="?", choices=["open", "executed", "all"], default="open")
    orders_parser.add_argument(
        "--date", help="Orders date in yymmdd (UTC). Default: today when status is executed/all."
    )

    buy_parser = subparsers.add_parser("buy", help="Buy")
    buy_parser.add_argument("symbol")
    buy_parser.add_argument("order_type", choices=["limit", "market", "stop"])
    buy_parser.add_argument("quantity", type=int)
    buy_parser.add_argument("price", nargs="?", type=float)
    buy_parser.add_argument("--aux", type=float)

    sell_parser = subparsers.add_parser("sell", help="Sell")
    sell_parser.add_argument("symbol")
    sell_parser.add_argument("order_type", choices=["limit", "market", "stop"])
    sell_parser.add_argument("quantity", type=int)
    sell_parser.add_argument("price", nargs="?", type=float)
    sell_parser.add_argument("--aux", type=float)

    args = parser.parse_args()

    if args.command == "account":
        if args.action == "list":
            handle_account_list(api)
        elif args.action == "balance":
            handle_account_balance(api)
        elif args.action == "positions":
            handle_account_positions(api)
    elif args.command == "orders":
        handle_orders(api, args.status, args.date)
    elif args.command == "buy":
        handle_trade(api, "BUY", args)
    elif args.command == "sell":
        handle_trade(api, "SELL", args)


if __name__ == "__main__":
    main()
