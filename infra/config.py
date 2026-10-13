"""Загрузка config.yaml: валидация и слияние настроек по умолчанию с настройками пар."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from contracts.models import OnOpposite, SizeMode, SymbolSettings


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Size(_Strict):
    mode: SizeMode
    value: Decimal = Field(gt=0)


class _Trade(_Strict):
    leverage: Decimal | None = Field(default=None, ge=1)
    size: _Size | None = None
    take_profit_pct: Decimal | None = Field(default=None, gt=0)
    stop_loss_pct: Decimal | None = Field(default=None, gt=0)
    on_opposite: OnOpposite | None = None


class _Bybit(_Strict):
    api_key: str = Field(min_length=1)
    api_secret: str = Field(min_length=1)


class _Webhook(_Strict):
    secret: str = Field(min_length=8)
    port: int = 8000

    @field_validator("secret")
    @classmethod
    def _ascii_secret(cls, value: str) -> str:
        # Заодно отсекает незаменённую заглушку из config.example.yaml (она на кириллице).
        if not all("!" <= ch <= "~" for ch in value):
            raise ValueError("только латиница, цифры и знаки без пробелов — придумайте свой секрет")
        return value


class _Config(_Strict):
    mode: Literal["demo", "live"]
    margin_mode: Literal["isolated", "cross"]
    bybit: _Bybit
    webhook: _Webhook
    defaults: _Trade
    symbols: dict[str, _Trade | None] = Field(min_length=1)


class AppConfig(BaseModel):
    mode: Literal["demo", "live"]
    margin_mode: Literal["isolated", "cross"]
    api_key: str
    api_secret: str
    webhook_secret: str
    port: int
    symbols: dict[str, SymbolSettings]


class ConfigError(Exception):
    pass


class StaticSettings:
    """SettingsPort поверх загруженного конфига."""

    def __init__(self, symbols: dict[str, SymbolSettings]):
        self._symbols = symbols

    def symbols(self) -> list[str]:
        return list(self._symbols)

    def for_symbol(self, symbol: str) -> SymbolSettings | None:
        return self._symbols.get(symbol)


def load_config(path: Path) -> AppConfig:
    if not path.is_file():
        # Docker создаёт папку на месте отсутствующего файла, поэтому проверяем именно файл.
        raise ConfigError(f"файл настроек {path} не найден — скопируйте config.example.yaml в config.yaml")
    try:
        raw = _Config.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except ValidationError as e:
        raise ConfigError(f"ошибка в {path}:\n{e}") from None

    return AppConfig(
        mode=raw.mode,
        margin_mode=raw.margin_mode,
        api_key=raw.bybit.api_key,
        api_secret=raw.bybit.api_secret,
        webhook_secret=raw.webhook.secret,
        port=raw.webhook.port,
        symbols={name.upper(): _merge(name, raw.defaults, override) for name, override in raw.symbols.items()},
    )


def _merge(symbol: str, defaults: _Trade, override: _Trade | None) -> SymbolSettings:
    merged = _Trade.model_validate(
        defaults.model_dump(exclude_unset=True) | (override.model_dump(exclude_unset=True) if override else {})
    )
    if merged.leverage is None or merged.size is None:
        raise ConfigError(f"{symbol}: не заданы leverage или size (ни в defaults, ни для пары)")
    return SymbolSettings(
        leverage=merged.leverage,
        size_mode=merged.size.mode,
        size_value=merged.size.value,
        take_profit_pct=merged.take_profit_pct,
        stop_loss_pct=merged.stop_loss_pct,
        on_opposite=merged.on_opposite or OnOpposite.REVERSE,
    )
