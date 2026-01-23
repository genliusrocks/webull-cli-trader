import logging
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timezone, timedelta

# 引入 Webull 数据常量
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan

from app.adapter import WebullApiAdapter, WebullApiError

logger = logging.getLogger(__name__)

# ==========================================
# 辅助函数
# ==========================================

def parse_order_time(time_val):
    """解析订单时间为 UTC datetime"""
    if not time_val:
        return None
    try:
        # 可能是毫秒时间戳
        if str(time_val).isdigit():
            return datetime.fromtimestamp(int(time_val) / 1000, tz=timezone.utc)
        # 可能是 ISO 字符串
        dt = pd.to_datetime(time_val)
        if dt.tz is None:
            dt = dt.tz_localize(timezone.utc)
        else:
            dt = dt.tz_convert(timezone.utc)
        return dt.to_pydatetime()
    except Exception:
        return None

def fetch_history_for_date(client, account_id, target_date_str, symbol):
    """
    专门为 Review 设计的抓取函数。
    会自动翻页，直到覆盖了目标日期的数据。
    """
    target_date = datetime.strptime(target_date_str, "%y%m%d").date()
    print(f"  > 正在搜索 {target_date} 关于 {symbol} 的交易记录...")
    
    all_target_orders = []
    last_oid = None
    page_size = 100
    max_pages = 50 
    
    for page in range(1, max_pages + 1):
        # 构造请求参数
        kwargs = {'page_size': str(page_size)}
        if last_oid:
            kwargs['last_order_id'] = last_oid
            
        try:
            res = client.order_v2.get_order_history_request(account_id, **kwargs)
        except TypeError:
            if page == 1:
                res = client.order_v2.get_order_history_request(account_id, page_size=100)
            else:
                break

        if res and res.status_code == 200:
            data = res.json()
            batch = data if isinstance(data, list) else (data.get("data") or data.get("items") or [])
            
            if not batch:
                break
                
            for item in batch:
                detail = item['orders'][0] if isinstance(item.get("orders"), list) and item['orders'] else item
                
                fill_time = detail.get('filledTime') or detail.get('filled_time') or detail.get('place_time')
                order_dt = parse_order_time(fill_time)
                
                if not order_dt:
                    continue
                
                order_date = order_dt.date()
                
                s = detail.get('symbol') or detail.get('ticker', {}).get('symbol')
                if str(s).upper() == symbol.upper() and order_date == target_date:
                    status = str(detail.get('status') or detail.get('order_status') or "").lower()
                    if 'filled' in status:
                        all_target_orders.append(item)

            # 如果这一页最后一条的时间比目标日期还早，通常可以停止了
            last_item_dt = parse_order_time(batch[-1].get('filledTime') or batch[-1].get('place_time'))
            if last_item_dt and last_item_dt.date() < target_date:
                break

            last_oid = batch[-1].get('order_id') or batch[-1].get('orderId')
            if not last_oid:
                break
        else:
            logger.warning(f"无法获取历史订单: {res.status_code if res else 'Unknown'}")
            break
            
    return all_target_orders

def get_bars(api: WebullApiAdapter, symbol, count=800):
    """
    [修改] 获取 K 线数据
    Webull API 限制最大 count 为 1650。
    我们将默认值设为 800 (约 2 个交易日)，足够 Review 使用。
    """
    try:
        data_client = api.get_data_client()
        
        # 确保不超过 API 限制
        safe_count = min(count, 1650)
        
        print(f"  > 正在获取 {symbol} 的 K 线数据 (Count: {safe_count})...")
        
        # 调用 DataClient 的 get_history_bar
        res = data_client.market_data.get_history_bar(
            symbol, 
            Category.US_STOCK.name, 
            Timespan.M1.name, 
            safe_count
        )
        
        if res.status_code == 200:
            data = res.json()
            bars_list = data if isinstance(data, list) else data.get('data', [])
            
            if not bars_list:
                return None
            
            df = pd.DataFrame(bars_list)
            return df
        else:
            logger.error(f"API 返回错误: {res.status_code} - {res.text}")
            return None

    except Exception as exc:
        logger.error(f"获取 K 线数据失败: {exc}")
        return None

def calculate_indicators(df):
    """计算 VWAP, EMA"""
    # 简单的列名映射，防止 API 返回简写
    mapping = {'op': 'open', 'cl': 'close', 'hi': 'high', 'lo': 'low', 'vol': 'volume'}
    df = df.rename(columns=mapping)
    
    cols = ['open', 'high', 'low', 'close', 'volume']
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col])
            
    if 'close' not in df.columns:
        return df

    df['tp'] = (df['high'] + df['low'] + df['close']) / 3
    df['cum_vol'] = df['volume'].cumsum()
    df['cum_pv'] = (df['tp'] * df['volume']).cumsum()
    df['vwap'] = df['cum_pv'] / df['cum_vol']
    df['ema9'] = df['close'].ewm(span=9, adjust=False).mean()
    df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
    return df

