# backend/app/plugins/__init__.py
from .base_plugin import BasePlugin
from .trading_plugin import TradingPlugin
from .email_plugin import EmailPlugin

__all__ = ['BasePlugin', 'TradingPlugin', 'EmailPlugin']