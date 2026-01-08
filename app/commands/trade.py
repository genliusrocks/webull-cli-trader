import json
import logging
import sys
import uuid

from app.adapter import WebullApiAdapter, WebullApiError

logger = logging.getLogger(__name__)


def handle_trade(api: WebullApiAdapter, side: str, args):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        logger.info("准备下单 - 账户 ID: %s", account_id)

        order_type = args.order_type.upper()
        if order_type == "LIMIT" and not args.price:
            logger.error("错误: LIMIT 单必须提供价格")
            return
        if order_type == "STOP" and not args.aux:
            logger.error("错误: STOP 单必须提供触发价 (使用 --aux 参数)")
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
            logger.info(">>> 下单成功!")
            logger.info("%s", json.dumps(res.json(), indent=4))
        else:
            logger.error(">>> 下单失败: %s", res.status_code)
            logger.error("%s", res.text)
    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except Exception as exc:
        logger.exception("交易出错: %s", exc)
        sys.exit(1)
