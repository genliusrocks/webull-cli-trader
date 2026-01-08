import argparse
import functools
import logging

from app.adapter import WebullApiAdapter
from app.commands.account import (
    handle_account_balance,
    handle_account_list,
    handle_account_positions,
)
from app.commands.orders import handle_orders
from app.commands.trade import handle_trade
from app.config import load_config


def add_trade_subparser(subparsers: argparse._SubParsersAction, name: str) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=name.capitalize())
    parser.add_argument("symbol")
    parser.add_argument("order_type", choices=["limit", "market", "stop"])
    parser.add_argument("quantity", type=int)
    parser.add_argument("price", nargs="?", type=float)
    parser.add_argument("--aux", type=float)
    return parser


def handle_account(api: WebullApiAdapter, args: argparse.Namespace) -> None:
    if args.action == "list":
        handle_account_list(api)
    elif args.action == "balance":
        handle_account_balance(api)
    elif args.action == "positions":
        handle_account_positions(api)


def handle_orders_command(api: WebullApiAdapter, args: argparse.Namespace) -> None:
    handle_orders(api, args.status, args.date)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("webull").setLevel(logging.WARNING)
    api = WebullApiAdapter(load_config())
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest="command", required=True)

    account_parser = subparsers.add_parser("account", help="Account")
    account_parser.add_argument("action", choices=["list", "balance", "positions"])
    account_parser.set_defaults(handler=functools.partial(handle_account, api))

    orders_parser = subparsers.add_parser("orders", help="Orders")
    orders_parser.add_argument("status", nargs="?", choices=["open", "executed", "all"], default="open")
    orders_parser.add_argument(
        "--date", help="Orders date in yymmdd (UTC). Default: today when status is executed/all."
    )
    orders_parser.set_defaults(handler=functools.partial(handle_orders_command, api))

    buy_parser = add_trade_subparser(subparsers, "buy")
    buy_parser.set_defaults(handler=functools.partial(handle_trade, api, "BUY"))

    sell_parser = add_trade_subparser(subparsers, "sell")
    sell_parser.set_defaults(handler=functools.partial(handle_trade, api, "SELL"))

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
