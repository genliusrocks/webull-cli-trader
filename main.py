import argparse
import logging
import sys
import os
from dataclasses import dataclass

# 复用你现有的模块
from app.config import load_config
from app.adapter import WebullApiAdapter
from app.commands import account, orders, trade


def parse_log_level(value: str) -> str:
    level_name = value.upper()
    if level_name not in logging._nameToLevel:
        raise argparse.ArgumentTypeError(
            f"Invalid log level '{value}'. Use one of: {', '.join(logging._nameToLevel.keys())}"
        )
    return level_name


def configure_logging(level_name: str) -> None:
    level = logging._nameToLevel[level_name]
    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(level)
        for handler in root_logger.handlers:
            handler.setLevel(level)
        return
    logging.basicConfig(level=level)

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    parser.add_argument(
        "--log-level",
        default=os.getenv("WEBULL_LOG_LEVEL", "WARNING"),
        type=parse_log_level,
        help="Logging level (e.g. DEBUG, INFO, WARNING, ERROR). Can also set WEBULL_LOG_LEVEL.",
    )
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # --- Account 命令 ---
    account_parser = subparsers.add_parser('account', help='Account management')
    account_parser.add_argument('action', choices=['list', 'balance', 'positions'], help='Action')
    
    # --- Token 命令 ---
    token_parser = subparsers.add_parser('token', help='Manage Token')
    token_parser.add_argument('--export', action='store_true', help='Print export command')

    # --- Orders 命令 ---
    orders_parser = subparsers.add_parser('orders', help='List orders')
    orders_parser.add_argument('status', nargs='?', choices=['open', 'executed', 'all'], default='open')
    orders_parser.add_argument('--date', help='Orders date (yymmdd)')

    # --- Review 命令 (新增) ---
    review_parser = subparsers.add_parser('review', help='Review trades on a chart')
    review_parser.add_argument('symbol', help='Stock Symbol (e.g. TSLA)')
    review_parser.add_argument('--date', required=True, help='Date to review (yymmdd), e.g. 260122')

    # --- Buy 命令 ---
    buy_parser = subparsers.add_parser('buy', help='Place a BUY order')
    buy_parser.add_argument('symbol', help='Symbol (e.g. AAPL)')
    buy_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    buy_parser.add_argument('quantity', type=int, help='Quantity')
    buy_parser.add_argument('price', nargs='?', type=float, help='Price (for Limit)')
    buy_parser.add_argument('--aux', type=float, help='Aux Price (for Stop)')

    # --- Sell 命令 (平多仓) ---
    sell_parser = subparsers.add_parser('sell', help='Place a SELL order (Close Position)')
    sell_parser.add_argument('symbol', help='Symbol')
    sell_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    sell_parser.add_argument('quantity', type=int, help='Quantity')
    sell_parser.add_argument('price', nargs='?', type=float, help='Price')
    sell_parser.add_argument('--aux', type=float, help='Aux Price')

    # --- Short 命令 (开空仓) ---
    short_parser = subparsers.add_parser('short', help='Place a SHORT SELL order')
    short_parser.add_argument('symbol', help='Symbol')
    short_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    short_parser.add_argument('quantity', type=int, help='Quantity')
    short_parser.add_argument('price', nargs='?', type=float, help='Price')
    short_parser.add_argument('--aux', type=float, help='Aux Price')

    # --- Cancel 命令 ---
    cancel_parser = subparsers.add_parser('cancel', help='Cancel an order')
    cancel_parser.add_argument('order_id', help='Order ID to cancel')

    args = parser.parse_args()

    configure_logging(args.log_level)

    # 加载配置
    try:
        config = load_config()
        api = WebullApiAdapter(config)
    except Exception as e:
        print(f"初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    # --- 命令分发 ---
    if args.command == 'account':
        if args.action == 'list':
            account.handle_account_list(api)
        elif args.action == 'balance':
            account.handle_account_balance(api)
        elif args.action == 'positions':
            account.handle_account_positions(api)
            
    elif args.command == 'token':
        from app.commands import token 
        if args.export:
            token_path = "conf/token.txt"
            if os.path.exists(token_path):
                with open(token_path) as f:
                    print(f"export WEBULL_ACCESS_TOKEN='{f.read().strip()}'")
            else:
                print("Token file not found.", file=sys.stderr)

    elif args.command == 'orders':
        orders.handle_orders(api, args.status, args.date)
        
    elif args.command == 'review':
        # 动态导入 review 模块
        from app.commands import review
        review.handle_review(api, args.symbol, args.date)
    
    elif args.command == 'buy':
        trade.handle_trade(api, 'BUY', args)
        
    elif args.command == 'sell':
        trade.handle_trade(api, 'SELL', args)
        
    elif args.command == 'short':
        trade.handle_trade(api, 'SHORT', args)
        
    elif args.command == 'cancel':
        trade.handle_cancel(api, args.order_id)

if __name__ == "__main__":
    main()
