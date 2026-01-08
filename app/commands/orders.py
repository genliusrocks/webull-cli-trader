import logging
import sys
from datetime import datetime, timezone

from app.adapter import WebullApiAdapter, WebullApiError
from app.utils import (
    filter_orders_by_date,
    filter_orders_by_status,
    parse_utc_date,
    print_orders,
)

logger = logging.getLogger(__name__)


def handle_orders(api: WebullApiAdapter, status: str, date_str: str | None):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        date_note = ""
        if status != "open":
            query_date = date_str or datetime.now(timezone.utc).strftime("%y%m%d")
            date_note = f", 日期: {query_date} (UTC)"
        logger.info("正在查询账户 %s 的订单 (模式: %s%s)...", account_id, status, date_note)

        if hasattr(client, "order_v2"):
            try:
                res = None

                if status == "open":
                    if hasattr(client.order_v2, "get_order_open"):
                        res = client.order_v2.get_order_open(account_id)
                    else:
                        logger.error("错误: 找不到 get_order_open 方法")
                else:
                    if hasattr(client.order_v2, "get_order_history_request"):
                        res = client.order_v2.get_order_history_request(account_id)
                    else:
                        logger.error("错误: 找不到 get_order_history_request 方法")

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
                    logger.error("查询失败: %s %s", res.status_code, res.text)

            except Exception as exc:
                logger.exception("V2 接口调用出错: %s", exc)
        else:
            logger.error("错误: client 对象没有 order_v2 属性。")

    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except Exception as exc:
        logger.exception("执行出错: %s", exc)
        sys.exit(1)
