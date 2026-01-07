import argparse
import json
import sys
import os
import uuid
from datetime import datetime

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
    
    data = list_res.json()
    if isinstance(data, dict):
        account_list = data.get('data', [])
    else:
        account_list = data

    if not account_list:
        print("未找到有效账户。")
        sys.exit(1)
        
    first_acct = account_list[0]
    acct_id = first_acct.get('account_id') or first_acct.get('secAccountId')
    return str(acct_id)

def extract_list_from_response(json_data):
    """通用工具：从响应中提取列表数据"""
    if isinstance(json_data, list):
        return json_data
    elif isinstance(json_data, dict):
        return json_data.get('data') or json_data.get('items') or []
    return []

# ================= 辅助打印功能 =================

def print_orders(orders_list):
    """格式化打印订单列表"""
    if not orders_list:
        print(">>> 当前没有订单。")
        return

    if not isinstance(orders_list, list):
        print(f"数据格式错误: {orders_list}")
        return

    # 表头
    header = f"{'Symbol':<8} {'Side':<5} {'Type':<8} {'Price':<10} {'Qty':<8} {'Status':<12} {'Time (UTC)':<20} {'Order ID'}"
    print("-" * 100)
    print(header)
    print("-" * 100)

    for order in orders_list:
        if not isinstance(order, dict): continue

        symbol = order.get('symbol', 'N/A')
        side = order.get('side', 'N/A')
        order_type = order.get('order_type', 'N/A')
        
        # 价格显示
        price = order.get('limit_price') or order.get('price')
        if order_type == 'MARKET':
            price = "MKT"
        elif not price and order.get('avg_filled_price'):
            price = order.get('avg_filled_price')
        
        qty = f"{order.get('filled_qty', 0)}/{order.get('quantity', 0)}"
        status = order.get('status') or order.get('order_status', 'Unknown')
        
        # 时间处理
        time_str = order.get('place_time') or order.get('create_time') or order.get('update_time', '')
        if 'T' in time_str:
            time_str = time_str.replace('T', ' ').split('.')[0]

        order_id = order.get('order_id') or order.get('client_order_id')

        print(f"{symbol:<8} {side:<5} {order_type:<8} {str(price):<10} {qty:<8} {status:<12} {time_str:<20} {order_id}")
    print("-" * 100)

# ================= 订单查询功能 =================

def handle_orders(status):
    """处理订单查询逻辑 (最终修复版)"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        print(f"正在查询账户 {account_id} 的订单 (模式: {status})...")

        orders = []
        
        # 使用确认存在的 V2 方法
        if hasattr(client, 'order_v2'):
            try:
                res = None
                
                # 1. 查询 Open Orders
                if status == 'open':
                    # 对应: get_order_open
                    if hasattr(client.order_v2, 'get_order_open'):
                        res = client.order_v2.get_order_open(account_id)
                    else:
                        print("错误: 找不到 get_order_open 方法")

                # 2. 查询 All / Executed
                else:
                    # 对应: get_order_history_request
                    # 注意: 这个名字通常包含今日订单
                    if hasattr(client.order_v2, 'get_order_history_request'):
                        res = client.order_v2.get_order_history_request(account_id)
                    else:
                        print("错误: 找不到 get_order_history_request 方法")

                if res and res.status_code == 200:
                    orders = extract_list_from_response(res.json())
                    
                    # 过滤逻辑
                    if status == 'executed':
                        # 过滤出已成交
                        orders = [o for o in orders if o.get('status') in ['Filled', 'Partial Filled']]
                    
                    print_orders(orders)
                    return
                elif res:
                    print(f"查询失败: {res.status_code} {res.text}")
                
            except Exception as e:
                print(f"V2 接口调用出错: {e}")
        else:
            print("错误: client 对象没有 order_v2 属性。")

    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)

# ================= 账户与交易功能 (保持不变) =================

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
        data = list_res.json()
        account_list = data.get('data') if isinstance(data, dict) else data
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
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        print(f"正在查询账户 {account_id} 的持仓...")
        res = client.account_v2.get_account_position(account_id)
        if res.status_code == 200:
            positions = extract_list_from_response(res.json())
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

def handle_trade(side, args):
    """处理买卖下单逻辑"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        print(f"准备下单 - 账户 ID: {account_id}")

        order_type = args.order_type.upper()
        if order_type == 'LIMIT' and not args.price:
            print("错误: LIMIT 单必须提供价格")
            return
        if order_type == 'STOP' and not args.aux:
            print("错误: STOP 单必须提供触发价 (使用 --aux 参数)")
            return

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
            "support_trading_session": "N"
        }

        if order_type == 'LIMIT':
            new_order["limit_price"] = str(args.price)
        elif order_type == 'STOP':
            new_order["aux_price"] = str(args.aux)

        res = client.order_v2.place_order(account_id=account_id, new_orders=[new_order])
        
        if res.status_code == 200:
            print(">>> 下单成功!")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f">>> 下单失败: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"交易出错: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    subparsers.add_parser('account', help='Account').add_argument('action', choices=['list', 'balance', 'positions'])
    
    orders_parser = subparsers.add_parser('orders', help='Orders')
    orders_parser.add_argument('status', nargs='?', choices=['open', 'executed', 'all'], default='open')

    buy_parser = subparsers.add_parser('buy', help='Buy')
    buy_parser.add_argument('symbol')
    buy_parser.add_argument('order_type', choices=['limit', 'market', 'stop'])
    buy_parser.add_argument('quantity', type=int)
    buy_parser.add_argument('price', nargs='?', type=float)
    buy_parser.add_argument('--aux', type=float)

    sell_parser = subparsers.add_parser('sell', help='Sell')
    sell_parser.add_argument('symbol')
    sell_parser.add_argument('order_type', choices=['limit', 'market', 'stop'])
    sell_parser.add_argument('quantity', type=int)
    sell_parser.add_argument('price', nargs='?', type=float)
    sell_parser.add_argument('--aux', type=float)

    args = parser.parse_args()

    if args.command == 'account':
        if args.action == 'list': handle_account_list()
        elif args.action == 'balance': handle_account_balance()
        elif args.action == 'positions': handle_account_positions()
    elif args.command == 'orders':
        handle_orders(args.status)
    elif args.command == 'buy':
        handle_trade('BUY', args)
    elif args.command == 'sell':
        handle_trade('SELL', args)

if __name__ == "__main__":
    main()


