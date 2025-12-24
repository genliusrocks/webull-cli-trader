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

    # Webull API: Get Account Balance
    # Note: Currency param might be optional or 'USD' depending on region
    response = api.account.get_account_balance(account_id)

    if response.status_code != 200:
        console.print(f"[bold red]Error fetching funds:[/bold red] {response.text}")
        return

    data = response.json()
    
    # Create Table
    currency = data.get('total_asset_currency', 'USD')
    table = Table(title=f"Webull Account Summary - {currency}")
    table.add_column("Metric", style="cyan", no_wrap=True)
    table.add_column(f"Value ({currency})", style="green")

    # Extract Fields (Based on Webull Open API V1/V2 specs)
    total_asset = safe_float(data.get('total_asset') or data.get('net_liquidation'))
    market_val = safe_float(data.get('total_market_value'))
    cash_balance = safe_float(data.get('total_cash_balance') or data.get('cash_balance'))
    unrealized_pl = safe_float(data.get('total_unrealized_profit_loss'))
    
    # Some endpoints return Buying Power fields
    buying_power = safe_float(data.get('overnight_liquidity') or data.get('day_trade_buying_power'))

    table.add_row("Total Assets", f"${total_asset:,.2f}")
    table.add_row("Market Value", f"${market_val:,.2f}")
    table.add_row("Cash Balance", f"${cash_balance:,.2f}")
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
