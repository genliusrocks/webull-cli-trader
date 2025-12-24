import json
from rich.console import Console
from rich.table import Table
from connection import ConnectionManager

console = Console()

def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0

def get_account_summary():
    """
    Fetches and displays Webull account assets and cash balance.
    """
    api = ConnectionManager.get_trade_api()
    account_id = ConnectionManager.get_account_id()

    console.print(f"[dim]Fetching summary for account: {account_id}...[/dim]")

    # FIX: Added required argument 'total_asset_currency'
    # We default to 'USD' for US market accounts.
    response = api.account.get_account_balance(account_id, total_asset_currency='USD')

    if response.status_code != 200:
        console.print(f"[bold red]Error fetching funds:[/bold red] {response.text}")
        return

    data = response.json()
    
    # Create Table
    currency = data.get('total_asset_currency', 'USD')
    table = Table(title=f"Webull Account Summary - {currency}")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column(f"Value ({currency})", style="green")

    # Extract Fields (Based on Webull Open API specs)
    total_asset = safe_float(data.get('total_asset') or data.get('net_liquidation'))
    market_val = safe_float(data.get('total_market_value'))
    cash_balance = safe_float(data.get('total_cash_balance') or data.get('cash_balance'))
    unrealized_pl = safe_float(data.get('total_unrealized_profit_loss'))
    
    # Some endpoints return Buying Power fields
    buying_power = safe_float(data.get('overnight_liquidity') or data.get('day_trade_buying_power'))

    table.add_row("Total Assets", f"${total_asset:,.2f}")
    table.add_row("Cash Balance", f"${cash_balance:,.2f}")
    table.add_row("Market Value", f"${market_val:,.2f}")
    table.add_row("Unrealized P&L", f"${unrealized_pl:,.2f}")
    table.add_row("Buying Power", f"${buying_power:,.2f}")

    console.print(table)

def get_positions():
    """
    Fetches and displays current positions from Webull.
    """
    api = ConnectionManager.get_trade_api()
    account_id = ConnectionManager.get_account_id()

    console.print(f"[dim]Fetching positions for account: {account_id}...[/dim]")

    response = api.account.get_account_position(account_id)

    if response.status_code != 200:
        console.print(f"[bold red]Error fetching positions:[/bold red] {response.text}")
        return

    data = response.json()
    positions = data if isinstance(data, list) else data.get('positions', [])

    if not positions:
        console.print("[yellow]No positions found.[/yellow]")
        return

    table = Table(title="Webull Positions")
    table.add_column("Symbol", style="yellow")
    table.add_column("Qty", justify="right")
    table.add_column("Cost", justify="right")
    table.add_column("Last Price", justify="right")
    table.add_column("Market Val", justify="right")
    table.add_column("Unrealized P&L", justify="right")

    for pos in positions:
        # Field names based on Webull API docs
        symbol = pos.get('symbol', 'N/A')
        # Some endpoints use 'ticker' object
        if 'ticker' in pos:
            symbol = pos['ticker'].get('symbol', symbol)

        qty = safe_float(pos.get('position') or pos.get('qty'))
        cost = safe_float(pos.get('cost_price') or pos.get('cost'))
        last_price = safe_float(pos.get('last_price'))
        mkt_val = safe_float(pos.get('market_value'))
        unrealized_pl = safe_float(pos.get('unrealized_profit_loss'))

        # P&L Color
        pl_style = "green" if unrealized_pl >= 0 else "red"

        table.add_row(
            symbol,
            f"{qty:,.0f}",
            f"{cost:,.2f}",
            f"{last_price:,.2f}",
            f"{mkt_val:,.2f}",
            f"[{pl_style}]{unrealized_pl:+,.2f}[/{pl_style}]"
        )

    console.print(table)
def list_accounts():
    """
    Fetches and lists all accounts associated with the user.
    """
    api = ConnectionManager.get_trade_api()
    console.print(f"[dim]Fetching account list...[/dim]")

    data = None
    response = None

    try:
        # 策略 1: 尝试 api.account_v2.get_account_list (常见于新版 SDK)
        # 注意: 这里检查的是 api 根对象下的 account_v2，而不是 api.account
        if hasattr(api, 'account_v2') and hasattr(api.account_v2, 'get_account_list'):
            console.print("[dim]Using api.account_v2.get_account_list()...[/dim]")
            response = api.account_v2.get_account_list()
            
        # 策略 2: 尝试 api.account.get_account_list (旧版)
        elif hasattr(api.account, 'get_account_list'):
            response = api.account.get_account_list()
            
        # 策略 3: 尝试 get_app_subscriptions (有时包含 account_id)
        elif hasattr(api.account, 'get_app_subscriptions'):
            console.print("[dim]Method 'get_account_list' missing. Trying 'get_app_subscriptions' to find account...[/dim]")
            # 传入空字典或 0 作为 page_size/offset
            response = api.account.get_app_subscriptions({'page_size': 10})
        
        else:
            console.print("[bold red]Error:[/bold red] Could not find any method to list accounts.")
            console.print(f"Please check dir(api): {dir(api)}")
            return

        # 检查响应
        if response and response.status_code != 200:
            console.print(f"[bold red]Error API Response:[/bold red] {response.text}")
            return
        
        if response:
            data = response.json()
        
    except Exception as e:
        console.print(f"[bold red]Exception:[/bold red] {e}")
        return

    if not data:
        console.print("[yellow]No data returned.[/yellow]")
        return

    # 解析数据 (兼容 v1/v2/subscriptions 不同结构)
    accounts = []
    
    # 情况 A: 标准 Account List 结构
    if isinstance(data, list):
        accounts = data
    elif 'data' in data and isinstance(data['data'], list):
        accounts = data['data']
    elif 'accountList' in data: # 有些版本返回 camelCase
        accounts = data['accountList']
    # 情况 B: Subscriptions 结构 (提取 account_id)
    elif isinstance(data, dict) and 'account_id' in data:
        accounts = [data] # 单个对象转列表
    
    if not accounts:
        console.print(f"[yellow]Could not parse accounts from:[/yellow] {data}")
        return

    # 绘制表格
    table = Table(title="Webull Accounts")
    table.add_column("Account ID", style="bold cyan")
    table.add_column("Type/Status", style="yellow")
    table.add_column("Region")

    for acc in accounts:
        # 尝试提取各种可能的字段名
        acc_id = str(acc.get('account_id') or acc.get('accountId') or acc.get('sec_account_id') or 'N/A')
        
        # 尝试提取状态/类型
        acc_type = str(acc.get('account_type_name') or acc.get('account_type') or 'Unknown')
        status = str(acc.get('status') or acc.get('account_status') or '-')
        
        # 尝试提取区域
        region = str(acc.get('region_name') or acc.get('region_id') or '-')

        table.add_row(acc_id, f"{acc_type} ({status})", region)

    console.print(table)
