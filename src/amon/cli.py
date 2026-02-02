"""Command line interface for Amon."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from .core import AmonCore


def _print_project(record) -> None:
    print(f"專案 ID：{record.project_id}")
    print(f"名稱：{record.name}")
    print(f"路徑：{record.path}")
    print(f"狀態：{record.status}")
    print(f"建立時間：{record.created_at}")
    print(f"更新時間：{record.updated_at}")
    if record.trash_path:
        print(f"回收桶路徑：{record.trash_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="amon", description="Amon 本地端 Agent 系統 CLI")
    parser.add_argument(
        "--data-dir",
        default=None,
        help="指定 Amon 資料夾位置（預設 ~/.amon）",
    )

    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init", help="初始化 Amon 資料夾")

    project_parser = subparsers.add_parser("project", help="專案管理")
    project_sub = project_parser.add_subparsers(dest="project_command")

    create_parser = project_sub.add_parser("create", help="建立新專案")
    create_parser.add_argument("name", help="專案名稱")

    list_parser = project_sub.add_parser("list", help="列出專案")
    list_parser.add_argument("--all", action="store_true", help="包含已刪除專案")

    show_parser = project_sub.add_parser("show", help="查看專案資訊")
    show_parser.add_argument("project_id", help="專案 ID")

    update_parser = project_sub.add_parser("update", help="更新專案資訊")
    update_parser.add_argument("project_id", help="專案 ID")
    update_parser.add_argument("--name", required=True, help="新的專案名稱")

    delete_parser = project_sub.add_parser("delete", help="刪除專案（移到回收桶）")
    delete_parser.add_argument("project_id", help="專案 ID")

    restore_parser = project_sub.add_parser("restore", help="還原專案")
    restore_parser.add_argument("project_id", help="專案 ID")

    config_parser = subparsers.add_parser("config", help="設定管理")
    config_sub = config_parser.add_subparsers(dest="config_command")

    config_get = config_sub.add_parser("get", help="讀取設定")
    config_get.add_argument("key", help="設定鍵（例如 providers.openai.model）")
    config_get.add_argument("--project", help="指定專案 ID")

    config_set = config_sub.add_parser("set", help="更新設定")
    config_set.add_argument("key", help="設定鍵（例如 providers.openai.model）")
    config_set.add_argument("value", help="設定值（會以 YAML 解析）")
    config_set.add_argument("--project", help="指定專案 ID")

    run_parser = subparsers.add_parser("run", help="執行單一模式")
    run_parser.add_argument("--prompt", required=True, help="輸入提示")
    run_parser.add_argument("--project", help="指定專案 ID")
    run_parser.add_argument("--model", help="指定模型")

    skills_parser = subparsers.add_parser("skills", help="技能管理")
    skills_sub = skills_parser.add_subparsers(dest="skills_command")
    skills_scan = skills_sub.add_parser("scan", help="掃描技能")
    skills_scan.add_argument("--project", help="指定專案 ID")
    skills_sub.add_parser("list", help="列出技能")

    mcp_parser = subparsers.add_parser("mcp", help="MCP 設定")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")
    mcp_sub.add_parser("list", help="列出 MCP Server")
    mcp_allow = mcp_sub.add_parser("allow", help="允許 MCP tool")
    mcp_allow.add_argument("tool", help="tool 名稱")
    mcp_deny = mcp_sub.add_parser("deny", help="移除 MCP tool 權限")
    mcp_deny.add_argument("tool", help="tool 名稱")

    ui_parser = subparsers.add_parser("ui", help="啟動 UI 預覽")
    ui_parser.add_argument("--port", type=int, default=8000, help="UI 服務埠號（預設 8000）")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    data_dir = Path(args.data_dir).expanduser() if args.data_dir else None
    core = AmonCore(data_dir=data_dir)

    try:
        if args.command == "init":
            core.initialize()
            print("已完成初始化")
            return
        if args.command == "project":
            _handle_project(core, args)
        elif args.command == "config":
            _handle_config(core, args)
        elif args.command == "run":
            _handle_run(core, args)
        elif args.command == "skills":
            _handle_skills(core, args)
        elif args.command == "mcp":
            _handle_mcp(core, args)
        elif args.command == "ui":
            _handle_ui(args)
        else:
            parser.print_help()
    except Exception as exc:  # noqa: BLE001
        core.logger.error("執行失敗：%s", exc, exc_info=True)
        print("發生錯誤，請查看 logs/amon.log 取得詳細資訊。", file=sys.stderr)
        sys.exit(1)


def _handle_project(core: AmonCore, args: argparse.Namespace) -> None:
    if args.project_command == "create":
        record = core.create_project(args.name)
        print("已建立專案")
        _print_project(record)
        return

    if args.project_command == "list":
        records = core.list_projects(include_deleted=args.all)
        if not records:
            print("目前沒有任何專案。")
            return
        for record in records:
            status_note = "（已刪除）" if record.status == "deleted" else ""
            print(f"{record.project_id}｜{record.name}{status_note}")
        return

    if args.project_command == "show":
        record = core.get_project(args.project_id)
        _print_project(record)
        return

    if args.project_command == "update":
        record = core.update_project_name(args.project_id, args.name)
        print("已更新專案")
        _print_project(record)
        return

    if args.project_command == "delete":
        record = core.delete_project(args.project_id)
        print("已刪除專案（已移至回收桶）")
        _print_project(record)
        return

    if args.project_command == "restore":
        record = core.restore_project(args.project_id)
        print("已還原專案")
        _print_project(record)
        return

    raise ValueError("請指定專案指令")


def _handle_config(core: AmonCore, args: argparse.Namespace) -> None:
    project_path = core.get_project_path(args.project) if args.project else None
    if args.config_command == "get":
        value = core.get_config_value(args.key, project_path=project_path)
        print(value)
        return
    if args.config_command == "set":
        try:
            parsed_value = yaml.safe_load(args.value)
        except yaml.YAMLError as exc:
            raise ValueError("設定值格式錯誤") from exc
        core.set_config_value(args.key, parsed_value, project_path=project_path)
        print("已更新設定")
        return
    raise ValueError("請指定設定指令")


def _handle_run(core: AmonCore, args: argparse.Namespace) -> None:
    project_path = core.get_project_path(args.project) if args.project else None
    core.run_single(args.prompt, project_path=project_path, model=args.model)


def _handle_skills(core: AmonCore, args: argparse.Namespace) -> None:
    project_path = core.get_project_path(args.project) if args.project else None
    if args.skills_command == "scan":
        skills = core.scan_skills(project_path=project_path)
        print(f"已掃描 {len(skills)} 個技能")
        return
    if args.skills_command == "list":
        skills = core.list_skills()
        if not skills:
            print("尚未建立技能索引，請先執行 amon skills scan。")
            return
        for skill in skills:
            scope = "全域" if skill.get("scope") == "global" else "專案"
            description = skill.get("description") or "無描述"
            print(f"{skill.get('name')}｜{scope}｜{description}")
        return
    raise ValueError("請指定技能指令")


def _handle_mcp(core: AmonCore, args: argparse.Namespace) -> None:
    if args.mcp_command == "list":
        config = core.load_config()
        servers = config.get("mcp", {}).get("servers", {})
        allowed_tools = config.get("mcp", {}).get("allowed_tools", [])
        if not servers:
            print("尚未設定 MCP server。")
        else:
            for name, server in servers.items():
                server_type = server.get("type", "unknown")
                endpoint = server.get("endpoint", "")
                print(f"{name}｜{server_type}｜{endpoint}")
        if allowed_tools:
            print("允許的 tools：")
            for tool in allowed_tools:
                print(f"- {tool}")
        return
    if args.mcp_command == "allow":
        core.add_allowed_tool(args.tool)
        print("已更新 MCP tool 權限")
        return
    if args.mcp_command == "deny":
        core.remove_allowed_tool(args.tool)
        print("已更新 MCP tool 權限")
        return
    raise ValueError("請指定 MCP 指令")


def _handle_ui(args: argparse.Namespace) -> None:
    from .ui_server import serve_ui

    serve_ui(port=args.port)
