import json
import logging
import sys

from app.adapter import WebullApiAdapter, WebullApiError
from app.utils import print_positions

logger = logging.getLogger(__name__)


def handle_account_list(api: WebullApiAdapter):
    try:
        client = api.get_trade_client()
        res = client.account_v2.get_account_list()
        if res.status_code == 200:
            logger.info("Successfully retrieved account list:")
            logger.info("%s", json.dumps(res.json(), indent=4))
        else:
            logger.error("Failed. Status Code: %s", res.status_code)
            logger.error("%s", res.text)
    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except Exception as exc:
        logger.exception("Error: %s", exc)
        sys.exit(1)


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
        logger.info("发现 %s 个账户，开始查询余额...\n", len(account_list))
        for acct in account_list:
            account_id = acct.get("account_id")
            if not account_id:
                continue
            logger.info("--- 账户 ID: %s ---", account_id)
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
                    logger.info("%s: %s", f"{k:<15}", v)
            else:
                logger.error("获取余额失败: %s", bal_res.text)
            logger.info("%s", "-" * 50)
    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except Exception as exc:
        logger.exception("执行出错: %s", exc)
        sys.exit(1)


def handle_account_positions(api: WebullApiAdapter):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        logger.info("正在查询账户 %s 的持仓...", account_id)
        res = client.account_v2.get_account_position(account_id)
        if res.status_code == 200:
            positions = api.extract_list_from_response(res.json())
            print_positions(positions)
        else:
            logger.error("获取持仓失败: %s", res.status_code)
            logger.error("%s", res.text)
    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except Exception as exc:
        logger.exception("执行出错: %s", exc)
        sys.exit(1)
