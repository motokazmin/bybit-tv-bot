"""Composition root: единственное место, где создаются и связываются зависимости."""

import logging
from pathlib import Path

from fastapi import FastAPI

from app.trader import Trader
from infra.bybit import BybitExchange
from infra.config import StaticSettings, load_config
from infra.logs import setup_logging
from infra.webhook import create_webhook_app


def build(config_path: Path) -> tuple[FastAPI, int]:
    setup_logging()
    config = load_config(config_path)
    logging.getLogger("bot").info("Режим: %s, маржа: %s", config.mode.upper(), config.margin_mode)

    exchange = BybitExchange(config.api_key, config.api_secret, demo=config.mode == "demo")
    exchange.prepare_account(config.margin_mode)

    trader = Trader(exchange, StaticSettings(config.symbols))
    trader.check_ready()

    return create_webhook_app(config.webhook_secret, trader.handle, config.mode), config.port
