"""Разбор JSON-сигнала TradingView в Signal."""

from contracts.models import Action, Signal

# Синонимы, которые может прислать TradingView.
# {{strategy.market_position}} даёт long / short / flat — это целевое состояние позиции.
_ACTIONS = {
    "long": Action.LONG,
    "buy": Action.LONG,
    "short": Action.SHORT,
    "sell": Action.SHORT,
    "close": Action.CLOSE,
    "flat": Action.CLOSE,
    "exit": Action.CLOSE,
}


class SignalError(ValueError):
    pass


def normalize_symbol(raw: str) -> str:
    """BYBIT:BTCUSDT.P → BTCUSDT"""
    symbol = raw.strip().upper()
    symbol = symbol.split(":")[-1]
    if symbol.endswith(".P"):
        symbol = symbol[:-2]
    return symbol


def parse_signal(payload: dict) -> Signal:
    symbol = payload.get("symbol")
    action = payload.get("action")
    if not isinstance(symbol, str) or not symbol.strip():
        raise SignalError("поле 'symbol' обязательно")
    if not isinstance(action, str) or action.strip().lower() not in _ACTIONS:
        raise SignalError(f"неизвестное действие {action!r}, ожидается одно из: {', '.join(_ACTIONS)}")

    signal_id = payload.get("id")
    return Signal(
        symbol=normalize_symbol(symbol),
        action=_ACTIONS[action.strip().lower()],
        signal_id=str(signal_id) if signal_id not in (None, "") else None,
    )
