import logging
import os
import sys
from pathlib import Path

import uvicorn

import bootstrap
from infra.bybit import ExchangeAccessError
from infra.config import ConfigError


def main() -> None:
    try:
        app, port = bootstrap.build(Path(os.environ.get("CONFIG", "config.yaml")))
    except (ConfigError, ExchangeAccessError) as e:
        sys.exit(f"Бот не запущен: {e}")
    except Exception as e:
        logging.getLogger("bot").exception("Бот не запущен: %s", e)
        sys.exit(1)
    uvicorn.run(app, host="0.0.0.0", port=port, log_config=None)


if __name__ == "__main__":
    main()
