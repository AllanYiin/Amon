"""FastAPI application for shared sandbox runner."""

from __future__ import annotations

import logging
import secrets
import sys
from typing import Any

from .config import RunnerSettings, load_settings
from .runner import SandboxRunner

logger = logging.getLogger("amon_sandbox_runner")


def create_app(settings: RunnerSettings | None = None):
    try:
        from fastapi import FastAPI, Header, HTTPException
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("請先安裝 sandbox-runner 依賴：pip install -e .[sandbox-runner]") from exc

    app = FastAPI(title="Amon Sandbox Runner", version="0.1.0")
    runtime_settings = settings or load_settings()
    runner = SandboxRunner(runtime_settings)

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "amon-sandbox-runner",
            "version": "0.1.0",
            **runner.health_snapshot(),
        }

    @app.post("/run")
    def run(payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        if runtime_settings.api_key:
            expected = f"Bearer {runtime_settings.api_key}"
            if not authorization or not secrets.compare_digest(authorization, expected):
                raise HTTPException(status_code=401, detail="unauthorized")

        try:
            return runner.run(payload)  # type: ignore[arg-type]
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("sandbox run 發生未預期錯誤")
            raise HTTPException(status_code=500, detail="runner internal error") from exc

    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    try:
        import uvicorn

        settings = load_settings()
        app = create_app(settings)
        uvicorn.run(app, host=settings.host, port=settings.port)
    except Exception as exc:  # noqa: BLE001
        logger.exception("runner 啟動失敗")
        print(f"runner 啟動失敗：{exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
