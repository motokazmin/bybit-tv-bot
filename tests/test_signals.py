import pytest

from app.signals import SignalError, normalize_symbol, parse_signal
from contracts.models import Action


@pytest.mark.parametrize("raw", ["BTCUSDT", "btcusdt", "BTCUSDT.P", "BYBIT:BTCUSDT.P", " BYBIT:btcusdt "])
def test_normalize_symbol(raw):
    assert normalize_symbol(raw) == "BTCUSDT"


@pytest.mark.parametrize(
    ("raw", "action"),
    [("long", Action.LONG), ("BUY", Action.LONG), ("short", Action.SHORT), ("sell", Action.SHORT),
     ("close", Action.CLOSE), ("flat", Action.CLOSE), ("exit", Action.CLOSE)],
)
def test_action_aliases(raw, action):
    assert parse_signal({"symbol": "BTCUSDT", "action": raw}).action is action


def test_signal_id_is_optional():
    assert parse_signal({"symbol": "BTCUSDT", "action": "long"}).signal_id is None
    assert parse_signal({"symbol": "BTCUSDT", "action": "long", "id": 42}).signal_id == "42"


@pytest.mark.parametrize(
    "payload", [{}, {"symbol": "BTCUSDT"}, {"action": "long"}, {"symbol": "BTCUSDT", "action": "moon"}]
)
def test_invalid_signal(payload):
    with pytest.raises(SignalError):
        parse_signal(payload)
