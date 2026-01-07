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
        # 常见包裹字段 data, items, orders
        return json_data.get('data') or json_data.get('items') or json_data.get('orders') or []
    return []

# ================= 辅助打印功能 (修复版) =================

def print_orders(orders_list):
    """格式化打印订单列表 (支持嵌套解包)"""
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

        # === 核心修复: 解包嵌套结构 ===
        # 如果外层有 'orders' 列表且不为空，说明是 Combo 结构，取第一个作为主腿
        if 'orders' in order and isinstance(order['orders'], list) and len(order['orders']) > 0:
            detail = order['orders'][0]
            # 有些字段可能还在外层 (如 combo_id)，但主要信息在内层
        else:
            # 如果不是嵌套结构，直接用当前对象
            detail = order

        # 1. 解析 Symbol
        symbol = detail.get('symbol')
        if not symbol:
            ticker = detail.get('ticker')
            if ticker and isinstance(ticker, dict):
                symbol = ticker.get('symbol')
        if not symbol: symbol = 'N/A'

        # 2. 解析 Side
        side = detail.get('side') or detail.get('action') or 'N/A'

        # 3. 解析 Type
        order_type = detail.get('order_type') or detail.get('orderType') or 'N/A'
        
        # 4. 解析 Price
        # 优先显示限价，如果是市价单显示 MKT
        limit_price = detail.get('limit_price') or detail.get('lmtPrice')
        filled_price = detail.get('filled_price') or detail.get('avg_filled_price')
        
        if order_type == 'MARKET':
            price_display = "MKT"
        else:
            price_display = str(limit_price) if limit_price else "0.0"
        
        # 如果已成交，可以在价格旁标注成交价 (可选)
        # if filled_price and float(filled_price) > 0:
        #     price_display += f" ({filled_price})"

        # 5. 解析 Qty (兼容 total_quantity / quantity)
        total_qty = detail.get('total_quantity') or detail.get('quantity') or detail.get('totalQuantity') or 0
        filled_qty = detail.get('filled_quantity') or detail.get('filled_qty') or detail.get('filledQuantity') or 0
        qty_str = f"{filled_qty}/{total_qty}"
        
        # 6. 解析 Status
        status = detail.get('status') or detail.get('order_status') or 'Unknown'
        
        # 7. 解析 Time (兼容 place_time_at / place_time)
        time_str = detail.get('place_time_at') # 优先用带 at 的 ISO 格式
        if not time_str:
            time_str = detail.get('place_time') or detail.get('create_time') or ''
        
        # 简化 ISO 时间 (2026-01-07T17:03:25.616Z -> 2026-01-07 17:03:25)
        if 'T' in str(time_str):
            time_str = str(time_str).replace('T', ' ').split('.')[0]
        elif str(time_str).isdigit(): # 如果是毫秒时间戳
            try:
                time_str = datetime.fromtimestamp(int(time_str)/1000).strftime('%Y-%m-%d %H:%M:%S')
            except: pass

        # 8. Order ID
        order_id = detail.get('order_id') or order.get('client_order_id')

        print(f"{symbol:<8} {side:<5} {order_type:<8} {price_display:<10} {qty_str:<8} {status:<12} {time_str:<20} {order_id}")
    print("-" * 100)

# ================= 订单查询功能 =================

def handle_orders(status):
    """处理订单查询逻辑"""
    try:
        client = get_trade_client()
        account_id = get_first_account_id(client)
        print(f"正在查询账户 {account_id} 的订单 (模式: {status})...")

        if hasattr(client, 'order_v2'):
            try:
                res = None
                
                # 1. 查询 Open Orders
                if status == 'open':
                    if hasattr(client.order_v2, 'get_order_open'):
                        res = client.order_v2.get_order_open(account_id)
                    else:
                        print("错误: 找不到 get_order_open 方法")

                # 2. 查询 History / All
                else:
                    if hasattr(client.order_v2, 'get_order_history_request'):
                        res = client.order_v2.get_order_history_request(account_id)
                    else:
                        print("错误: 找不到 get_order_history_request 方法")

                if res and res.status_code == 200:
                    orders = extract_list_from_response(res.json())
                    
                    if status == 'executed':
                        # 深度过滤：因为解包逻辑在 print_orders 里，这里简单根据字符串过滤可能不准
                        # 所以先打印全部，或者需要在这里也实现解包逻辑。
                        # 为了简单，这里暂不过滤，让 print_orders 全部显示，用户肉眼看状态即可
                        # 或者只显示包含 Filled 状态的组合
                        pass
                    
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
                    "Net Liquidation Value": data.get('total_net_liquidation_value'),
                    "Total Market Value": data.get('total_market_value'),
                    "Cash": data.get('total_cash_balance'),
                    "Buying Power": buying_power,
                    "Unrealized P&L": data.get('total_unrealized_profit_loss'),
                    "Day P&L": data.get('total_day_profit_loss'),
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
