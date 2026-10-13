"""Порты, которые нужны прикладному коду. Реализации живут в infra/."""

from decimal import Decimal
from typing import Protocol

from contracts.models import InstrumentRules, MarketOrder, Position, SymbolSettings


class ExchangePort(Protocol):
    def instrument_rules(self, symbol: str) -> InstrumentRules: ...

    def last_price(self, symbol: str) -> Decimal: ...

    def available_balance(self) -> Decimal: ...

    def position(self, symbol: str) -> Position | None: ...

    def set_leverage(self, symbol: str, leverage: Decimal) -> None: ...

    def market_order(self, order: MarketOrder) -> str: ...


class SettingsPort(Protocol):
    def symbols(self) -> list[str]: ...

    def for_symbol(self, symbol: str) -> SymbolSettings | None:
        """None — пара не разрешена к торговле."""
        ...
