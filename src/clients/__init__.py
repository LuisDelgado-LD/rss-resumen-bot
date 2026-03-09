"""Clientes para APIs externas."""
from .ttrss_client import TTRSSClient, TTRSSClientError, TTRSSAuthError
from .llm_client import LLMClient, LLMClientError, LLMRateLimitError
from .telegram_client import TelegramClient, TelegramClientError
from .wallabag_client import WallabagClient

__all__ = [
    "TTRSSClient",
    "TTRSSClientError", 
    "TTRSSAuthError",
    "LLMClient",
    "LLMClientError",
    "LLMRateLimitError",
    "TelegramClient",
    "TelegramClientError",
    "WallabagClient"
]