import argparse
import sys
import os
from dataclasses import dataclass

# 复用你现有的模块
from app.config import load_config
from app.adapter import WebullApiAdapter
from app.commands import account, orders, trade

def main():
    # 加载配置
    try:
        config = load_config()
        api = WebullApiAdapter(config)
    except Exception as e:
        print(f"初始化失败: {e}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
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

    # --- [新增] Short 命令 (开空仓) ---
    short_parser = subparsers.add_parser('short', help='Place a SHORT SELL order')
    short_parser.add_argument('symbol', help='Symbol')
    short_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    short_parser.add_argument('quantity', type=int, help='Quantity')
    short_parser.add_argument('price', nargs='?', type=float, help='Price')
    short_parser.add_argument('--aux', type=float, help='Aux Price')

    # --- [新增] Cancel 命令 ---
    cancel_parser = subparsers.add_parser('cancel', help='Cancel an order')
    cancel_parser.add_argument('order_id', help='Order ID to cancel')

    args = parser.parse_args()

    # --- 命令分发 ---
    if args.command == 'account':
        if args.action == 'list':
            account.handle_account_list(api)
        elif args.action == 'balance':
            account.handle_account_balance(api)
        elif args.action == 'positions':
            account.handle_account_positions(api)
            
    elif args.command == 'token':
        from app.commands import token # 假设你有这个模块，或者直接在这里处理
        if args.export:
            # 简单的 token 导出逻辑
            token_path = "conf/token.txt"
            if os.path.exists(token_path):
                with open(token_path) as f:
                    print(f"export WEBULL_ACCESS_TOKEN='{f.read().strip()}'")
            else:
                print("Token file not found.", file=sys.stderr)

    elif args.command == 'orders':
        orders.handle_orders(api, args.status, args.date)
    
    elif args.command == 'buy':
        trade.handle_trade(api, 'BUY', args)
        
    elif args.command == 'sell':
        # Sell 仅用于平多仓
        trade.handle_trade(api, 'SELL', args)
        
    elif args.command == 'short':
        # 新增: Short 专门用于做空，传递 'SELL_SHORT' 给 API
        # 注意: 确保你的账户类型是 Margin 账户，且有足够的保证金
        trade.handle_trade(api, 'SHORT', args)
        
    elif args.command == 'cancel':
        # 调用刚刚在 trade.py 中添加的函数
        trade.handle_cancel(api, args.order_id)

if __name__ == "__main__":
    main()
