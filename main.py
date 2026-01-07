import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

# ================= 配置区域 =================


@dataclass(frozen=True)
class WebullConfig:
    app_key: str
    app_secret: str
    region_id: str = "us"
    api_endpoint: str = "api.webull.com"


def load_config() -> WebullConfig:
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    if not app_key or not app_secret:
        print("错误: 未找到环境变量 WEBULL_APP_KEY 或 WEBULL_APP_SECRET。", file=sys.stderr)
        sys.exit(1)
    return WebullConfig(app_key=app_key, app_secret=app_secret)


# ================= API 适配 =================


class WebullApiAdapter:
    def __init__(self, config: WebullConfig):
        self.config = config

    def get_trade_client(self) -> TradeClient:
        api_client = ApiClient(self.config.app_key, self.config.app_secret, self.config.region_id)
        api_client.add_endpoint(self.config.region_id, self.config.api_endpoint)
        return TradeClient(api_client)

    def get_first_account_id(self, client: TradeClient) -> str:
        list_res = client.account_v2.get_account_list()
        if list_res.status_code != 200:
            print(f"无法获取账户列表: {list_res.text}")
            sys.exit(1)

        data = list_res.json()
        if isinstance(data, dict):
            account_list = data.get("data", [])
        else:
            account_list = data

        if not account_list:
            print("未找到有效账户。")
            sys.exit(1)

        first_acct = account_list[0]
        acct_id = first_acct.get("account_id") or first_acct.get("secAccountId")
        return str(acct_id)

    @staticmethod
    def extract_list_from_response(json_data):
        if isinstance(json_data, list):
            return json_data
        if isinstance(json_data, dict):
            return json_data.get("data") or json_data.get("items") or json_data.get("orders") or []
        return []


# ================= 输出格式化 =================


def format_time(time_str) -> str:
    if "T" in str(time_str):
        return str(time_str).replace("T", " ").split(".")[0]
    if str(time_str).isdigit():
        try:
            return datetime.fromtimestamp(int(time_str) / 1000, tz=timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except ValueError:
            return str(time_str)
    return str(time_str)


def parse_utc_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%y%m%d").replace(tzinfo=timezone.utc).date()


def extract_order_time(detail: dict) -> datetime | None:
    time_value = detail.get("place_time_at") or detail.get("place_time") or detail.get("create_time")
    if time_value is None:
        return None
    time_str = str(time_value)
    if time_str.isdigit():
        try:
            return datetime.fromtimestamp(int(time_str) / 1000, tz=timezone.utc)
        except ValueError:
            return None
    if "T" in time_str:
        try:
            normalized = time_str.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def filter_orders_by_status(orders_list, status: str):
    if status != "executed":
        return orders_list
    allowed_statuses = {"filled", "partially_filled", "partiallyfilled"}
    filtered = []
    for order in orders_list:
        if not isinstance(order, dict):
            continue
        detail = order["orders"][0] if isinstance(order.get("orders"), list) and order["orders"] else order
        order_status = str(detail.get("status") or detail.get("order_status") or "").lower()
        if order_status.replace(" ", "_") in allowed_statuses:
            filtered.append(order)
    return filtered


def filter_orders_by_date(orders_list, target_date: date | None):
    if target_date is None:
        return orders_list
    filtered = []
    for order in orders_list:
        if not isinstance(order, dict):
            continue
        detail = order["orders"][0] if isinstance(order.get("orders"), list) and order["orders"] else order
        order_time = extract_order_time(detail)
        if order_time and order_time.date() == target_date:
            filtered.append(order)
    return filtered


def format_price(value, default="-") -> str:
    if value is None or value == "":
        return default
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def format_qty(value) -> str:
    if value is None or value == "":
        return "0"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(round(number)))


def format_fill_time(detail: dict) -> str:
    time_value = (
        detail.get("filled_time")
        or detail.get("filled_time_at")
        or detail.get("fill_time")
        or detail.get("filledTime")
        or detail.get("filledAt")
        or detail.get("execution_time")
        or detail.get("last_filled_time")
    )
    if not time_value:
        return "-"
    return format_time(time_value)


