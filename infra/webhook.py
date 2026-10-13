"""HTTP-приём сигналов TradingView и последовательное исполнение в фоне.

TradingView ждёт ответ ~3 секунды, поэтому webhook только проверяет и ставит сигнал
в очередь, а ордера исполняет один фоновый воркер — строго по порядку.
"""

import asyncio
import hmac
import json
import logging
from collections import OrderedDict
from collections.abc import Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.signals import SignalError, parse_signal
from contracts.models import Signal

log = logging.getLogger("webhook")


class _RecentIds:
    """Последние id сигналов — защита от повторной обработки."""

    def __init__(self, limit: int = 1000):
        self._ids: OrderedDict[str, None] = OrderedDict()
        self._limit = limit

    def seen(self, signal_id: str) -> bool:
        if signal_id in self._ids:
            return True
        self._ids[signal_id] = None
        if len(self._ids) > self._limit:
            self._ids.popitem(last=False)
        return False


def create_webhook_app(secret: str, handle: Callable[[Signal], None], mode: str) -> FastAPI:
    queue: asyncio.Queue[Signal] = asyncio.Queue()
    recent = _RecentIds()

    async def worker() -> None:
        while True:
            signal = await queue.get()
            try:
                await asyncio.to_thread(handle, signal)
            except Exception:
                log.exception("Ошибка при исполнении сигнала %s %s", signal.action.value, signal.symbol)
            finally:
                queue.task_done()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        task = asyncio.create_task(worker())
        yield
        task.cancel()

    api = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @api.get("/health")
    async def health() -> dict:
        return {"status": "ok", "mode": mode}

    @api.post("/webhook")
    async def webhook(request: Request) -> JSONResponse:
        try:
            payload = json.loads(await request.body())
        except json.JSONDecodeError:
            return _reply(400, "тело запроса должно быть JSON")
        if not isinstance(payload, dict):
            return _reply(400, "тело запроса должно быть JSON-объектом")

        if not hmac.compare_digest(str(payload.get("secret", "")).encode(), secret.encode()):
            log.warning("Отклонён запрос с неверным secret от %s", request.client.host if request.client else "?")
            return _reply(401, "неверный secret")

        try:
            signal = parse_signal(payload)
        except SignalError as e:
            log.warning("Некорректный сигнал: %s", e)
            return _reply(400, str(e))

        if signal.signal_id and recent.seen(signal.signal_id):
            log.info("Повтор сигнала id=%s пропущен", signal.signal_id)
            return _reply(200, "duplicate")

        log.info("Получен сигнал: %s %s", signal.action.value.upper(), signal.symbol)
        queue.put_nowait(signal)
        return _reply(200, "accepted")

    return api


def _reply(status: int, message: str) -> JSONResponse:
    return JSONResponse({"status": message} if status == 200 else {"error": message}, status_code=status)
