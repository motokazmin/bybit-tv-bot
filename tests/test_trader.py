from decimal import Decimal

from app.trader import Trader
from contracts.models import Action, OnOpposite, Position, Side, Signal
from tests.fakes import FakeExchange, FakeSettings, make_settings


def make_trader(**settings_overrides) -> tuple[Trader, FakeExchange]:
    exchange = FakeExchange()
    trader = Trader(exchange, FakeSettings({"BTCUSDT": make_settings(**settings_overrides)}))
    return trader, exchange


def test_opens_long_with_leverage():
    trader, exchange = make_trader()

    trader.handle(Signal("BTCUSDT", Action.LONG))

    assert exchange.leverage["BTCUSDT"] == Decimal("5")
    [order] = exchange.orders
    assert order.side is Side.LONG
    assert order.qty == Decimal("0.01")  # 100 USDT × 5 / 50000
    assert not order.reduce_only


def test_same_direction_is_skipped():
    trader, exchange = make_trader()
    exchange.positions["BTCUSDT"] = Position(Side.LONG, Decimal("0.01"))

    trader.handle(Signal("BTCUSDT", Action.LONG))

    assert exchange.orders == []


def test_opposite_signal_reverses_position():
    trader, exchange = make_trader()
    exchange.positions["BTCUSDT"] = Position(Side.LONG, Decimal("0.02"))

    trader.handle(Signal("BTCUSDT", Action.SHORT))

    close, open_ = exchange.orders
    assert (close.side, close.qty, close.reduce_only) == (Side.SHORT, Decimal("0.02"), True)
    assert (open_.side, open_.reduce_only) == (Side.SHORT, False)
    assert exchange.positions["BTCUSDT"].side is Side.SHORT


def test_opposite_signal_only_closes():
    trader, exchange = make_trader(on_opposite=OnOpposite.CLOSE)
    exchange.positions["BTCUSDT"] = Position(Side.LONG, Decimal("0.02"))

    trader.handle(Signal("BTCUSDT", Action.SHORT))

    [order] = exchange.orders
    assert order.reduce_only
    assert "BTCUSDT" not in exchange.positions


def test_opposite_signal_ignored():
    trader, exchange = make_trader(on_opposite=OnOpposite.IGNORE)
    exchange.positions["BTCUSDT"] = Position(Side.LONG, Decimal("0.02"))

    trader.handle(Signal("BTCUSDT", Action.SHORT))

    assert exchange.orders == []


def test_close_without_position_does_nothing():
    trader, exchange = make_trader()

    trader.handle(Signal("BTCUSDT", Action.CLOSE))

    assert exchange.orders == []


def test_close_short_position():
    trader, exchange = make_trader()
    exchange.positions["BTCUSDT"] = Position(Side.SHORT, Decimal("0.05"))

    trader.handle(Signal("BTCUSDT", Action.CLOSE))

    [order] = exchange.orders
    assert (order.side, order.qty, order.reduce_only) == (Side.LONG, Decimal("0.05"), True)


def test_unknown_symbol_is_rejected():
    trader, exchange = make_trader()

    trader.handle(Signal("DOGEUSDT", Action.LONG))

    assert exchange.orders == []


def test_too_small_size_does_not_open():
    trader, exchange = make_trader(size_value=Decimal("0.5"))  # 2.5 USDT объёма < 5 USDT минимума

    trader.handle(Signal("BTCUSDT", Action.LONG))

    assert exchange.orders == []


def test_take_profit_and_stop_loss_attached():
    trader, exchange = make_trader(take_profit_pct=Decimal("2"), stop_loss_pct=Decimal("1"))

    trader.handle(Signal("BTCUSDT", Action.SHORT))

    [order] = exchange.orders
    assert order.take_profit == Decimal("49000")
    assert order.stop_loss == Decimal("50500")
