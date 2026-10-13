"""Типы данных, общие для прикладного кода и каркаса. Зависят только от stdlib."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class Action(str, Enum):
    LONG = "long"
    SHORT = "short"
    CLOSE = "close"


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"

    @property
    def opposite(self) -> "Side":
        return Side.SHORT if self is Side.LONG else Side.LONG


class SizeMode(str, Enum):
    MARGIN_USDT = "margin_usdt"      # маржа в USDT, объём = маржа × плечо
    NOTIONAL_USDT = "notional_usdt"  # объём позиции в USDT
    BALANCE_PCT = "balance_pct"      # % доступного баланса как маржа
    QTY = "qty"                      # фиксированное количество монет


class OnOpposite(str, Enum):
    REVERSE = "reverse"  # закрыть текущую и открыть противоположную
    CLOSE = "close"      # только закрыть текущую
    IGNORE = "ignore"    # ничего не делать


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: Action
    signal_id: str | None = None


@dataclass(frozen=True)
class SymbolSettings:
    leverage: Decimal
    size_mode: SizeMode
    size_value: Decimal
    take_profit_pct: Decimal | None
    stop_loss_pct: Decimal | None
    on_opposite: OnOpposite


@dataclass(frozen=True)
class InstrumentRules:
    qty_step: Decimal
    min_qty: Decimal
    min_notional: Decimal
    tick_size: Decimal
    max_leverage: Decimal


@dataclass(frozen=True)
class Position:
    side: Side
    qty: Decimal


@dataclass(frozen=True)
class MarketOrder:
    symbol: str
    side: Side
    qty: Decimal
    reduce_only: bool = False
    take_profit: Decimal | None = None
    stop_loss: Decimal | None = None
