"""Command executor for chat-driven actions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from amon.chat.session_store import append_event
from amon.core import AmonCore
from amon.fs.safety import make_change_plan

from .registry import get_command, register_command


@dataclass(frozen=True)
class CommandPlan:
    name: str
    args: dict[str, Any]
    project_id: str
    chat_id: str
    metadata: dict[str, Any] = field(default_factory=dict)


_DEFAULT_REGISTERED = False


def execute(plan: CommandPlan, confirmed: bool) -> dict[str, Any]:
    _ensure_default_commands()
    definition = get_command(plan.name)
    if not definition:
        raise ValueError(f"找不到 command：{plan.name}")

    if definition.schema.get("requires_confirm") and not confirmed:
        return {
            "status": "confirm_required",
            "plan_card": _build_plan_card(plan.name, plan.args),
            "command": plan.name,
        }

    core = AmonCore()
    core.ensure_base_structure()
    try:
        result = definition.handler(core, plan)
    except Exception as exc:  # noqa: BLE001
        _append_plan_event(
            plan,
            event_type="plan_failed",
            text=f"{plan.name} 執行失敗：{exc}",
            extra={"error": str(exc)},
        )
        return {"status": "failed", "error": str(exc)}

    _append_plan_event(
        plan,
        event_type="plan_executed",
        text=f"{plan.name} 已完成",
        extra=_extract_event_payload(result),
    )
    return {"status": "ok", "result": result}


def _ensure_default_commands() -> None:
    global _DEFAULT_REGISTERED
    if _DEFAULT_REGISTERED:
        return

    register_command(
        "projects.create",
        {"inputs": {"name": "string"}},
        _handle_projects_create,
    )
    register_command(
        "projects.list",
        {"inputs": {}},
        _handle_projects_list,
    )
    register_command(
        "projects.delete",
        {"inputs": {"project_id": "string"}, "requires_confirm": True},
        _handle_projects_delete,
    )
    register_command(
        "projects.restore",
        {"inputs": {"trash_id": "string"}, "requires_confirm": True},
        _handle_projects_restore,
    )
    register_command(
        "graph.run",
        {"inputs": {"project_id": "string", "graph_path": "string", "template_id": "string", "vars": "object"}},
        _handle_graph_run,
    )
    register_command(
        "graph.show",
        {"inputs": {"run_id": "string"}},
        _handle_graph_show,
    )
    register_command(
        "graph.template.create",
        {"inputs": {"project_id": "string", "run_id": "string", "name": "string"}, "requires_confirm": True},
        _handle_graph_template_create,
    )
    register_command(
        "graph.template.parametrize",
        {"inputs": {"template_id": "string", "jsonpath": "string", "var_name": "string"}, "requires_confirm": True},
        _handle_graph_template_parametrize,
    )
    register_command(
        "graph.patch",
        {"inputs": {"message": "string"}, "requires_confirm": True},
        _handle_graph_patch,
    )
    register_command(
        "schedule.add",
        {"inputs": {"template_id": "string", "cron": "string", "vars": "object"}, "requires_confirm": True},
        _handle_schedule_add,
    )
    register_command(
        "schedule.run_now",
        {"inputs": {"schedule_id": "string"}},
        _handle_schedule_run_now,
    )

    _DEFAULT_REGISTERED = True


def _handle_projects_create(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    name = str(plan.args.get("name", "")).strip()
    if not name:
        raise ValueError("name 不可為空")
    record = core.create_project(name)
    return {"project": record.to_dict()}


def _handle_projects_list(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    include_deleted = bool(plan.args.get("include_deleted", False))
    records = core.list_projects(include_deleted=include_deleted)
    return {"projects": [record.to_dict() for record in records]}


def _handle_projects_delete(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    project_id = str(plan.args.get("project_id", "")).strip()
    if not project_id:
        raise ValueError("project_id 不可為空")
    record = core.delete_project(project_id)
    return {"project": record.to_dict()}


def _handle_projects_restore(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    trash_id = str(plan.args.get("trash_id", "")).strip()
    if not trash_id:
        raise ValueError("trash_id 不可為空")
    project_id = _resolve_project_id_from_trash(core, trash_id)
    record = core.restore_project(project_id)
    return {"project": record.to_dict()}


def _handle_graph_run(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    project_id = str(plan.args.get("project_id") or plan.project_id).strip()
    if not project_id:
        raise ValueError("project_id 不可為空")
    vars_payload = plan.args.get("vars") or {}
    if not isinstance(vars_payload, dict):
        raise ValueError("vars 需為物件")

    graph_path = plan.args.get("graph_path")
    template_id = plan.args.get("template_id")

    if graph_path and template_id:
        raise ValueError("graph_path 與 template_id 只能擇一")
    if not graph_path and not template_id:
        raise ValueError("請提供 graph_path 或 template_id")

    if template_id:
        result = core.run_graph_template(str(template_id), variables=vars_payload)
        return {"run_id": result.run_id, "state": result.state}

    project_path = core.get_project_path(project_id)
    resolved_path = _resolve_graph_path(project_path, str(graph_path))
    result = core.run_graph(project_path=project_path, graph_path=resolved_path, variables=vars_payload)
    return {"run_id": result.run_id, "state": result.state}


def _handle_graph_show(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    run_id = str(plan.args.get("run_id", "")).strip()
    if not run_id:
        raise ValueError("run_id 不可為空")
    project_path = core.get_project_path(plan.project_id)
    state_path = project_path / ".amon" / "runs" / run_id / "state.json"
    if not state_path.exists():
        raise FileNotFoundError("找不到指定的 run")
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        core.logger.error("讀取 state.json 失敗：%s", exc, exc_info=True)
        raise ValueError("state.json 讀取失敗") from exc
    return {"run_id": run_id, "state": state}


def _handle_graph_template_create(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    project_id = str(plan.args.get("project_id") or plan.project_id).strip()
    run_id = str(plan.args.get("run_id", "")).strip()
    name = str(plan.args.get("name", "")).strip()
    if not project_id:
        raise ValueError("project_id 不可為空")
    if not run_id:
        raise ValueError("run_id 不可為空")
    if not name:
        raise ValueError("name 不可為空")
    result = core.create_graph_template(project_id, run_id, name)
    return {
        "template_id": result["template_id"],
        "path": result["path"],
        "schema_path": result["schema_path"],
    }


def _handle_graph_template_parametrize(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    template_id = str(plan.args.get("template_id", "")).strip()
    json_path = str(plan.args.get("jsonpath", "")).strip()
    var_name = str(plan.args.get("var_name", "")).strip()
    if not template_id:
        raise ValueError("template_id 不可為空")
    if not json_path:
        raise ValueError("jsonpath 不可為空")
    if not var_name:
        raise ValueError("var_name 不可為空")
    result = core.parametrize_graph_template(template_id, json_path, var_name)
    return {
        "template_id": result["template_id"],
        "path": result["path"],
        "schema_path": result["schema_path"],
    }


def _handle_graph_patch(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    message = str(plan.args.get("message", "")).strip()
    if not message:
        raise ValueError("message 不可為空")
    return {
        "status": "stub",
        "note": "graph_patch_plan 尚未實作，先記錄需求。",
        "message": message,
    }


def _handle_schedule_add(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    template_id = str(plan.args.get("template_id", "")).strip()
    cron = str(plan.args.get("cron", "")).strip()
    vars_payload = plan.args.get("vars") or {}
    if not template_id:
        raise ValueError("template_id 不可為空")
    if not cron:
        raise ValueError("cron 不可為空")
    if not isinstance(vars_payload, dict):
        raise ValueError("vars 需為物件")

    schedules = _load_schedules(core)
    schedule_id = uuid.uuid4().hex
    schedule = {
        "schedule_id": schedule_id,
        "template_id": template_id,
        "cron": cron,
        "vars": vars_payload,
        "created_at": core._now(),
    }
    schedules["schedules"].append(schedule)
    _write_schedules(core, schedules)
    return {"schedule": schedule}


def _handle_schedule_run_now(core: AmonCore, plan: CommandPlan) -> dict[str, Any]:
    schedule_id = str(plan.args.get("schedule_id", "")).strip()
    if not schedule_id:
        raise ValueError("schedule_id 不可為空")
    schedules = _load_schedules(core)
    schedule = next((item for item in schedules.get("schedules", []) if item.get("schedule_id") == schedule_id), None)
    if not schedule:
        raise KeyError("找不到指定的排程")
    result = core.run_graph_template(schedule["template_id"], variables=schedule.get("vars") or {})
    return {"schedule_id": schedule_id, "run_id": result.run_id, "state": result.state}


def _append_plan_event(
    plan: CommandPlan,
    event_type: str,
    text: str,
    extra: dict[str, Any] | None = None,
) -> None:
    event = {
        "type": event_type,
        "text": text,
        "project_id": plan.project_id,
    }
    if extra:
        event.update(extra)
    append_event(plan.chat_id, event)


def _build_plan_card(command_name: str, args: dict[str, Any]) -> str:
    detail = json.dumps(args, ensure_ascii=False)
    return make_change_plan(
        [
            {
                "action": "執行命令",
                "target": command_name,
                "detail": detail,
            }
        ]
    )


def _resolve_project_id_from_trash(core: AmonCore, trash_id: str) -> str:
    manifest_path = core.trash_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError("回收桶清單不存在")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        core.logger.error("讀取回收桶清單失敗：%s", exc, exc_info=True)
        raise ValueError("回收桶清單讀取失敗") from exc
    for entry in manifest.get("entries", []):
        trash_path = entry.get("trash_path") or ""
        if entry.get("project_id") == trash_id:
            return str(entry.get("project_id"))
        if Path(trash_path).name == trash_id:
            return str(entry.get("project_id"))
    raise KeyError("找不到對應的專案")


def _resolve_graph_path(project_path: Path, graph_path: str) -> Path:
    path = Path(graph_path)
    if not path.is_absolute():
        path = project_path / graph_path
    return path


def _load_schedules(core: AmonCore) -> dict[str, Any]:
    path = core.cache_dir / "schedules.json"
    if not path.exists():
        return {"schedules": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        core.logger.error("讀取排程資料失敗：%s", exc, exc_info=True)
        raise ValueError("排程資料讀取失敗") from exc


def _write_schedules(core: AmonCore, payload: dict[str, Any]) -> None:
    path = core.cache_dir / "schedules.json"
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        core.logger.error("寫入排程資料失敗：%s", exc, exc_info=True)
        raise


def _extract_event_payload(result: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(result, dict):
        run_id = result.get("run_id")
        if run_id:
            payload["run_id"] = run_id
    return payload
