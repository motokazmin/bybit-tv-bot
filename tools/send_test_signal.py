"""Отправить боту тестовый сигнал — как будто от TradingView.

    python tools/send_test_signal.py long BTCUSDT
    python tools/send_test_signal.py close BTCUSDT --url https://xxxx.lhr.life/webhook
"""

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("action", help="long | short | close")
    parser.add_argument("symbol", help="например BTCUSDT")
    parser.add_argument("--url", help="адрес webhook (по умолчанию http://localhost:<port>/webhook)")
    parser.add_argument("--config", default=os.environ.get("CONFIG", "config.yaml"))
    args = parser.parse_args()

    webhook = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))["webhook"]
    url = args.url or f"http://localhost:{webhook.get('port', 8000)}/webhook"
    body = json.dumps({"secret": webhook["secret"], "symbol": args.symbol, "action": args.action}).encode()

    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            print(response.status, response.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode())


if __name__ == "__main__":
    main()
