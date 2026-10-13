# Архитектура

## Зоны

| Каталог | Зона | Что внутри |
|---|---|---|
| `contracts/` | контракт (leaf) | типы данных (`models.py`) и порты (`ports.py`); зависит только от stdlib |
| `app/` | **прикладной код** | разбор сигналов, расчёт размера и TP/SL, торговые решения |
| `infra/` | **каркас** | Bybit API, HTTP-webhook и очередь, загрузка конфига, логирование |
| `bootstrap.py` | composition root | создание и связывание всех объектов |
| `main.py` | точка входа | `bootstrap.build()` → `uvicorn.run()` |
| `tools/` | утилиты | отправка тестового сигнала |

## Основные сущности

| Сущность | Где | Роль |
|---|---|---|
| `Signal` | contracts | нормализованный сигнал: пара, действие (`long`/`short`/`close`), id |
| `SymbolSettings` | contracts | итоговые настройки пары: defaults с наложенными переопределениями |
| `ExchangePort` | contracts | узкий порт биржи: правила инструмента, цена, баланс, позиция, плечо, рыночный ордер |
| `SettingsPort` | contracts | список разрешённых пар и их настройки |
| `parse_signal` | app/signals | JSON TradingView → `Signal`; синонимы действий, нормализация тикера |
| `order_qty`, `protective_prices` | app/sizing | количество по режиму размера с округлением по `qtyStep`; уровни TP/SL по `tickSize` |
| `Trader` | app/trader | решает, что делать с позицией: открыть, закрыть, перевернуть или пропустить |
| `BybitExchange` | infra/bybit | реализация `ExchangePort` на pybit; настройка аккаунта при старте, кэш правил и плеча |
| `StaticSettings`, `load_config` | infra/config | валидация `config.yaml` (pydantic), слияние defaults и настроек пар |
| `create_webhook_app` | infra/webhook | FastAPI: проверка secret, разбор, защита от дублей, очередь с одним воркером |

## Порядок сборки (bootstrap.build)

1. `setup_logging()`
2. `load_config(path)` → `AppConfig`
3. `BybitExchange(keys, demo)` → `prepare_account(margin_mode)`: сверка часов с сервером Bybit, проверка ключа, режим one-way, режим маржи
4. `Trader(exchange, StaticSettings(symbols))` → `check_ready()`: баланс, существование пар, лимит плеча
5. `create_webhook_app(secret, trader.handle, mode)` → FastAPI-приложение для `uvicorn`

## Граф зависимостей

```
main ──► bootstrap ──► infra ──► app ──► contracts
                │                  ▲
                └──────────────────┘
infra ──► contracts
```

- `contracts` никого не импортирует.
- `app` зависит только от `contracts`: ничего не знает о pybit, HTTP и YAML.
- `infra/webhook` использует `app.signals.parse_signal`. Формат сигнала относится к прикладной логике, поэтому разбор живёт в `app`.
- Циклов нет.

## Поток сигнала

```
POST /webhook ─► JSON ─► secret ─► parse_signal ─► дубль? ─► queue ─► 200 OK
                                                              │
                                    воркер (to_thread) ◄──────┘
                                         │
                                  Trader.handle(signal)
                                         │
                           ExchangePort: position / set_leverage / market_order
```

## Тесты

`tests/fakes.py` содержит `FakeExchange` и `FakeSettings`. Логика `app/` тестируется без сети.
Webhook тестируется через `TestClient`, конфиг — на `config.example.yaml`.
