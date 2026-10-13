import time

import pytest
from fastapi.testclient import TestClient

from infra.webhook import create_webhook_app

SECRET = "test-secret-123"


@pytest.fixture
def received():
    return []


@pytest.fixture
def client(received):
    with TestClient(create_webhook_app(SECRET, received.append, "demo")) as c:
        yield c


def wait_for(received, count):
    deadline = time.monotonic() + 2
    while len(received) < count and time.monotonic() < deadline:
        time.sleep(0.01)


def test_health(client):
    assert client.get("/health").json() == {"status": "ok", "mode": "demo"}


def test_accepts_valid_signal(client, received):
    response = client.post("/webhook", json={"secret": SECRET, "symbol": "BYBIT:BTCUSDT.P", "action": "long"})

    assert response.status_code == 200
    wait_for(received, 1)
    assert received[0].symbol == "BTCUSDT"


def test_rejects_non_ascii_secret(client, received):
    response = client.post("/webhook", json={"secret": "секрет", "symbol": "BTCUSDT", "action": "long"})

    assert response.status_code == 401
    assert received == []


def test_rejects_wrong_secret(client, received):
    response = client.post("/webhook", json={"secret": "wrong", "symbol": "BTCUSDT", "action": "long"})

    assert response.status_code == 401
    assert received == []


def test_rejects_invalid_json(client):
    assert client.post("/webhook", content="long BTCUSDT").status_code == 400


def test_rejects_unknown_action(client):
    response = client.post("/webhook", json={"secret": SECRET, "symbol": "BTCUSDT", "action": "moon"})

    assert response.status_code == 400


def test_duplicate_signal_processed_once(client, received):
    payload = {"secret": SECRET, "symbol": "BTCUSDT", "action": "long", "id": "abc"}

    client.post("/webhook", json=payload)
    second = client.post("/webhook", json=payload)

    assert second.json() == {"status": "duplicate"}
    wait_for(received, 1)
    assert len(received) == 1
