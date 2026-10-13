"""Торговая логика: что сделать с позицией по пришедшему сигналу."""

import logging

from app.sizing import SizingError, order_qty, protective_prices
from contracts.models import Action, MarketOrder, OnOpposite, Position, Side, Signal, SymbolSettings
from contracts.ports import ExchangePort, SettingsPort

log = logging.getLogger("trader")


class Trader:
    def __init__(self, exchange: ExchangePort, settings: SettingsPort):
        self._exchange = exchange
        self._settings = settings

    def check_ready(self) -> None:
        """Проверка при старте: пары существуют, плечо в допустимых пределах."""
        log.info("Доступный баланс: %s USDT", self._exchange.available_balance())
        for symbol in self._settings.symbols():
            settings = self._settings.for_symbol(symbol)
            rules = self._exchange.instrument_rules(symbol)
            if settings.leverage > rules.max_leverage:
                raise ValueError(f"{symbol}: плечо {settings.leverage} больше максимального {rules.max_leverage}")
            log.info(
                "%s: плечо x%s, размер %s=%s, TP %s%%, SL %s%%, при обратном сигнале: %s",
                symbol, settings.leverage, settings.size_mode.value, settings.size_value,
                settings.take_profit_pct or "-", settings.stop_loss_pct or "-", settings.on_opposite.value,
            )

    def handle(self, signal: Signal) -> None:
        settings = self._settings.for_symbol(signal.symbol)
        if settings is None:
            log.warning("Сигнал по %s отклонён: пара не указана в настройках", signal.symbol)
            return

        position = self._exchange.position(signal.symbol)

        if signal.action is Action.CLOSE:
            if position is None:
                log.info("%s: сигнал на закрытие, но позиции нет", signal.symbol)
            else:
                self._close(signal.symbol, position)
            return

        target = Side(signal.action.value)
        if position is not None:
            if position.side is target:
                log.info("%s: позиция %s уже открыта, сигнал пропущен", signal.symbol, target.value.upper())
                return
            if settings.on_opposite is OnOpposite.IGNORE:
                log.info("%s: обратный сигнал проигнорирован (on_opposite=ignore)", signal.symbol)
                return
            self._close(signal.symbol, position)
            if settings.on_opposite is OnOpposite.CLOSE:
                return

        self._open(signal.symbol, target, settings)

    def _open(self, symbol: str, side: Side, settings: SymbolSettings) -> None:
        rules = self._exchange.instrument_rules(symbol)
        price = self._exchange.last_price(symbol)
        balance = self._exchange.available_balance()
        try:
            qty = order_qty(settings, price, balance, rules)
        except SizingError as e:
            log.error("%s: позиция не открыта — %s", symbol, e)
            return
        take_profit, stop_loss = protective_prices(side, price, settings, rules)

        self._exchange.set_leverage(symbol, settings.leverage)
        order_id = self._exchange.market_order(
            MarketOrder(symbol, side, qty, take_profit=take_profit, stop_loss=stop_loss)
        )
        log.info(
            "%s: открыт %s %s (~%s USDT, x%s), TP %s, SL %s, ордер %s",
            symbol, side.value.upper(), qty, (qty * price).quantize(rules.tick_size), settings.leverage,
            take_profit or "-", stop_loss or "-", order_id,
        )

    def _close(self, symbol: str, position: Position) -> None:
        order_id = self._exchange.market_order(
            MarketOrder(symbol, position.side.opposite, position.qty, reduce_only=True)
        )
        log.info("%s: закрыт %s %s, ордер %s", symbol, position.side.value.upper(), position.qty, order_id)
