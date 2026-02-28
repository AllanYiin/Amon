"""Reusable TaskGraph2 node execution helpers (extract/validate/retry/rate-limit)."""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from typing import Any, Callable

from .schema import TaskNode, TaskNodeOutput


class OutputExtractionError(ValueError):
    """Raised when output extraction fails with diagnostic context."""


class ValidationError(ValueError):
    """Raised when output validation fails."""


@dataclass
class NodeExecutionResult:
    raw_text: str
    extracted_output: Any


class NodeExecutor:
    def __init__(
        self,
        *,
        sleep_func: Callable[[float], None] | None = None,
        monotonic_func: Callable[[], float] | None = None,
        min_call_interval_s: float = 0.0,
    ) -> None:
        self._sleep = sleep_func or time.sleep
        self._monotonic = monotonic_func or time.monotonic
        self._min_call_interval_s = max(0.0, float(min_call_interval_s))
        self._last_call_at: float | None = None

    def execute_llm_node(
        self,
        *,
        node: TaskNode,
        base_messages: list[dict[str, str]],
        invoke_llm: Callable[[list[dict[str, str]]], str],
        append_event: Callable[[dict[str, Any]], None],
    ) -> NodeExecutionResult:
        repair_error: str | None = None
        max_attempts = max(1, int(node.retry.max_attempts))

        for attempt in range(1, max_attempts + 1):
            try:
                self._apply_rate_limit()
                messages = list(base_messages)
                if repair_error:
                    messages = self._append_repair_error(messages, repair_error)
                raw_text = invoke_llm(messages)
                extracted = extract_output(raw_text, node.output)
                validate_output(extracted, node.output)
                for warning in detect_numeric_anomalies(extracted):
                    append_event(
                        {
                            "event": "numeric_anomaly_warning",
                            "node_id": node.id,
                            "warning": warning,
                        }
                    )
                return NodeExecutionResult(raw_text=raw_text, extracted_output=extracted)
            except Exception as exc:  # noqa: BLE001
                repair_error = str(exc)
                if attempt >= max_attempts:
                    raise
                append_event(
                    {
                        "event": "node_retry",
                        "node_id": node.id,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "repair_error": repair_error,
                    }
                )
                backoff = max(float(node.retry.backoff_s), 0.0) * attempt
                self._sleep(backoff)

        raise RuntimeError("unreachable")

    def _apply_rate_limit(self) -> None:
        if self._min_call_interval_s <= 0:
            self._last_call_at = self._monotonic()
            return
        now = self._monotonic()
        if self._last_call_at is not None:
            delta = now - self._last_call_at
            wait = self._min_call_interval_s - delta
            if wait > 0:
                self._sleep(wait)
                now = self._monotonic()
        self._last_call_at = now

    def _append_repair_error(self, messages: list[dict[str, str]], repair_error: str) -> list[dict[str, str]]:
        patch = "\n\n[repair_error]\n" + repair_error
        if messages:
            tail = dict(messages[-1])
            if tail.get("role") == "user":
                tail["content"] = str(tail.get("content") or "") + patch
                return [*messages[:-1], tail]
        return [*messages, {"role": "user", "content": patch.strip()}]


def extract_output(raw_text: str, output_spec: TaskNodeOutput) -> Any:
    expected_type = output_spec.type
    if expected_type != "json":
        return raw_text

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw_text.find(open_ch)
        end = raw_text.rfind(close_ch)
        if start == -1 or end == -1 or end <= start:
            continue
        candidate = raw_text[start : end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise OutputExtractionError(
                f"json extraction failed: len={len(raw_text)}, start={start}, end={end}, candidate_len={len(candidate)}"
            ) from exc

    raise OutputExtractionError(
        f"json extraction failed: len={len(raw_text)}, start=-1, end=-1, candidate_len=0"
    )


def validate_output(output: Any, output_spec: TaskNodeOutput) -> None:
    schema = output_spec.schema or {}
    required_keys = schema.get("required_keys") or {}
    if not required_keys:
        return
    if not isinstance(output, dict):
        raise ValidationError("output must be object when required_keys is configured")

    type_map: dict[str, type[Any] | tuple[type[Any], ...]] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "object": dict,
        "array": list,
    }

    for key, expected in required_keys.items():
        if key not in output:
            raise ValidationError(f"missing required key: {key}")
        if expected is None:
            continue
        expected_type = type_map.get(str(expected))
        if expected_type is None:
            continue
        value = output[key]
        if str(expected) == "number" and isinstance(value, bool):
            raise ValidationError(f"key '{key}' expected number, got bool")
        if not isinstance(value, expected_type):
            raise ValidationError(f"key '{key}' expected {expected}, got {type(value).__name__}")


def detect_numeric_anomalies(payload: Any) -> list[str]:
    warnings: list[str] = []

    def _walk(value: Any, path: str) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int):
            if abs(value) > 1e18:
                warnings.append(f"{path}: unusually large integer {value}")
            return
        if isinstance(value, float):
            if math.isnan(value):
                warnings.append(f"{path}: NaN detected")
            elif math.isinf(value):
                warnings.append(f"{path}: Infinity detected")
            elif abs(value) > 1e18:
                warnings.append(f"{path}: unusually large float {value}")
            return
        if isinstance(value, dict):
            for key, child in value.items():
                _walk(child, f"{path}.{key}")
            return
        if isinstance(value, list):
            for index, child in enumerate(value):
                _walk(child, f"{path}[{index}]")

    _walk(payload, "$")
    return warnings