def print_orders(orders_list):
    if not orders_list:
        print(">>> 当前没有订单。")
        return

    if not isinstance(orders_list, list):
        print(f"数据格式错误: {orders_list}")
        return

    header = (
        f"{'Symbol':<8} {'Side':<5} {'Type':<8} {'Price':<10} {'Fill':<10} "
        f"{'Qty':<8} {'Status':<12} {'Time (UTC)':<20} {'Fill Time (UTC)':<20} {'Order ID'}"
    )
    print("-" * 130)
    print(header)
    print("-" * 130)

    for order in orders_list:
        if not isinstance(order, dict):
            continue

        detail = order["orders"][0] if isinstance(order.get("orders"), list) and order["orders"] else order

        symbol = detail.get("symbol")
        if not symbol:
            ticker = detail.get("ticker")
            if ticker and isinstance(ticker, dict):
                symbol = ticker.get("symbol")
        if not symbol:
            symbol = "N/A"

        side = detail.get("side") or detail.get("action") or "N/A"
        order_type = detail.get("order_type") or detail.get("orderType") or "N/A"
        limit_price = detail.get("limit_price") or detail.get("lmtPrice")

        if order_type == "MARKET":
            price_display = "MKT"
        else:
            price_display = format_price(limit_price, default="0.0")

        fill_price = (
            detail.get("filled_price")
            or detail.get("filledPrice")
            or detail.get("avg_filled_price")
            or detail.get("avgFilledPrice")
            or detail.get("avg_price")
            or detail.get("avgPrice")
            or detail.get("average_price")
            or detail.get("averagePrice")
            or detail.get("exec_price")
            or detail.get("executed_price")
        )
        fill_display = format_price(fill_price)

        total_qty = detail.get("total_quantity") or detail.get("quantity") or detail.get("totalQuantity") or 0
        filled_qty = (
            detail.get("filled_quantity") or detail.get("filled_qty") or detail.get("filledQuantity") or 0
        )
        qty_str = f"{format_qty(filled_qty)}/{format_qty(total_qty)}"

        status = detail.get("status") or detail.get("order_status") or "Unknown"
        time_str = detail.get("place_time_at") or detail.get("place_time") or detail.get("create_time") or ""
        time_str = format_time(time_str)
        fill_time_str = format_fill_time(detail)
        order_id = detail.get("order_id") or order.get("client_order_id")

        print(
            f"{symbol:<8} {side:<5} {order_type:<8} {price_display:<10} {fill_display:<10} "
            f"{qty_str:<8} {status:<12} {time_str:<20} {fill_time_str:<20} {order_id}"
        )
    print("-" * 130)


def print_positions(positions):
    if not positions:
        print("当前无持仓。")
        return
    header = (
        f"{'Symbol':<10} {'Qty':<10} {'Last Price':<12} {'Mkt Value':<12} "
        f"{'Cost':<10} {'Unrealized P&L':<15}"
    )
    print(header)
    print("-" * len(header))
    for pos in positions:
        ticker = pos.get("ticker", {})
        symbol = ticker.get("symbol") or pos.get("symbol") or "Unknown"
        qty = pos.get("position") or pos.get("quantity") or "0"
        last = pos.get("last_price") or pos.get("lastPrice") or "0.00"
        mkt_val = pos.get("market_value") or pos.get("marketValue") or "0.00"
        cost = pos.get("cost") or pos.get("costPrice") or "0.00"
        pnl = pos.get("unrealized_profit_loss") or pos.get("unrealizedProfitLoss") or "0.00"
        print(f"{symbol:<10} {qty:<10} {last:<12} {mkt_val:<12} {cost:<10} {pnl:<15}")


# ================= 命令处理 =================