def plot_chart(symbol, date_str, bars_df, trades):
    """绘图逻辑"""
    target_date = datetime.strptime(date_str, "%y%m%d").date()
    
    # 识别时间列
    time_col = next((col for col in ['timestamp', 'time', 't'] if col in bars_df.columns), None)
    if not time_col:
        logger.error(f"无法识别时间列: {bars_df.columns}")
        return

    # 统一时间列
    try:
        # 尝试毫秒转换 (Webull 通常是毫秒)
        bars_df['dt'] = pd.to_datetime(bars_df[time_col], unit='ms')
    except:
        # 尝试字符串解析
        bars_df['dt'] = pd.to_datetime(bars_df[time_col])
    
    # 转换为 UTC
    if bars_df['dt'].dt.tz is None:
        bars_df['dt'] = bars_df['dt'].dt.tz_localize(timezone.utc)
    else:
        bars_df['dt'] = bars_df['dt'].dt.tz_convert(timezone.utc)

    # 过滤当日数据
    df_day = bars_df[bars_df['dt'].dt.date == target_date].copy()
    
    if df_day.empty:
        print(f"未找到 {date_str} 的 K 线数据 (可能休市或数据超出 Count 范围)。")
        if not bars_df.empty:
            print(f"DEBUG: 数据范围 {bars_df['dt'].min().date()} 到 {bars_df['dt'].max().date()}")
        return

    df_day = df_day.set_index('dt')
    df_day = calculate_indicators(df_day)

    # 绘图
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # K 线
    up = df_day[df_day.close >= df_day.open]
    down = df_day[df_day.close < df_day.open]
    
    ax.vlines(up.index, up.low, up.high, color='green', linewidth=1)
    ax.vlines(down.index, down.low, down.high, color='red', linewidth=1)
    ax.vlines(up.index, up.open, up.close, color='green', linewidth=4)
    ax.vlines(down.index, down.open, down.close, color='red', linewidth=4)
    
    # 指标
    if 'ema9' in df_day.columns:
        ax.plot(df_day.index, df_day['ema9'], label='EMA 9', color='cyan', linewidth=1, alpha=0.8)
    if 'ema20' in df_day.columns:
        ax.plot(df_day.index, df_day['ema20'], label='EMA 20', color='orange', linewidth=1, alpha=0.8)
    if 'vwap' in df_day.columns:
        ax.plot(df_day.index, df_day['vwap'], label='VWAP', color='purple', linestyle='--', linewidth=1)

    # 标记交易
    print(f"  > 在图表上标记 {len(trades)} 笔交易...")
    for trade in trades:
        detail = trade['orders'][0] if isinstance(trade.get("orders"), list) else trade
        
        fill_time = detail.get('filledTime') or detail.get('filled_time')
        fill_dt = parse_order_time(fill_time)
        if not fill_dt: continue
            
        price = float(detail.get('avgFilledPrice') or detail.get('filledPrice') or 0)
        action = detail.get('action') or detail.get('side')
        qty = detail.get('filledQuantity') or detail.get('quantity')
        
        marker = '^' if action == 'BUY' else 'v'
        color = 'lime' if action == 'BUY' else 'magenta'
        offset = -0.002 * price if action == 'BUY' else 0.002 * price
        
        ax.plot(fill_dt, price, marker=marker, color=color, markersize=12, markeredgecolor='black', zorder=10)
        ax.text(fill_dt, price + offset, f"{qty}", ha='center', va='bottom' if action=='BUY' else 'top', fontsize=9, color='black', fontweight='bold')

    ax.set_title(f"Review: {symbol.upper()} - {date_str}")
    ax.grid(True, alpha=0.3)
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    filename = f"review_{symbol}_{date_str}.png"
    plt.savefig(filename)
    print(f">>> 图表已保存: {filename}")


# ==========================================
# 主入口
# ==========================================

def handle_review(api: WebullApiAdapter, symbol: str, date_str: str):
    try:
        client = api.get_trade_client()
        account_id = api.get_first_account_id(client)
        symbol = symbol.upper()
        
        # 1. 独立获取历史订单
        trades = fetch_history_for_date(client, account_id, date_str, symbol)
        
        if not trades:
            print(f"没有找到 {date_str} 关于 {symbol} 的成交记录。")
        else:
            print(f"找到 {len(trades)} 笔交易。")

        # 2. 获取 K 线
        # [修改点] 这里 count 设为 800 (API 允许最大 1650)
        bars_df = get_bars(api, symbol, count=800) 
        
        if bars_df is None or bars_df.empty:
            logger.error("无法获取 K 线数据。")
            return
            
        # 3. 绘图
        plot_chart(symbol, date_str, bars_df, trades)

    except WebullApiError as exc:
        logger.error("%s", exc)
        sys.exit(exc.exit_code)
    except ImportError:
        logger.error("缺少 pandas 或 matplotlib。请安装: pip install pandas matplotlib")
    except Exception as exc:
        logger.exception("Review 出错: %s", exc)
        sys.exit(1)