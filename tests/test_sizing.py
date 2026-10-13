from decimal import Decimal

import pytest

from app.sizing import SizingError, order_qty, protective_prices
from contracts.models import Side, SizeMode
from tests.fakes import BTC_RULES, make_settings

PRICE = Decimal("50000")
BALANCE = Decimal("1000")


@pytest.mark.parametrize(
    ("mode", "value", "expected"),
    [
        (SizeMode.MARGIN_USDT, "100", "0.01"),     # 100 × 5 / 50000
        (SizeMode.NOTIONAL_USDT, "100", "0.002"),  # 100 / 50000
        (SizeMode.BALANCE_PCT, "10", "0.01"),      # 1000 × 10% × 5 / 50000
        (SizeMode.QTY, "0.0157", "0.015"),         # округление вниз до шага 0.001
    ],
)
def test_order_qty_modes(mode, value, expected):
    settings = make_settings(size_mode=mode, size_value=Decimal(value))

    assert order_qty(settings, PRICE, BALANCE, BTC_RULES) == Decimal(expected)


def test_qty_below_minimum_raises():
    settings = make_settings(size_mode=SizeMode.QTY, size_value=Decimal("0.0005"))

    with pytest.raises(SizingError):
        order_qty(settings, PRICE, BALANCE, BTC_RULES)


def test_long_protective_prices():
    settings = make_settings(take_profit_pct=Decimal("3"), stop_loss_pct=Decimal("1.5"))

    assert protective_prices(Side.LONG, PRICE, settings, BTC_RULES) == (Decimal("51500"), Decimal("49250"))


def test_no_protective_prices_by_default():
    assert protective_prices(Side.LONG, PRICE, make_settings(), BTC_RULES) == (None, None)
