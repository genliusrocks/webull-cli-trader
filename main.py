import argparse
import json
import sys
import os
import uuid

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

# ================= 配置区域 =================
YOUR_APP_KEY = os.getenv("WEBULL_APP_KEY")
YOUR_APP_SECRET = os.getenv("WEBULL_APP_SECRET")
REGION_ID = "us"
API_ENDPOINT = "api.webull.com" 
# ===========================================

def get_trade_client():
    """初始化并返回 TradeClient"""
    if not YOUR_APP_KEY or not YOUR_APP_SECRET:
        print("错误: 未找到环境变量 WEBULL_APP_KEY 或 WEBULL_APP_SECRET。", file=sys.stderr)
        sys.exit(1)

    api_client = ApiClient(YOUR_APP_KEY, YOUR_APP_SECRET, REGION_ID)
    api_client.add_endpoint(REGION_ID, API_ENDPOINT)
    return TradeClient(api_client)

def get_first_account_id(client):
    """辅助函数：获取第一个有效账户ID"""
    list_res = client.account_v2.get_account_list()
    if list_res.status_code != 200:
        print(f"无法获取账户列表: {list_res.text}")
        sys.exit(1)
    
    account_list = list_res.json()
    if not account_list:
        print("未找到有效账户。")
        sys.exit(1)
        
    # 优先寻找 account_id
    first_acct = account_list[0]
    acct_id = first_acct.get('account_id') or first_acct.get('secAccountId')
    return str(acct_id)

# ================= 账户查询功能 =================

def handle_account_list():
    try:
        client = get_trade_client()
        res = client.account_v2.get_account_list()
        if res.status_code == 200:
            print("Successfully retrieved account list:")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f"Failed. Status Code: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

def handle_account_balance():
    try:
        client = get_trade_client()
        list_res = client.account_v2.get_account_list()
        if list_res.status_code != 200: return

        account_list = list_res.json()
        if not account_list: return

        print(f"发现 {len(account_list)} 个账户，开始查询余额...\n")

        for acct in account_list:
            account_id = acct.get('account_id')
            if not account_id: continue

            print(f"--- 账户 ID: {account_id} ---")
            bal_res = client.account_v2.get_account_balance(account_id)
            
            if bal_res.status_code == 200:
                data = bal_res.json()
                buying_power = "N/A"
                assets_list = data.get('account_currency_assets')
                if assets_list and isinstance(assets_list, list) and len(assets_list) > 0:
                    buying_power = assets_list[0].get('day_buying_power') or assets_list[0].get('buying_power')

                summary = {
                    "净资产": data.get('total_net_liquidation_value'),
                    "总市值": data.get('total_market_value'),
                    "现金": data.get('total_cash_balance'),
                    "购买力": buying_power,
                    "浮盈": data.get('total_unrealized_profit_loss'),
                    "当日盈亏": data.get('total_day_profit_loss')
                }
                for k, v in summary.items():
                    print(f"{k:<15}: {v}")
            else:
                print(f"获取余额失败: {bal_res.text}")
            print("-" * 50)
    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)

def handle_account_positions():
    """获取并打印持仓"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        
        print(f"正在查询账户 {account_id} 的持仓...")
        res = client.account_v2.get_account_position(account_id)
        
        if res.status_code == 200:
            positions = res.json()
            if not positions:
                print("当前无持仓。")
                return
            
            header = f"{'Symbol':<10} {'Qty':<10} {'Last Price':<12} {'Mkt Value':<12} {'Cost':<10} {'Unrealized P&L':<15}"
            print(header)
            print("-" * len(header))

            for pos in positions:
                ticker = pos.get('ticker', {})
                symbol = ticker.get('symbol') or pos.get('symbol') or "Unknown"
                qty = pos.get('position') or pos.get('quantity') or "0"
                last = pos.get('last_price') or pos.get('lastPrice') or "0.00"
                mkt_val = pos.get('market_value') or pos.get('marketValue') or "0.00"
                cost = pos.get('cost') or pos.get('costPrice') or "0.00"
                pnl = pos.get('unrealized_profit_loss') or pos.get('unrealizedProfitLoss') or "0.00"
                
                print(f"{symbol:<10} {qty:<10} {last:<12} {mkt_val:<12} {cost:<10} {pnl:<15}")
        else:
            print(f"获取持仓失败: {res.status_code}")
            print(res.text)
            
    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)

# ================= 下单交易功能 =================

def handle_trade(side, args):
    """处理买卖下单逻辑"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        
        print(f"准备下单 - 账户 ID: {account_id}")

        # 参数校验
        order_type = args.order_type.upper()
        if order_type == 'LIMIT' and not args.price:
            print("错误: LIMIT 单必须提供价格 (例如: buy aapl limit 1 150.5)")
            return
        if order_type == 'STOP' and not args.aux:
            print("错误: STOP 单必须提供触发价 (使用 --aux 参数)")
            return

        # 构建订单 payload
        new_order = {
            "client_order_id": uuid.uuid4().hex,
            "combo_type": "NORMAL",         
            "symbol": args.symbol.upper(),
            "instrument_type": "EQUITY",
            "market": "US",
            "side": side.upper(),
            "order_type": order_type,
            "quantity": str(args.quantity),
            "time_in_force": "DAY",
            "entrust_type": "QTY",
            "account_tax_type": "GENERAL",
            "support_trading_session": "N"  # <--- 新增: 必须指定是否允许盘前盘后交易
        }

        if order_type == 'LIMIT':
            new_order["limit_price"] = str(args.price)
        elif order_type == 'STOP':
            new_order["aux_price"] = str(args.aux)

        # 必须包装为列表
        orders_list = [new_order]

        print(f"正在发送订单: {json.dumps(orders_list, indent=2)}")
        
        # 调用下单接口
        res = client.order_v2.place_order(account_id=account_id, new_orders=orders_list)
        
        if res.status_code == 200:
            print(">>> 下单成功!")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f">>> 下单失败: {res.status_code}")
            print(res.text)

    except Exception as e:
        print(f"交易出错: {e}", file=sys.stderr)

# ================= 主入口 =================

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    account_parser = subparsers.add_parser('account', help='Account management')
    account_parser.add_argument('action', choices=['list', 'balance', 'positions'], help='Action')

    buy_parser = subparsers.add_parser('buy', help='Place a BUY order')
    buy_parser.add_argument('symbol', help='Stock Symbol (e.g. AAPL)')
    buy_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    buy_parser.add_argument('quantity', type=int, help='Quantity')
    buy_parser.add_argument('price', nargs='?', type=float, help='Limit Price')
    buy_parser.add_argument('--aux', type=float, help='Stop Price')

    sell_parser = subparsers.add_parser('sell', help='Place a SELL order')
    sell_parser.add_argument('symbol', help='Stock Symbol')
    sell_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    sell_parser.add_argument('quantity', type=int, help='Quantity')
    sell_parser.add_argument('price', nargs='?', type=float, help='Limit Price')
    sell_parser.add_argument('--aux', type=float, help='Stop Price')

    args = parser.parse_args()

    if args.command == 'account':
        if args.action == 'list':
            handle_account_list()
        elif args.action == 'balance':
            handle_account_balance()
        elif args.action == 'positions':
            handle_account_positions()
    
    elif args.command == 'buy':
        handle_trade('BUY', args)
        
    elif args.command == 'sell':
        handle_trade('SELL', args)

if __name__ == "__main__":
    main()