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
    # 兼容处理：有时账户列表在 'data' 字段中
    if isinstance(data, dict):
        account_list = data.get('data', [])
    else:
        account_list = data

    if not account_list:
        print("未找到有效账户。")
        sys.exit(1)
        
    # 优先寻找 account_id
    first_acct = account_list[0]
    acct_id = first_acct.get('account_id') or first_acct.get('secAccountId')
    return str(acct_id)

# ================= 辅助打印功能 =================

def print_orders(orders_list):
    """格式化打印订单列表"""
    if not orders_list:
        print(">>> 没有找到订单。")
        return

    # 再次确保传入的是列表
    if not isinstance(orders_list, list):
        print(f"错误: 订单数据格式不正确 (期望 List, 实际 {type(orders_list)})")
        print(f"原始数据: {orders_list}")
        return

    # 表头
    header = f"{'Symbol':<8} {'Side':<5} {'Type':<8} {'Price':<10} {'Qty':<8} {'Status':<12} {'Time (UTC)':<20} {'Order ID'}"
    print("-" * 100)
    print(header)
    print("-" * 100)

    for order in orders_list:
        # 防御性编程: 如果列表里混入了字符串，跳过
        if not isinstance(order, dict):
            continue

        symbol = order.get('symbol', 'N/A')
        side = order.get('side', 'N/A')
        order_type = order.get('order_type', 'N/A')
        
        # 价格显示
        price = order.get('limit_price') or order.get('price')
        if order_type == 'MARKET':
            price = "MKT"
        elif not price and order.get('avg_filled_price'):
            price = order.get('avg_filled_price')
        
        qty = f"{order.get('filled_qty', 0)}/{order.get('quantity', 0)}" # 显示 成交/总数
        status = order.get('status') or order.get('order_status', 'Unknown')
        
        # 时间处理
        time_str = order.get('place_time') or order.get('create_time') or order.get('update_time', '')
        if 'T' in time_str:
            time_str = time_str.replace('T', ' ').split('.')[0]

        order_id = order.get('order_id') or order.get('client_order_id')

        print(f"{symbol:<8} {side:<5} {order_type:<8} {str(price):<10} {qty:<8} {status:<12} {time_str:<20} {order_id}")
    print("-" * 100)

def extract_list_from_response(json_data):
    """通用工具：从响应中提取列表数据"""
    if isinstance(json_data, list):
        return json_data
    elif isinstance(json_data, dict):
        # 常见包裹字段
        return json_data.get('data') or json_data.get('items') or []
    return []

# ================= 订单查询功能 =================

def handle_orders(status):
    """处理订单查询逻辑"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        print(f"正在查询账户 {account_id} 的订单 (模式: {status})...")

        orders = []
        
        try:
            # 1. 尝试使用 V2 接口
            if status == 'open':
                res = client.order_v2.list_open_orders(account_id, page_size=50)
            else: # executed or all
                res = client.order_v2.list_today_orders(account_id, page_size=100)

            if res.status_code == 200:
                orders = extract_list_from_response(res.json())
            else:
                print(f"V2 查询失败: {res.status_code} {res.text}")
                # 只有 V2 失败且不是 404/500 时才考虑 fallback，这里简单起见让它继续尝试 fallback
                # 但通常如果 V2 存在，就不应该 fallback。这里保留 fallback 是为了兼容你的旧版 SDK
                raise AttributeError("Force fallback if needed") 

        except (AttributeError, Exception):
            # 2. Fallback 到旧版接口 (client.order)
            print("提示: 尝试使用 client.order (Legacy) 接口...")
            try:
                if status == 'open':
                    res = client.order.list_open_orders(account_id)
                else:
                    res = client.order.list_today_orders(account_id)
                
                if res.status_code == 200:
                    # === 关键修复点：解析数据结构 ===
                    orders = extract_list_from_response(res.json())
                else:
                    print(f"查询失败: {res.text}")
                    return
            except Exception as e_legacy:
                print(f"接口调用完全失败: {e_legacy}")
                return

        # 3. 如果是 'executed' 模式，在本地过滤
        if status == 'executed':
            orders = [o for o in orders if o.get('status') in ['Filled', 'Partial Filled']]

        print_orders(orders)

    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)

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

# ================= 下单交易功能 =================

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

# ================= 主入口 =================

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # Account
    account_parser = subparsers.add_parser('account', help='Account management')
    account_parser.add_argument('action', choices=['list', 'balance', 'positions'], help='Action')

    # Orders
    orders_parser = subparsers.add_parser('orders', help='List orders')
    orders_parser.add_argument('status', nargs='?', choices=['open', 'executed', 'all'], default='open', help='Order status')

    # Buy
    buy_parser = subparsers.add_parser('buy', help='Place a BUY order')
    buy_parser.add_argument('symbol', help='Stock Symbol')
    buy_parser.add_argument('order_type', choices=['limit', 'market', 'stop'], help='Order Type')
    buy_parser.add_argument('quantity', type=int, help='Quantity')
    buy_parser.add_argument('price', nargs='?', type=float, help='Limit Price')
    buy_parser.add_argument('--aux', type=float, help='Stop Price')

    # Sell
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
            
    elif args.command == 'orders':
        handle_orders(args.status)
    
    elif args.command == 'buy':
        handle_trade('BUY', args)
        
    elif args.command == 'sell':
        handle_trade('SELL', args)

if __name__ == "__main__":
    main()