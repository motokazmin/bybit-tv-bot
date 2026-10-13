"""Адаптер ExchangePort для Bybit V5 (USDT-перпетуалы, Unified-аккаунт, one-way режим)."""

import logging
import time
from decimal import Decimal

from pybit.exceptions import FailedRequestError, InvalidRequestError
from pybit.unified_trading import HTTP

from contracts.models import InstrumentRules, MarketOrder, Position, Side

log = logging.getLogger("bybit")


class ExchangeAccessError(Exception):
    pass

_CATEGORY = "linear"
_ONE_WAY = 0

# Коды Bybit «ничего не изменилось» — не ошибка.
_LEVERAGE_NOT_MODIFIED = 110043
_POSITION_MODE_NOT_MODIFIED = 110025

# Запас под сетевую задержку внутри допуска Bybit (метка запроса < server_time + 1 с).
_MAX_CLOCK_AHEAD_S = 0.5

_MARGIN_MODES = {"isolated": "ISOLATED_MARGIN", "cross": "REGULAR_MARGIN"}
_ORDER_SIDES = {Side.LONG: "Buy", Side.SHORT: "Sell"}


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


class BybitExchange:
    def __init__(self, api_key: str, api_secret: str, demo: bool):
        self._http = HTTP(demo=demo, api_key=api_key, api_secret=api_secret, max_retries=1)
        self._rules: dict[str, InstrumentRules] = {}
        self._leverage: dict[str, Decimal] = {}

    def prepare_account(self, margin_mode: str) -> None:
        """Проверка часов и ключа, режим позиции one-way и режим маржи — один раз при старте."""
        self._check_clock()
        try:
            self._http.get_wallet_balance(accountType="UNIFIED")
        except (FailedRequestError, InvalidRequestError) as e:
            raise ExchangeAccessError(
                f"Bybit отклонил API-ключ ({e.message}). Проверьте api_key/api_secret и mode: "
                "ключ из Demo Trading работает только с mode: demo, ключ реального счёта — с mode: live."
            ) from None
        try:
            self._http.switch_position_mode(category=_CATEGORY, coin="USDT", mode=_ONE_WAY)
        except InvalidRequestError as e:
            if e.status_code != _POSITION_MODE_NOT_MODIFIED:
                raise
        try:
            self._http.set_margin_mode(setMarginMode=_MARGIN_MODES[margin_mode])
        except InvalidRequestError as e:
            # Например, при открытых позициях Bybit не даёт сменить режим — работаем дальше в текущем.
            log.warning("Не удалось установить режим маржи %s: %s", margin_mode, e.message)

    def _check_clock(self) -> None:
        # Bybit отвергает подписанный запрос, если его метка времени опережает сервер больше чем на 1 с
        # (ErrCode 10002); pybit после ретраев выдаёт это как безликий «Bad Request».
        server_ms = int(self._http.get_server_time()["time"])
        drift_s = (time.time() * 1000 - server_ms) / 1000
        if drift_s > _MAX_CLOCK_AHEAD_S:
            raise ExchangeAccessError(
                f"Системные часы спешат на {drift_s:.1f} с относительно сервера Bybit. "
                "Включите синхронизацию времени на хосте: sudo timedatectl set-ntp true"
            )

    def instrument_rules(self, symbol: str) -> InstrumentRules:
        if symbol not in self._rules:
            items = self._http.get_instruments_info(category=_CATEGORY, symbol=symbol)["result"]["list"]
            if not items:
                raise ValueError(f"пара {symbol} не найдена на Bybit (USDT-перпетуалы)")
            info = items[0]
            lot, price, lev = info["lotSizeFilter"], info["priceFilter"], info["leverageFilter"]
            self._rules[symbol] = InstrumentRules(
                qty_step=Decimal(lot["qtyStep"]),
                min_qty=Decimal(lot["minOrderQty"]),
                min_notional=Decimal(lot.get("minNotionalValue") or "0"),
                tick_size=Decimal(price["tickSize"]),
                max_leverage=Decimal(lev["maxLeverage"]),
            )
        return self._rules[symbol]

    def last_price(self, symbol: str) -> Decimal:
        ticker = self._http.get_tickers(category=_CATEGORY, symbol=symbol)["result"]["list"][0]
        return Decimal(ticker["lastPrice"])

    def available_balance(self) -> Decimal:
        # Сводные поля аккаунта (totalAvailableBalance и т.п.) в ISOLATED_MARGIN пустые,
        # поэтому свободные USDT считаем по самой монете — так одинаково для isolated и cross.
        account = self._http.get_wallet_balance(accountType="UNIFIED", coin="USDT")["result"]["list"][0]
        usdt = next((c for c in account["coin"] if c["coin"] == "USDT"), None)
        if usdt is None:
            return Decimal(0)
        used = sum(Decimal(usdt[k] or "0") for k in ("totalPositionIM", "totalOrderIM", "locked"))
        return max(Decimal(usdt["walletBalance"] or "0") - used, Decimal(0))

    def position(self, symbol: str) -> Position | None:
        for item in self._http.get_positions(category=_CATEGORY, symbol=symbol)["result"]["list"]:
            qty = Decimal(item["size"] or "0")
            if qty > 0:
                return Position(side=Side.LONG if item["side"] == "Buy" else Side.SHORT, qty=qty)
        return None

    def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        if self._leverage.get(symbol) == leverage:
            return
        try:
            self._http.set_leverage(
                category=_CATEGORY, symbol=symbol, buyLeverage=_fmt(leverage), sellLeverage=_fmt(leverage)
            )
        except InvalidRequestError as e:
            if e.status_code != _LEVERAGE_NOT_MODIFIED:
                raise
        self._leverage[symbol] = leverage

    def market_order(self, order: MarketOrder) -> str:
        params = dict(
            category=_CATEGORY,
            symbol=order.symbol,
            side=_ORDER_SIDES[order.side],
            orderType="Market",
            qty=_fmt(order.qty),
            positionIdx=_ONE_WAY,
            reduceOnly=order.reduce_only,
        )
        if order.take_profit is not None:
            params["takeProfit"] = _fmt(order.take_profit)
        if order.stop_loss is not None:
            params["stopLoss"] = _fmt(order.stop_loss)
        return self._http.place_order(**params)["result"]["orderId"]
