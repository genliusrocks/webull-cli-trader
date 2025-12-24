import argparse
import json
import sys
import os

from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

# ================= 配置区域 =================
YOUR_APP_KEY = os.getenv("WEBULL_APP_KEY")
YOUR_APP_SECRET = os.getenv("WEBULL_APP_SECRET")
REGION_ID = "us"
API_ENDPOINT = "api.webull.com" 
# ===========================================

def get_trade_client():
    """初始化并返回 TradeClient"""
    if not YOUR_APP_KEY or not YOUR_APP_SECRET:
        print("错误: 未找到环境变量 WEBULL_APP_KEY 或 WEBULL_APP_SECRET。", file=sys.stderr)
        sys.exit(1)

    api_client = ApiClient(YOUR_APP_KEY, YOUR_APP_SECRET, REGION_ID)
    api_client.add_endpoint(REGION_ID, API_ENDPOINT)
    return TradeClient(api_client)

def handle_account_list():
    """获取账户列表"""
    try:
        client = get_trade_client()
        res = client.account_v2.get_account_list()
        if res.status_code == 200:
            print("Successfully retrieved account list:")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f"Failed. Status Code: {res.status_code}")
            print(res.text)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)

def handle_account_balance():
    """获取所有账户的资产余额并打印关键信息"""
    try:
        client = get_trade_client()
        
        # 1. 获取账户列表
        list_res = client.account_v2.get_account_list()
        if list_res.status_code != 200:
            print(f"无法获取账户列表: {list_res.text}")
            return

        account_list = list_res.json()
        if not account_list:
            print("未找到有效账户。")
            return

        print(f"发现 {len(account_list)} 个账户，开始查询余额...\n")

        # 2. 遍历每个账户查询余额
        for acct in account_list:
            account_id = acct.get('account_id')
            if not account_id:
                print("跳过: 无法找到 account_id")
                continue

            account_type = acct.get('account_type', 'Unknown')
            print(f"--- 账户 ID: {account_id} (类型: {account_type}) ---")
            
            # 调用 Balance 接口
            bal_res = client.account_v2.get_account_balance(account_id)
            
            if bal_res.status_code == 200:
                data = bal_res.json()
                
                # === 调试关键点：打印原始数据 ===
                # 如果下面打印出来的还是 None，请把这段打印出来的 JSON 发给我
                print(">>> DEBUG: 服务器返回的原始数据:") 
                print(json.dumps(data, indent=2))
                print("-" * 20)
                # ============================

                # 尝试同时获取驼峰(camelCase)和下划线(snake_case)两种格式
                summary = {
                    "净资产 (Net Liquidation)": data.get('netLiquidation') or data.get('net_liquidation'),
                    "总市值 (Total Market Value)": data.get('totalMarketValue') or data.get('total_market_value') or data.get('market_value'),
                    "现金余额 (Cash Balance)": data.get('cashBalance') or data.get('cash_balance') or data.get('total_cash_balance'),
                    "可用购买力 (Buying Power)": data.get('buyingPower') or data.get('buying_power'),
                    "未实现盈亏 (Unrealized P&L)": data.get('unrealizedProfitLoss') or data.get('unrealized_profit_loss'),
                    "币种 (Currency)": data.get('currency')
                }

                for k, v in summary.items():
                    print(f"{k:<30}: {v}")
            else:
                print(f"获取余额失败: {bal_res.status_code}")
                print(bal_res.text)
            
            print("-" * 50 + "\n")

    except Exception as e:
        print(f"执行出错: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # 'account' 子命令
    account_parser = subparsers.add_parser('account')
    account_parser.add_argument('action', choices=['list', 'balance'], help='Action to perform')

    args = parser.parse_args()

    if args.command == 'account':
        if args.action == 'list':
            handle_account_list()
        elif args.action == 'balance':
            handle_account_balance()

if __name__ == "__main__":
    main()
