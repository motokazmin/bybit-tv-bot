"""Расчёт количества и уровней TP/SL с учётом правил инструмента."""

from decimal import ROUND_DOWN, Decimal

from contracts.models import InstrumentRules, Side, SizeMode, SymbolSettings

_HUNDRED = Decimal(100)


class SizingError(ValueError):
    pass


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def order_qty(settings: SymbolSettings, price: Decimal, balance: Decimal, rules: InstrumentRules) -> Decimal:
    if settings.size_mode is SizeMode.QTY:
        raw = settings.size_value
    else:
        notional = {
            SizeMode.MARGIN_USDT: settings.size_value * settings.leverage,
            SizeMode.NOTIONAL_USDT: settings.size_value,
            SizeMode.BALANCE_PCT: balance * settings.size_value / _HUNDRED * settings.leverage,
        }[settings.size_mode]
        raw = notional / price

    qty = floor_to_step(raw, rules.qty_step)
    if qty < rules.min_qty:
        raise SizingError(f"количество {qty} меньше минимального {rules.min_qty}")
    if qty * price < rules.min_notional:
        raise SizingError(f"объём {qty * price:.2f} USDT меньше минимального {rules.min_notional} USDT")
    return qty


def protective_prices(
    side: Side, price: Decimal, settings: SymbolSettings, rules: InstrumentRules
) -> tuple[Decimal | None, Decimal | None]:
    """(take_profit, stop_loss) от цены входа, округлённые до шага цены."""
    sign = 1 if side is Side.LONG else -1

    def level(pct: Decimal | None, direction: int) -> Decimal | None:
        if pct is None:
            return None
        return floor_to_step(price * (1 + direction * pct / _HUNDRED), rules.tick_size)

    return level(settings.take_profit_pct, sign), level(settings.stop_loss_pct, -sign)
