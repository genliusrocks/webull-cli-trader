import os
import sys
from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region
from webullsdktrade.api import API

# Configuration from Environment Variables
APP_KEY = os.getenv("WEBULL_APP_KEY")
APP_SECRET = os.getenv("WEBULL_APP_SECRET")
REGION_CODE = os.getenv("WEBULL_REGION", "US").upper()  # US, HK, JP
ACCOUNT_ID = os.getenv("WEBULL_ACCOUNT_ID")

class ConnectionManager:
    _api_client = None
    _trade_api = None
    _cached_account_id = ACCOUNT_ID

    @classmethod
    def get_api_client(cls):
        if cls._api_client is None:
            if not APP_KEY or not APP_SECRET:
                print("[bold red]Error:[/bold red] Please set WEBULL_APP_KEY and WEBULL_APP_SECRET environment variables.")
                sys.exit(1)
            
            # Determine Region
            region = Region.US
            if REGION_CODE == "HK": region = Region.HK
            elif REGION_CODE == "JP": region = Region.JP
            
            try:
                cls._api_client = ApiClient(APP_KEY, APP_SECRET, region.value)
            except Exception as e:
                print(f"[bold red]Error initializing Webull Client:[/bold red] {e}")
                sys.exit(1)
        return cls._api_client

    @classmethod
    def get_trade_api(cls):
        if cls._trade_api is None:
            client = cls.get_api_client()
            cls._trade_api = API(client)
        return cls._trade_api

    @classmethod
    def get_account_id(cls):
        """
        Returns the configured account ID or fetches the first available one.
        """
        if cls._cached_account_id:
            return cls._cached_account_id
        
        # If no ID provided, fetch list and use the first one
        api = cls.get_trade_api()
        try:
            response = api.account.get_account_list()
            if response.status_code == 200:
                accounts = response.json()
                if accounts and len(accounts) > 0:
                    cls._cached_account_id = accounts[0].get('account_id')
                    return cls._cached_account_id
        except Exception as e:
            print(f"[red]Failed to fetch account list:[/red] {e}")
        
        print("[bold red]Error:[/bold red] No account ID found. Please set WEBULL_ACCOUNT_ID.")
        sys.exit(1)