from __future__ import annotations

from datetime import date, datetime, timezone


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


def format_time_only(time_value) -> str:
    formatted = format_time(time_value)
    if formatted == "-" or formatted == "":
        return formatted
    if " " in formatted:
        return formatted.split(" ", 1)[1]
    return formatted


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
    return format_time_only(time_value)


def print_orders(orders_list):
    if not orders_list:
        print(">>> 当前没有订单。")
        return

    if not isinstance(orders_list, list):
        print(f"数据格式错误: {orders_list}")
        return

    header = (
        f"{'Symbol':<8} {'Side':<5} {'Type':<8} {'Price':<10} {'Fill':<10} "
        f"{'Qty':<8} {'Status':<12} {'Time (UTC)':<10} {'Fill Time (UTC)':<10} {'Order ID'}"
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
        time_str = format_time_only(time_str)
        fill_time_str = format_fill_time(detail)
        order_id = detail.get("order_id") or order.get("client_order_id")

        print(
            f"{symbol:<8} {side:<5} {order_type:<8} {price_display:<10} {fill_display:<10} "
            f"{qty_str:<8} {status:<12} {time_str:<10} {fill_time_str:<10} {order_id}"
        )
    print("-" * 130)


def print_positions(positions):
    if not positions:
        print("当前无持仓。")
        return
    header = (
        f"{'Symbol':<10} {'Qty':<10} {'Last Price':<12} {'Mkt Value':<12} "
        f"{'Cost':<10} {'Diluted Cost':<14} {'Unrealized P&L':<15}"
    )
    print(header)
    print("-" * len(header))
    for pos in positions:
        ticker = pos.get("ticker", {})
        symbol = ticker.get("symbol") or pos.get("symbol") or "Unknown"
        qty = pos.get("position") or pos.get("quantity") or "0"
        last = pos.get("last_price") or pos.get("lastPrice")
        mkt_val = pos.get("market_value") or pos.get("marketValue")
        cost = pos.get("cost") or pos.get("costPrice")
        diluted_cost = (
            pos.get("diluted_cost")
            or pos.get("dilutedCost")
            or pos.get("diluted_cost_price")
            or pos.get("dilutedCostPrice")
        )
        pnl = pos.get("unrealized_profit_loss") or pos.get("unrealizedProfitLoss")
        print(
            f"{symbol:<10} {qty:<10} {format_price(last):<12} {format_price(mkt_val):<12} "
            f"{format_price(cost):<10} {format_price(diluted_cost):<14} {format_price(pnl):<15}"
        )
