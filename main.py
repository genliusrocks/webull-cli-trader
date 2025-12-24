import argparse
import json
import sys
import os  # 必须导入 os 模块

# --- 严格按照官方文档的 Import 路径 ---
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

# ================= 配置区域 =================
# 从环境变量读取凭据
YOUR_APP_KEY = os.getenv("WEBULL_APP_KEY")
YOUR_APP_SECRET = os.getenv("WEBULL_APP_SECRET")

# Region 配置
REGION_ID = "us"
# API 地址 (生产环境: api.webull.com, 测试环境: us-openapi-alb.uat.webullbroker.com)
API_ENDPOINT = "api.webull.com" 
# ===========================================

def get_trade_client():
    """初始化并返回 TradeClient"""
    # 检查环境变量是否已设置
    if not YOUR_APP_KEY or not YOUR_APP_SECRET:
        print("错误: 未找到环境变量 WEBULL_APP_KEY 或 WEBULL_APP_SECRET。", file=sys.stderr)
        print("请先在终端中设置它们，例如: export WEBULL_APP_KEY='你的Key'", file=sys.stderr)
        sys.exit(1)

    # 1. 初始化基础 API Client
    # 注意：这里如果 Key 包含非法字符（如中文），SDK 内部发请求时仍会报 latin-1 错误
    api_client = ApiClient(YOUR_APP_KEY, YOUR_APP_SECRET, REGION_ID)
    
    # 2. 添加 Endpoint (关键步骤)
    api_client.add_endpoint(REGION_ID, API_ENDPOINT)
    
    # 3. 初始化 Trade Client
    trade_client = TradeClient(api_client)
    return trade_client

def handle_account_list():
    """获取账户列表"""
    try:
        client = get_trade_client()
        
        # 调用 V2 接口
        res = client.account_v2.get_account_list()
        
        if res.status_code == 200:
            print("Successfully retrieved account list:")
            print(json.dumps(res.json(), indent=4))
        else:
            print(f"Failed. Status Code: {res.status_code}")
            print("Response:", res.text)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Webull OpenAPI CLI")
    subparsers = parser.add_subparsers(dest='command', required=True)
    
    # 'account' 子命令
    account_parser = subparsers.add_parser('account')
    account_parser.add_argument('action', choices=['list'])

    args = parser.parse_args()

    if args.command == 'account':
        if args.action == 'list':
            handle_account_list()

if __name__ == "__main__":
    main()