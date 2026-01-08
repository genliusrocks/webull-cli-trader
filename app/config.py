import logging
import os
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WebullConfig:
    app_key: str
    app_secret: str
    region_id: str = "us"
    api_endpoint: str = "api.webull.com"


def load_config() -> WebullConfig:
    app_key = os.getenv("WEBULL_APP_KEY")
    app_secret = os.getenv("WEBULL_APP_SECRET")
    if not app_key or not app_secret:
        logger.error("错误: 未找到环境变量 WEBULL_APP_KEY 或 WEBULL_APP_SECRET。")
        sys.exit(1)
    return WebullConfig(app_key=app_key, app_secret=app_secret)
