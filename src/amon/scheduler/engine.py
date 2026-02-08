"""Scheduler engine for Amon."""

from __future__ import annotations

import json
import logging
import os
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from amon.events import emit_event
from amon.fs.atomic import atomic_write_text


logger = logging.getLogger(__name__)


_EVENT_EMITTER = Callable[[dict[str, Any]], str]


@dataclass
class ScheduleTickResult:
    fired: list[dict[str, Any]]
    updated: bool


def tick(
    now: datetime | None = None,
    *,
    data_dir: Path | None = None,
    event_emitter: _EVENT_EMITTER | None = None,
) -> list[dict[str, Any]]:
    current_time = (now or datetime.now().astimezone()).astimezone()
    emitter = event_emitter or emit_event
    payload = load_schedules(data_dir=data_dir)
    schedules = payload.get("schedules", [])
    fired_events: list[dict[str, Any]] = []
    updated = False

    for schedule in schedules:
        try:
            result = _process_schedule(schedule, current_time, emitter)
        except Exception as exc:  # noqa: BLE001
            logger.error("排程 tick 失敗：%s", exc, exc_info=True)
            continue
        if result.fired:
            fired_events.extend(result.fired)
        if result.updated:
            updated = True

    if updated:
        payload["schedules"] = schedules
        write_schedules(payload, data_dir=data_dir)
    return fired_events


