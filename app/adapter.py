
from webull.core.client import ApiClient
from webull.trade.trade_client import TradeClient

from app.config import WebullConfig


class WebullApiError(Exception):
    def __init__(self, message: str, exit_code: int = 1):
        super().__init__(message)
        self.exit_code = exit_code


class WebullApiAdapter:
    def __init__(self, config: WebullConfig):
        self.config = config

    def get_trade_client(self) -> TradeClient:
        api_client = ApiClient(self.config.app_key, self.config.app_secret, self.config.region_id)
        api_client.add_endpoint(self.config.region_id, self.config.api_endpoint)
        return TradeClient(api_client)

    def get_first_account_id(self, client: TradeClient) -> str:
        list_res = client.account_v2.get_account_list()
        if list_res.status_code != 200:
            raise WebullApiError(f"无法获取账户列表: {list_res.text}", exit_code=1)

        data = list_res.json()
        if isinstance(data, dict):
            account_list = data.get("data", [])
        else:
            account_list = data

        if not account_list:
            raise WebullApiError("未找到有效账户。", exit_code=1)

        first_acct = account_list[0]
        acct_id = first_acct.get("account_id") or first_acct.get("secAccountId")
        return str(acct_id)

    @staticmethod
    def extract_list_from_response(json_data):
        if isinstance(json_data, list):
            return json_data
        if isinstance(json_data, dict):
            return json_data.get("data") or json_data.get("items") or json_data.get("orders") or []
        return []
