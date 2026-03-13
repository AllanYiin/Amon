"""Logging helpers for Amon."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class AutoClosingFileHandler(logging.FileHandler):
    def __init__(self, filename: Path, *, encoding: str) -> None:
        super().__init__(filename, encoding=encoding, delay=True)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if self.stream is None:
                Path(self.baseFilename).parent.mkdir(parents=True, exist_ok=True)
                self.stream = self._open()
            super().emit(record)
        finally:
            self.close()


def _reset_logger_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.flush()
        except Exception:
            pass
        handler.close()


def setup_logger(name: str, log_dir: Path) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        _reset_logger_handlers(logger)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "amon.log"

    logger.setLevel(logging.INFO)
    logger.propagate = False
    formatter = logging.Formatter(LOG_FORMAT)
    json_formatter = JsonFormatter()

    file_handler = AutoClosingFileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger


def setup_billing_logger(log_dir: Path) -> logging.Logger:
    logger = logging.getLogger("amon.billing")
    if logger.handlers:
        _reset_logger_handlers(logger)

    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "billing.log"

    logger.setLevel(logging.INFO)
    logger.propagate = False
    json_formatter = JsonFormatter()

    file_handler = AutoClosingFileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(json_formatter)

    logger.addHandler(file_handler)
    return logger