def load_schedules(*, data_dir: Path | None = None) -> dict[str, Any]:
    path = _resolve_schedules_path(data_dir)
    if not path.exists():
        return {"schedules": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("讀取排程資料失敗：%s", exc, exc_info=True)
        raise ValueError("排程資料讀取失敗") from exc


def write_schedules(payload: dict[str, Any], *, data_dir: Path | None = None) -> None:
    path = _resolve_schedules_path(data_dir)
    try:
        atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.error("寫入排程資料失敗：%s", exc, exc_info=True)
        raise


def _resolve_schedules_path(data_dir: Path | None = None) -> Path:
    if data_dir:
        return data_dir / "schedules" / "schedules.json"
    env_path = os.environ.get("AMON_HOME")
    if env_path:
        return Path(env_path).expanduser() / "schedules" / "schedules.json"
    return Path("~/.amon").expanduser() / "schedules" / "schedules.json"


def _process_schedule(
    schedule: dict[str, Any],
    current_time: datetime,
    emitter: _EVENT_EMITTER,
) -> ScheduleTickResult:
    if not schedule.get("enabled", True):
        return ScheduleTickResult(fired=[], updated=False)

    schedule_id = str(schedule.get("schedule_id", "")).strip()
    if not schedule_id:
        logger.warning("排程缺少 schedule_id，已略過")
        return ScheduleTickResult(fired=[], updated=False)

    schedule_type = str(schedule.get("type") or schedule.get("schedule_type") or "").strip().lower()
    if not schedule_type:
        schedule_type = _infer_schedule_type(schedule)

    if schedule_type == "interval":
        return _process_interval(schedule, current_time, emitter)
    if schedule_type in {"one_shot", "oneshot", "one-shot"}:
        return _process_one_shot(schedule, current_time, emitter)
    if schedule_type == "cron":
        return _process_cron(schedule, current_time, emitter)

    logger.warning("未知的排程類型：%s", schedule_type)
    return ScheduleTickResult(fired=[], updated=False)


def _infer_schedule_type(schedule: dict[str, Any]) -> str:
    if schedule.get("interval_seconds") is not None:
        return "interval"
    if schedule.get("run_at") is not None:
        return "one_shot"
    if schedule.get("cron") is not None:
        return "cron"
    return "interval"


def _process_interval(
    schedule: dict[str, Any],
    current_time: datetime,
    emitter: _EVENT_EMITTER,
) -> ScheduleTickResult:
    interval_seconds = _read_number(schedule.get("interval_seconds"))
    if not interval_seconds or interval_seconds <= 0:
        logger.warning("interval 排程缺少 interval_seconds")
        return ScheduleTickResult(fired=[], updated=False)

    due_at = _resolve_next_fire_at(schedule, current_time, interval_seconds)
    fired_events: list[dict[str, Any]] = []
    updated = False
    if due_at and current_time >= due_at:
        if _is_misfire(schedule, current_time, due_at):
            schedule["last_misfire_at"] = current_time.isoformat(timespec="seconds")
            updated = True
        else:
            fired_events.append(_emit_schedule_fired(schedule, due_at, current_time, emitter))
            schedule["last_fire_at"] = current_time.isoformat(timespec="seconds")
            updated = True
        next_fire = _advance_interval(due_at, current_time, interval_seconds)
        schedule["next_fire_at"] = _apply_jitter(next_fire, schedule)
        schedule["updated_at"] = current_time.isoformat(timespec="seconds")
        updated = True

    return ScheduleTickResult(fired=fired_events, updated=updated)


def _process_one_shot(
    schedule: dict[str, Any],
    current_time: datetime,
    emitter: _EVENT_EMITTER,
) -> ScheduleTickResult:
    if schedule.get("status") in {"completed", "misfired"}:
        return ScheduleTickResult(fired=[], updated=False)

    due_at = _parse_datetime(schedule.get("run_at")) or _parse_datetime(schedule.get("next_fire_at"))
    if not due_at:
        due_at = _parse_datetime(schedule.get("created_at")) or current_time
    fired_events: list[dict[str, Any]] = []
    updated = False

    if current_time >= due_at:
        if _is_misfire(schedule, current_time, due_at):
            schedule["status"] = "misfired"
            schedule["last_misfire_at"] = current_time.isoformat(timespec="seconds")
        else:
            fired_events.append(_emit_schedule_fired(schedule, due_at, current_time, emitter))
            schedule["status"] = "completed"
            schedule["last_fire_at"] = current_time.isoformat(timespec="seconds")
        schedule["next_fire_at"] = None
        schedule["enabled"] = False
        schedule["updated_at"] = current_time.isoformat(timespec="seconds")
        updated = True

    return ScheduleTickResult(fired=fired_events, updated=updated)


def _process_cron(
    schedule: dict[str, Any],
    current_time: datetime,
    emitter: _EVENT_EMITTER,
) -> ScheduleTickResult:
    cron_expr = str(schedule.get("cron", "")).strip()
    if not cron_expr:
        logger.warning("cron 排程缺少 cron 表達式")
        return ScheduleTickResult(fired=[], updated=False)

    try:
        due_at = _parse_datetime(schedule.get("next_fire_at"))
        if not due_at:
            due_at = _next_cron_after(cron_expr, current_time - timedelta(minutes=1))
    except ValueError as exc:
        logger.error("解析 cron 失敗：%s", exc, exc_info=True)
        schedule["status"] = "invalid"
        schedule["updated_at"] = current_time.isoformat(timespec="seconds")
        return ScheduleTickResult(fired=[], updated=True)

    fired_events: list[dict[str, Any]] = []
    updated = False
    if current_time >= due_at:
        if _is_misfire(schedule, current_time, due_at):
            schedule["last_misfire_at"] = current_time.isoformat(timespec="seconds")
        else:
            fired_events.append(_emit_schedule_fired(schedule, due_at, current_time, emitter))
            schedule["last_fire_at"] = current_time.isoformat(timespec="seconds")
        try:
            next_fire = _next_cron_after(cron_expr, max(current_time, due_at))
            schedule["next_fire_at"] = _apply_jitter(next_fire, schedule)
        except ValueError as exc:
            logger.error("計算下一次 cron 失敗：%s", exc, exc_info=True)
            schedule["status"] = "invalid"
            schedule["next_fire_at"] = None
        schedule["updated_at"] = current_time.isoformat(timespec="seconds")
        updated = True
    else:
        next_fire_at = due_at.isoformat(timespec="seconds")
        if schedule.get("next_fire_at") != next_fire_at:
            schedule["next_fire_at"] = next_fire_at
            schedule["updated_at"] = current_time.isoformat(timespec="seconds")
            updated = True

    return ScheduleTickResult(fired=fired_events, updated=updated)


def _emit_schedule_fired(
    schedule: dict[str, Any],
    scheduled_for: datetime,
    fired_at: datetime,
    emitter: _EVENT_EMITTER,
) -> dict[str, Any]:
    payload = {
        "schedule_id": schedule.get("schedule_id"),
        "template_id": schedule.get("template_id"),
        "vars": schedule.get("vars") or {},
        "scheduled_for": scheduled_for.isoformat(timespec="seconds"),
        "fired_at": fired_at.isoformat(timespec="seconds"),
    }
    event = {
        "type": "schedule.fired",
        "scope": "schedule",
        "actor": "system",
        "payload": payload,
        "risk": "low",
    }
    event_id = emitter(event)
    payload["event_id"] = event_id
    return payload


def _resolve_next_fire_at(
    schedule: dict[str, Any],
    current_time: datetime,
    interval_seconds: float,
) -> datetime | None:
    next_fire = _parse_datetime(schedule.get("next_fire_at"))
    if next_fire:
        return next_fire

    last_fire = _parse_datetime(schedule.get("last_fire_at"))
    if last_fire:
        return last_fire + timedelta(seconds=interval_seconds)

    created_at = _parse_datetime(schedule.get("created_at"))
    if created_at:
        return created_at + timedelta(seconds=interval_seconds)
    return current_time


def _advance_interval(
    due_at: datetime,
    current_time: datetime,
    interval_seconds: float,
) -> datetime:
    next_fire = due_at + timedelta(seconds=interval_seconds)
    while next_fire <= current_time:
        next_fire += timedelta(seconds=interval_seconds)
    return next_fire


def _is_misfire(schedule: dict[str, Any], current_time: datetime, due_at: datetime) -> bool:
    grace = _read_number(schedule.get("misfire_grace_seconds")) or 0
    if grace <= 0:
        return False
    return (current_time - due_at).total_seconds() > grace


def _apply_jitter(next_fire: datetime, schedule: dict[str, Any]) -> str:
    jitter = _read_number(schedule.get("jitter_seconds")) or 0
    if jitter <= 0:
        return next_fire.isoformat(timespec="seconds")
    offset = random.uniform(0, jitter)
    return (next_fire + timedelta(seconds=offset)).isoformat(timespec="seconds")


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone()
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=datetime.now().astimezone().tzinfo)
        return parsed.astimezone()
    return None


