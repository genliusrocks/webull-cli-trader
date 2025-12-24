import click
import os
import sys

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from portfolio import get_account_summary, get_positions

@click.group()
def cli():
    """Webull CLI Trader - Official Open API."""
    pass

@cli.group()
def portfolio():
    """Manage portfolio and view account details."""
    pass

@portfolio.command("summary")
def summary_cmd():
    """Display current assets, cash, and market value."""
    get_account_summary()

@portfolio.command("positions")
def positions_cmd():
    """List current stock holdings."""
    get_positions()

if __name__ == '__main__':
    cli()