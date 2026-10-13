from decimal import Decimal

from contracts.models import InstrumentRules, MarketOrder, OnOpposite, Position, SizeMode, SymbolSettings

BTC_RULES = InstrumentRules(
    qty_step=Decimal("0.001"),
    min_qty=Decimal("0.001"),
    min_notional=Decimal("5"),
    tick_size=Decimal("0.1"),
    max_leverage=Decimal("100"),
)


def make_settings(**overrides) -> SymbolSettings:
    values = dict(
        leverage=Decimal("5"),
        size_mode=SizeMode.MARGIN_USDT,
        size_value=Decimal("100"),
        take_profit_pct=None,
        stop_loss_pct=None,
        on_opposite=OnOpposite.REVERSE,
    )
    return SymbolSettings(**(values | overrides))


class FakeExchange:
    def __init__(self, price: str = "50000", balance: str = "1000"):
        self.price = Decimal(price)
        self.balance = Decimal(balance)
        self.positions: dict[str, Position] = {}
        self.orders: list[MarketOrder] = []
        self.leverage: dict[str, Decimal] = {}

    def instrument_rules(self, symbol: str) -> InstrumentRules:
        return BTC_RULES

    def last_price(self, symbol: str) -> Decimal:
        return self.price

    def available_balance(self) -> Decimal:
        return self.balance

    def position(self, symbol: str) -> Position | None:
        return self.positions.get(symbol)

    def set_leverage(self, symbol: str, leverage: Decimal) -> None:
        self.leverage[symbol] = leverage

    def market_order(self, order: MarketOrder) -> str:
        self.orders.append(order)
        if order.reduce_only:
            self.positions.pop(order.symbol, None)
        else:
            self.positions[order.symbol] = Position(order.side, order.qty)
        return f"order-{len(self.orders)}"


class FakeSettings:
    def __init__(self, symbols: dict[str, SymbolSettings]):
        self._symbols = symbols

    def symbols(self) -> list[str]:
        return list(self._symbols)

    def for_symbol(self, symbol: str) -> SymbolSettings | None:
        return self._symbols.get(symbol)