def _read_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _next_cron_after(expr: str, base: datetime) -> datetime:
    minute_set, hour_set, dom_set, month_set, dow_set = _parse_cron_expression(expr)
    candidate = base.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 366):
        if (
            candidate.minute in minute_set
            and candidate.hour in hour_set
            and candidate.day in dom_set
            and candidate.month in month_set
            and _cron_weekday(candidate) in dow_set
        ):
            return candidate
        candidate += timedelta(minutes=1)
    raise ValueError("找不到下一次 cron 時間")


def _parse_cron_expression(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    parts = [part for part in expr.split() if part.strip()]
    if len(parts) != 5:
        raise ValueError("cron 格式需為 5 欄位")
    minute = _parse_cron_field(parts[0], 0, 59, "minute")
    hour = _parse_cron_field(parts[1], 0, 23, "hour")
    dom = _parse_cron_field(parts[2], 1, 31, "day_of_month")
    month = _parse_cron_field(parts[3], 1, 12, "month")
    dow = _parse_cron_field(parts[4], 0, 6, "day_of_week")
    return minute, hour, dom, month, dow


def _parse_cron_field(field: str, min_value: int, max_value: int, label: str) -> set[int]:
    field = field.strip()
    if field == "*":
        return set(range(min_value, max_value + 1))
    if field.startswith("*/"):
        step = int(field[2:])
        if step <= 0:
            raise ValueError(f"cron {label} step 無效")
        return set(range(min_value, max_value + 1, step))
    if field.isdigit():
        value = int(field)
        if label == "day_of_week" and value == 7:
            value = 0
        if not min_value <= value <= max_value:
            raise ValueError(f"cron {label} 超出範圍")
        return {value}
    raise ValueError(f"cron {label} 不支援格式：{field}")


def _cron_weekday(candidate: datetime) -> int:
    return (candidate.weekday() + 1) % 7