def handle_orders(api: WebullApiAdapter, status: str, date_str: str | None):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        date_note = ""
        if status != "open":
            query_date = date_str or datetime.now(timezone.utc).strftime("%y%m%d")
            date_note = f", 日期: {query_date} (UTC)"
        print(f"正在查询账户 {account_id} 的订单 (模式: {status}{date_note})...")

        if hasattr(client, "order_v2"):
            try:
                res = None

                if status == "open":
                    if hasattr(client.order_v2, "get_order_open"):
                        res = client.order_v2.get_order_open(account_id)
                    else:
                        print("错误: 找不到 get_order_open 方法")
                else:
                    if hasattr(client.order_v2, "get_order_history_request"):
                        res = client.order_v2.get_order_history_request(account_id)
                    else:
                        print("错误: 找不到 get_order_history_request 方法")

                if res and res.status_code == 200:
                    orders = api.extract_list_from_response(res.json())
                    if status != "open":
                        if date_str is None:
                            target_date = datetime.now(timezone.utc).date()
                        else:
                            target_date = parse_utc_date(date_str)
                        orders = filter_orders_by_date(orders, target_date)
                    orders = filter_orders_by_status(orders, status)
                    print_orders(orders)
                    return

                if res:
                    print(f"查询失败: {res.status_code} {res.text}")

            except Exception as e:
                print(f"V2 接口调用出错: {e}")
        else:
            print("错误: client 对象没有 order_v2 属性。")

    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)


def handle_account_list(api: WebullApiAdapter):
    try:
        client = api.get_trade_client()
        res = client.account_v2.get_account_list()
        if res.status_code == 200:
            print("Successfully retrieved account list:")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f"Failed. Status Code: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)


def handle_account_balance(api: WebullApiAdapter):
    try:
        client = api.get_trade_client()
        list_res = client.account_v2.get_account_list()
        if list_res.status_code != 200:
            return
        data = list_res.json()
        account_list = data.get("data") if isinstance(data, dict) else data
        if not account_list:
            return
        print(f"发现 {len(account_list)} 个账户，开始查询余额...\n")
        for acct in account_list:
            account_id = acct.get("account_id")
            if not account_id:
                continue
            print(f"--- 账户 ID: {account_id} ---")
            bal_res = client.account_v2.get_account_balance(account_id)
            if bal_res.status_code == 200:
                data = bal_res.json()
                buying_power = "N/A"
                assets_list = data.get("account_currency_assets")
                if assets_list and isinstance(assets_list, list) and len(assets_list) > 0:
                    buying_power = assets_list[0].get("day_buying_power") or assets_list[0].get(
                        "buying_power"
                    )
                summary = {
                    "Net Liquidation Value": data.get("total_net_liquidation_value"),
                    "Total Market Value": data.get("total_market_value"),
                    "Cash": data.get("total_cash_balance"),
                    "Buying Power": buying_power,
                    "Unrealized P&L": data.get("total_unrealized_profit_loss"),
                    "Day P&L": data.get("total_day_profit_loss"),
                }
                for k, v in summary.items():
                    print(f"{k:<15}: {v}")
            else:
                print(f"获取余额失败: {bal_res.text}")
            print("-" * 50)
    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)


def handle_account_positions(api: WebullApiAdapter):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        print(f"正在查询账户 {account_id} 的持仓...")
        res = client.account_v2.get_account_position(account_id)
        if res.status_code == 200:
            positions = api.extract_list_from_response(res.json())
            print_positions(positions)
        else:
            print(f"获取持仓失败: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)


def handle_trade(api: WebullApiAdapter, side: str, args):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        print(f"准备下单 - 账户 ID: {account_id}")

        order_type = args.order_type.upper()
        if order_type == "LIMIT" and not args.price:
            print("错误: LIMIT 单必须提供价格")
            return
        if order_type == "STOP" and not args.aux:
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
            "support_trading_session": "N",
        }

        if order_type == "LIMIT":
            new_order["limit_price"] = str(args.price)
        elif order_type == "STOP":
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
    api = WebullApiAdapter(load_config())
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI Trader")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    subparsers.add_parser('account', help='Account').add_argument('action', choices=['list', 'balance', 'positions'])
    
    orders_parser = subparsers.add_parser('orders', help='Orders')
    orders_parser.add_argument('status', nargs='?', choices=['open', 'executed', 'all'], default='open')
    orders_parser.add_argument('--date', help='Orders date in yymmdd (UTC). Default: today when status is executed/all.')

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
        if args.action == 'list':
            handle_account_list(api)
        elif args.action == 'balance':
            handle_account_balance(api)
        elif args.action == 'positions':
            handle_account_positions(api)
    elif args.command == 'orders':
        handle_orders(api, args.status, args.date)
    elif args.command == 'buy':
        handle_trade(api, 'BUY', args)
    elif args.command == 'sell':
        handle_trade(api, 'SELL', args)

if __name__ == "__main__":
    main()
