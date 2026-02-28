"""TaskGraph2 node execution helpers for extraction, validation, retry, and rate limiting."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from .schema import TaskNodeOutput, TaskNodeRetry


@dataclass
class ExtractionError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class ValidationError(Exception):
    message: str

    def __str__(self) -> str:
        return self.message


class NodeExecutor:
    def __init__(
        self,
        *,
        sleep_func: Callable[[float], None] = time.sleep,
        monotonic_func: Callable[[], float] = time.monotonic,
        min_call_interval_s: float = 0.0,
    ) -> None:
        self._sleep = sleep_func
        self._monotonic = monotonic_func
        self._min_call_interval_s = max(0.0, float(min_call_interval_s))
        self._last_call_started_at: float | None = None

    def run_llm_with_retry(
        self,
        *,
        generate_text: Callable[[list[dict[str, str]]], str],
        base_messages: list[dict[str, str]],
        output_spec: TaskNodeOutput,
        retry_spec: TaskNodeRetry,
        on_retry: Callable[[int, str], None] | None = None,
        on_warning: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[str, Any]:
        last_error: Exception | None = None
        attempts = max(1, int(retry_spec.max_attempts))

        for attempt in range(1, attempts + 1):
            self._apply_rate_limit()
            messages = [dict(item) for item in base_messages]
            if last_error is not None:
                messages.append(
                    {
                        "role": "user",
                        "content": f"[repair_error]\n{last_error}",
                    }
                )

            try:
                output_text = generate_text(messages)
                extracted = extract_output(output_text, output_spec.type)
                validate_output(extracted, output_spec)
                self._emit_numeric_warnings(extracted, on_warning)
                return output_text, extracted
            except (ExtractionError, ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                if attempt >= attempts:
                    break
                if on_retry is not None:
                    on_retry(attempt, str(exc))
                backoff = max(0.0, float(retry_spec.backoff_s))
                if backoff > 0:
                    self._sleep(backoff)

        raise ValidationError(f"node execution failed after retries: {last_error}")

    def _apply_rate_limit(self) -> None:
        now = self._monotonic()
        if self._last_call_started_at is not None and self._min_call_interval_s > 0:
            elapsed = now - self._last_call_started_at
            remaining = self._min_call_interval_s - elapsed
            if remaining > 0:
                self._sleep(remaining)
                now = self._monotonic()
        self._last_call_started_at = now

    def _emit_numeric_warnings(self, payload: Any, on_warning: Callable[[dict[str, Any]], None] | None) -> None:
        if on_warning is None:
            return
        for item in _iter_numeric_anomalies(payload):
            on_warning(item)


def extract_output(text: str, expected_type: str) -> Any:
    if expected_type != "json":
        return text

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for open_char, close_char in (("{", "}"), ("[", "]")):
        start = text.find(open_char)
        end = text.rfind(close_char)
        if start == -1 or end == -1 or end <= start:
            continue
        candidate = text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    raise ExtractionError(
        "json extraction failed: "
        f"length={len(text)}, object_start={text.find('{')}, object_end={text.rfind('}')}, "
        f"array_start={text.find('[')}, array_end={text.rfind(']')}"
    )


def validate_output(output: Any, output_spec: TaskNodeOutput) -> None:
    schema = output_spec.schema or {}
    required_keys = schema.get("required_keys")
    type_map = schema.get("types")

    if required_keys is not None:
        if not isinstance(output, dict):
            raise ValidationError("required_keys requires dict output")
        missing = [key for key in required_keys if key not in output]
        if missing:
            raise ValidationError(f"missing required keys: {missing}")

    if type_map is not None:
        if not isinstance(output, dict):
            raise ValidationError("types validation requires dict output")
        for key, expected in dict(type_map).items():
            if key not in output:
                continue
            if not _matches_type(output[key], str(expected)):
                raise ValidationError(
                    f"type mismatch for key='{key}': expected={expected}, actual={type(output[key]).__name__}"
                )


def _matches_type(value: Any, expected: str) -> bool:
    expected_normalized = expected.strip().lower()
    if expected_normalized == "str":
        expected_normalized = "string"
    if expected_normalized == "int":
        expected_normalized = "integer"
    if expected_normalized == "bool":
        expected_normalized = "boolean"

    checks: dict[str, Callable[[Any], bool]] = {
        "string": lambda v: isinstance(v, str),
        "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "boolean": lambda v: isinstance(v, bool),
        "object": lambda v: isinstance(v, dict),
        "array": lambda v: isinstance(v, list),
        "null": lambda v: v is None,
    }
    check = checks.get(expected_normalized)
    if check is None:
        return True
    return check(value)


def _iter_numeric_anomalies(payload: Any, path: str = "$"):
    if isinstance(payload, bool) or payload is None:
        return
    if isinstance(payload, (int, float)):
        value = float(payload)
        if math.isnan(value) or math.isinf(value) or abs(value) > 1e18:
            yield {
                "event": "numeric_anomaly_warning",
                "path": path,
                "value": repr(payload),
                "reason": "nan_or_inf_or_out_of_bound",
            }
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield from _iter_numeric_anomalies(value, f"{path}.{key}")
        return
    if isinstance(payload, list):
        for idx, value in enumerate(payload):
            yield from _iter_numeric_anomalies(value, f"{path}[{idx}]")
