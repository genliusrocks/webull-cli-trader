import json
import sys
import uuid

from app.adapter import WebullApiAdapter


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
