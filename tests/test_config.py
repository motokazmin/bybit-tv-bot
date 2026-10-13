from decimal import Decimal
from pathlib import Path

import pytest

from contracts.models import OnOpposite, SizeMode
from infra.config import ConfigError, load_config

EXAMPLE = Path(__file__).parent.parent / "config.example.yaml"


def example_with_secret(tmp_path, secret: str = "my-real-secret-123") -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        EXAMPLE.read_text(encoding="utf-8").replace("придумайте-длинный-секрет", secret), encoding="utf-8"
    )
    return path


def test_example_config_loads_and_merges_defaults(tmp_path):
    config = load_config(example_with_secret(tmp_path))

    btc, eth = config.symbols["BTCUSDT"], config.symbols["ETHUSDT"]
    assert (btc.leverage, btc.size_mode, btc.size_value) == (Decimal("5"), SizeMode.MARGIN_USDT, Decimal("20"))
    assert btc.on_opposite is OnOpposite.REVERSE
    assert (eth.leverage, eth.size_mode, eth.take_profit_pct) == (Decimal("10"), SizeMode.BALANCE_PCT, Decimal("3"))


def test_unknown_field_is_reported(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(EXAMPLE.read_text(encoding="utf-8").replace("leverage: 5", "leverag: 5"), encoding="utf-8")

    with pytest.raises(ConfigError, match="leverag"):
        load_config(path)


def test_placeholder_secret_is_rejected():
    with pytest.raises(ConfigError, match="secret"):
        load_config(EXAMPLE)


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="не найден"):
        load_config(tmp_path / "config.yaml")
