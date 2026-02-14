"""Command line interface for Amon."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import yaml

from .config import ConfigLoader
from .core import AmonCore
from .events import emit_event
from .fs.safety import make_change_plan, require_confirm
from .mcp_client import MCPClientError
from .sandbox import (
    SandboxRunnerClient,
    build_input_file,
    decode_output_files,
    parse_runner_settings,
)


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

    config_show = config_sub.add_parser("show", help="顯示合併後設定")
    config_show.add_argument("--project", help="指定專案 ID")

    run_parser = subparsers.add_parser("run", help="執行模式")
    run_parser.add_argument("user_task", nargs="?", help="輸入任務")
    run_parser.add_argument("--prompt", help="輸入提示（相容舊版）")
    run_parser.add_argument("--project", required=True, help="指定專案 ID")
    run_parser.add_argument("--model", help="指定模型")
    run_parser.add_argument("--mode", default="single", help="指定模式（single/self_critique/team）")
    run_parser.add_argument("--skill", action="append", default=[], help="指定技能名稱（可重複）")

    skills_parser = subparsers.add_parser("skills", help="技能管理")
    skills_sub = skills_parser.add_subparsers(dest="skills_command")
    skills_scan = skills_sub.add_parser("scan", help="掃描技能")
    skills_scan.add_argument("--project", help="指定專案 ID")
    skills_list = skills_sub.add_parser("list", help="列出技能")
    skills_list.add_argument("--project", help="指定專案 ID")
    skills_show = skills_sub.add_parser("show", help="顯示技能內容")
    skills_show.add_argument("name", help="技能名稱")
    skills_show.add_argument("--project", help="指定專案 ID")

    mcp_parser = subparsers.add_parser("mcp", help="MCP 設定")
    mcp_sub = mcp_parser.add_subparsers(dest="mcp_command")
    mcp_sub.add_parser("list", help="列出 MCP Server")
    mcp_allow = mcp_sub.add_parser("allow", help="允許 MCP tool")
    mcp_allow.add_argument("tool", help="tool 名稱")
    mcp_deny = mcp_sub.add_parser("deny", help="移除 MCP tool 權限")
    mcp_deny.add_argument("tool", help="tool 名稱")

    tools_parser = subparsers.add_parser("tools", help="工具管理")
    tools_sub = tools_parser.add_subparsers(dest="tools_command")
    tools_forge = tools_sub.add_parser("forge", help="建立新工具")
    tools_forge.add_argument("--project", required=True, help="指定專案 ID")
    tools_forge.add_argument("--name", required=True, help="工具名稱")
    tools_forge.add_argument("--spec", required=True, help="工具需求規格")

    tools_list = tools_sub.add_parser("list", help="列出工具")
    tools_list.add_argument("--project", help="指定專案 ID（可顯示專案覆寫）")
    tools_list.add_argument("--builtin", action="store_true", help="列出內建工具")

    tools_run = tools_sub.add_parser("run", help="執行工具")
    tools_run.add_argument("tool_name", help="工具名稱")
    tools_run.add_argument("--project", help="指定專案 ID")
    tools_run.add_argument("--args", default="{}", help="JSON 格式的參數")
    tools_run.add_argument("--builtin", action="store_true", help="呼叫內建工具")

    tools_test = tools_sub.add_parser("test", help="執行工具測試")
    tools_test.add_argument("tool_name", help="工具名稱")
    tools_test.add_argument("--project", help="指定專案 ID")

    tools_register = tools_sub.add_parser("register", help="註冊工具")
    tools_register.add_argument("tool_name", help="工具名稱")
    tools_register.add_argument("--project", help="指定專案 ID")

    tools_mcp_list = tools_sub.add_parser("mcp-list", help="列出 MCP tools")
    tools_mcp_list.add_argument("--refresh", action="store_true", help="重新抓取 MCP tools（忽略快取）")
    tools_mcp_call = tools_sub.add_parser("mcp-call", help="呼叫 MCP tool")
    tools_mcp_call.add_argument("target", help="格式：<server>:<tool>")
    tools_mcp_call.add_argument("--args", default="{}", help="JSON 格式的參數")

    tools_call = tools_sub.add_parser("call", help="呼叫內建/原生工具")
    tools_call.add_argument("tool_name", help="工具名稱（例如 native:hello 或 builtin:filesystem.read）")
    tools_call.add_argument("--project", help="指定專案 ID")
    tools_call.add_argument("--args", default="{}", help="JSON 格式的參數")

    toolforge_parser = subparsers.add_parser("toolforge", help="Toolforge 管理")
    toolforge_sub = toolforge_parser.add_subparsers(dest="toolforge_command")
    toolforge_init = toolforge_sub.add_parser("init", help="建立 toolforge scaffold")
    toolforge_init.add_argument("name", help="工具名稱")
    toolforge_install = toolforge_sub.add_parser("install", help="安裝 toolforge 工具")
    toolforge_install.add_argument("path", help="工具資料夾")
    toolforge_install.add_argument("--project", help="指定專案 ID（安裝到專案）")
    toolforge_verify = toolforge_sub.add_parser("verify", help="驗證已安裝工具")
    toolforge_verify.add_argument("--project", help="指定專案 ID（包含專案工具）")

    ui_parser = subparsers.add_parser("ui", help="啟動 UI 預覽")
    ui_parser.add_argument("--port", type=int, default=8000, help="UI 服務埠號（預設 8000）")

    fs_parser = subparsers.add_parser("fs", help="檔案安全操作")
    fs_sub = fs_parser.add_subparsers(dest="fs_command")
    fs_delete = fs_sub.add_parser("delete", help="刪除檔案（移到回收桶）")
    fs_delete.add_argument("path", help="要刪除的路徑")
    fs_restore = fs_sub.add_parser("restore", help="從回收桶還原")
    fs_restore.add_argument("trash_id", help="回收桶 ID")

    export_parser = subparsers.add_parser("export", help="匯出專案資料")
    export_parser.add_argument("--project", required=True, help="專案 ID")
    export_parser.add_argument("--out", required=True, help="輸出檔案路徑（zip）")

    eval_parser = subparsers.add_parser("eval", help="執行簡易回歸評測")
    eval_parser.add_argument("--suite", default="basic", help="評測套件（預設 basic）")

    daemon_parser = subparsers.add_parser("daemon", help="啟動常駐服務")
    daemon_parser.add_argument("--tick-interval", type=int, default=5, help="scheduler tick 間隔秒數")

    subparsers.add_parser("doctor", help="一鍵診斷系統狀態")

    graph_parser = subparsers.add_parser("graph", help="Graph 執行")
    graph_sub = graph_parser.add_subparsers(dest="graph_command")
    graph_run = graph_sub.add_parser("run", help="執行 graph")
    graph_run.add_argument("--project", help="指定專案 ID")
    graph_run.add_argument("--graph", help="graph.json 路徑")
    graph_run.add_argument("--template", help="template ID")
    graph_run.add_argument("--var", action="append", default=[], help="變數（k=v）")

    graph_template = graph_sub.add_parser("template", help="Graph template 管理")
    graph_template_sub = graph_template.add_subparsers(dest="template_command")
    template_create = graph_template_sub.add_parser("create", help="建立 graph template")
    template_create.add_argument("--project", required=True, help="指定專案 ID")
    template_create.add_argument("--run", required=True, help="graph run ID")
    template_create.add_argument("--name", help="template 名稱")
    template_param = graph_template_sub.add_parser("parametrize", help="參數化 template")
    template_param.add_argument("--template", required=True, help="template ID")
    template_param.add_argument("--path", required=True, help="JSONPath")
    template_param.add_argument("--var_name", required=True, help="變數名稱")

    chat_parser = subparsers.add_parser("chat", help="互動式 Chat")
    chat_parser.add_argument("--project", required=True, help="指定專案 ID")

    hooks_parser = subparsers.add_parser("hooks", help="Hook 管理")
    hooks_sub = hooks_parser.add_subparsers(dest="hooks_command")
    hooks_sub.add_parser("list", help="列出 hooks")
    hooks_add = hooks_sub.add_parser("add", help="新增 hook")
    hooks_add.add_argument("hook_id", help="hook ID")
    hooks_add.add_argument("--file", required=True, help="hook YAML 檔案路徑")
    hooks_enable = hooks_sub.add_parser("enable", help="啟用 hook")
    hooks_enable.add_argument("hook_id", help="hook ID")
    hooks_disable = hooks_sub.add_parser("disable", help="停用 hook")
    hooks_disable.add_argument("hook_id", help="hook ID")
    hooks_delete = hooks_sub.add_parser("delete", help="刪除 hook")
    hooks_delete.add_argument("hook_id", help="hook ID")

    schedules_parser = subparsers.add_parser("schedules", help="排程管理")
    schedules_sub = schedules_parser.add_subparsers(dest="schedules_command")
    schedules_sub.add_parser("list", help="列出排程")
    schedules_add = schedules_sub.add_parser("add", help="新增排程")
    schedules_add.add_argument("--payload", required=True, help="JSON 格式的排程內容")
    schedules_enable = schedules_sub.add_parser("enable", help="啟用排程")
    schedules_enable.add_argument("schedule_id", help="排程 ID")
    schedules_disable = schedules_sub.add_parser("disable", help="停用排程")
    schedules_disable.add_argument("schedule_id", help="排程 ID")
    schedules_delete = schedules_sub.add_parser("delete", help="刪除排程")
    schedules_delete.add_argument("schedule_id", help="排程 ID")
    schedules_run_now = schedules_sub.add_parser("run-now", help="排程立即執行")
    schedules_run_now.add_argument("schedule_id", help="排程 ID")

    jobs_parser = subparsers.add_parser("jobs", help="常駐工作管理")
    jobs_sub = jobs_parser.add_subparsers(dest="jobs_command")
    jobs_sub.add_parser("list", help="列出 jobs")
    jobs_start = jobs_sub.add_parser("start", help="啟動 job")
    jobs_start.add_argument("job_id", help="job ID")
    jobs_start.add_argument("--heartbeat-interval", type=int, default=5, help="heartbeat 間隔秒數")
    jobs_stop = jobs_sub.add_parser("stop", help="停止 job")
    jobs_stop.add_argument("job_id", help="job ID")
    jobs_restart = jobs_sub.add_parser("restart", help="重啟 job")
    jobs_restart.add_argument("job_id", help="job ID")
    jobs_status = jobs_sub.add_parser("status", help="查看 job 狀態")
    jobs_status.add_argument("job_id", help="job ID")

    sandbox_parser = subparsers.add_parser("sandbox", help="外部 sandbox runner")
    sandbox_sub = sandbox_parser.add_subparsers(dest="sandbox_command")
    sandbox_exec = sandbox_sub.add_parser("exec", help="送出程式到外部 runner 執行")
    sandbox_exec.add_argument("--language", required=True, help="語言，例如 python")
    sandbox_exec.add_argument("--code-file", required=True, help="程式碼檔案路徑")
    sandbox_exec.add_argument("--project", help="指定專案 ID（讀取專案設定）")
    sandbox_exec.add_argument(
        "--in",
        dest="input_files",
        action="append",
        default=[],
        help="輸入檔案對應，格式：runner/path=local_file_path，可重複",
    )
    sandbox_exec.add_argument("--out-dir", required=True, help="runner output_files 解碼落地資料夾")

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
        elif args.command == "tools":
            _handle_tools(core, args)
        elif args.command == "toolforge":
            _handle_toolforge(core, args)
        elif args.command == "ui":
            _handle_ui(args)
        elif args.command == "daemon":
            from .daemon import run_daemon

            run_daemon(data_dir=data_dir, tick_interval_seconds=args.tick_interval)
        elif args.command == "fs":
            _handle_fs(core, args)
        elif args.command == "export":
            _handle_export(core, args)
        elif args.command == "eval":
            _handle_eval(core, args)
        elif args.command == "doctor":
            _handle_doctor(core)
        elif args.command == "graph":
            _handle_graph(core, args)
        elif args.command == "chat":
            _handle_chat(core, args)
        elif args.command == "hooks":
            _handle_hooks(core, args)
        elif args.command == "schedules":
            _handle_schedules(core, args)
        elif args.command == "jobs":
            _handle_jobs(core, args)
        elif args.command == "sandbox":
            _handle_sandbox(core, args)
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
    if args.config_command == "get":
        project_path = core.get_project_path(args.project) if args.project else None
        value = core.get_config_value(args.key, project_path=project_path)
        print(value)
        return
    if args.config_command == "set":
        project_path = core.get_project_path(args.project) if args.project else None
        try:
            parsed_value = yaml.safe_load(args.value)
        except yaml.YAMLError as exc:
            raise ValueError("設定值格式錯誤") from exc
        core.set_config_value(args.key, parsed_value, project_path=project_path)
        print("已更新設定")
        return
    if args.config_command == "show":
        loader = ConfigLoader(data_dir=core.data_dir)
        resolution = loader.resolve(project_id=args.project)
        print(yaml.safe_dump(resolution.annotated(), allow_unicode=True, sort_keys=False))
        return
    raise ValueError("請指定設定指令")


def _handle_run(core: AmonCore, args: argparse.Namespace) -> None:
    user_task = args.user_task or args.prompt
    if not user_task:
        raise ValueError("請提供任務內容")
    project_path = core.get_project_path(args.project) if args.project else None
    if args.mode == "single":
        core.run_single(user_task, project_path=project_path, model=args.model, skill_names=args.skill)
        return
    if args.mode == "self_critique":
        core.run_self_critique(user_task, project_path=project_path, model=args.model, skill_names=args.skill)
        return
    if args.mode == "team":
        core.run_team(user_task, project_path=project_path, model=args.model, skill_names=args.skill)
        return
    raise ValueError(f"目前僅支援 single/self_critique/team 模式（收到：{args.mode}）")


def _handle_skills(core: AmonCore, args: argparse.Namespace) -> None:
    project_path = core.get_project_path(args.project) if args.project else None
    if args.skills_command == "scan":
        skills = core.scan_skills(project_path=project_path)
        print(f"已掃描 {len(skills)} 個技能")
        return
    if args.skills_command == "list":
        if args.project:
            skills = core.scan_skills(project_path=project_path)
        else:
            skills = core.list_skills()
            if not skills:
                print("尚未建立技能索引，請先執行 amon skills scan。")
                return
        if not skills:
            print("未找到任何技能。")
            return
        for skill in skills:
            source = skill.get("source", skill.get("scope"))
            scope = "全域" if source == "global" else "專案"
            description = skill.get("description") or "無描述"
            print(f"{skill.get('name')}｜{scope}｜{description}")
        return
    if args.skills_command == "show":
        skill = core.load_skill(args.name, project_path=project_path)
        source = skill.get("source", skill.get("scope"))
        scope = "全域" if source == "global" else "專案"
        description = skill.get("description") or "無描述"
        print(f"名稱：{skill.get('name')}")
        print(f"範圍：{scope}")
        print(f"描述：{description}")
        print(f"路徑：{skill.get('path')}")
        references = skill.get("references", [])
        if references:
            print(f"參考資料：{len(references)} 筆")
            for ref in references:
                print(f"- {ref.get('path')} ({ref.get('size')} bytes)")
        print("內容：")
        print(skill.get("content", ""))
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


def _handle_tools(core: AmonCore, args: argparse.Namespace) -> None:
    if args.tools_command == "forge":
        tool_dir = core.forge_tool(args.project, args.name, args.spec)
        print(f"已建立工具：{tool_dir}")
        return
    if args.tools_command == "list":
        if args.builtin:
            _handle_builtin_list(core, args)
            return
        legacy_tools = core.list_tools(project_id=args.project)
        native_tools = core.list_native_tools(project_id=args.project)
        if not legacy_tools and not native_tools:
            print("目前沒有可用工具。")
            return
        for tool in legacy_tools:
            print(f"{tool['name']}｜{tool['version']}｜{tool['risk_level']}｜{tool['scope']}")
        for tool in native_tools:
            print(
                f"native:{tool['name']}｜{tool['version']}｜{tool['risk']}｜native｜{tool['default_permission']}"
            )
        return
    if args.tools_command == "run":
        if args.builtin or args.tool_name.startswith("builtin:"):
            _handle_builtin_run(core, args)
            return
        try:
            parsed_args = json.loads(args.args)
        except json.JSONDecodeError as exc:
            raise ValueError("args 必須是 JSON 格式") from exc
        output = core.run_tool(args.tool_name, parsed_args, project_id=args.project)
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    if args.tools_command == "test":
        core.test_tool(args.tool_name, project_id=args.project)
        print("工具測試成功")
        return
    if args.tools_command == "register":
        entry = core.register_tool(args.tool_name, project_id=args.project)
        print(f"已註冊工具：{entry.get('name')} {entry.get('version')}")
        return
    if args.tools_command == "mcp-list":
        registry = core.get_mcp_registry(refresh=args.refresh)
        servers = registry.get("servers", {})
        if not servers:
            print("尚未設定 MCP tools。")
            return
        for name, info in servers.items():
            tools = info.get("tools", [])
            error = info.get("error")
            if error:
                print(f"{name}｜{info.get('transport', 'unknown')}｜錯誤：{error}")
                continue
            if not tools:
                print(f"{name}｜{info.get('transport', 'unknown')}｜無可用 tools")
                continue
            for tool in tools:
                tool_name = tool.get("name", "unknown")
                description = tool.get("description", "")
                print(f"{name}:{tool_name}｜{description}")
        return
    if args.tools_command == "mcp-call":
        if ":" not in args.target:
            raise ValueError("請提供 <server>:<tool> 格式")
        server_name, tool_name = args.target.split(":", 1)
        try:
            parsed_args = json.loads(args.args)
        except json.JSONDecodeError as exc:
            raise ValueError("args 必須是 JSON 格式") from exc
        try:
            result = core.call_mcp_tool(server_name, tool_name, parsed_args)
        except PermissionError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)
        except MCPClientError as exc:
            print(f"CLIENT_ERROR: {exc}", file=sys.stderr)
            sys.exit(1)
        print(result.get("data_prompt", ""))
        if result.get("is_error"):
            print("TOOL_ERROR: MCP tool 執行失敗。", file=sys.stderr)
            sys.exit(1)
        return
    if args.tools_command == "call":
        from .tooling.audit import FileAuditSink, default_audit_log_path
        from .tooling.runtime import build_registry
        from .tooling.types import ToolCall

        try:
            parsed_args = json.loads(args.args)
        except json.JSONDecodeError as exc:
            raise ValueError("args 必須是 JSON 格式") from exc
        tool_name = args.tool_name
        if tool_name.startswith("builtin:"):
            tool_name = tool_name.split(":", 1)[1]
        elif not tool_name.startswith("native:") and tool_name.startswith("native."):
            tool_name = tool_name.replace("native.", "native:", 1)
        workspace_root = core.get_project_path(args.project) if args.project else Path.cwd()
        registry = build_registry(
            workspace_root,
            core.native_tool_dirs(args.project),
            audit_sink=FileAuditSink(default_audit_log_path()),
        )
        result = registry.call(ToolCall(tool=tool_name, args=parsed_args, caller="cli", project_id=args.project))
        payload = _format_builtin_result(result)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    raise ValueError("請指定 tools 指令")


def _handle_toolforge(core: AmonCore, args: argparse.Namespace) -> None:
    if args.toolforge_command == "init":
        tool_dir = core.toolforge_init(args.name)
        print(f"已建立 toolforge 工具：{tool_dir}")
        return
    if args.toolforge_command == "install":
        entry = core.toolforge_install(Path(args.path), project_id=args.project)
        print(f"已安裝 toolforge 工具：{entry.get('name')} {entry.get('version')}")
        return
    if args.toolforge_command == "verify":
        tools = core.toolforge_verify(project_id=args.project)
        if not tools:
            print("尚未安裝 toolforge 工具。")
            return
        for tool in tools:
            violations = tool.get("violations") or []
            violation_text = f"｜VIOLATION: {', '.join(violations)}" if violations else ""
            print(
                f"native:{tool['name']}｜{tool['version']}｜{tool['path']}｜{tool['sha256']}｜"
                f"{tool['risk']}｜{tool['default_permission']}{violation_text}"
            )
        return
    raise ValueError("請指定 toolforge 指令")


def _handle_builtin_list(core: AmonCore, args: argparse.Namespace) -> None:
    from .tooling.builtin import build_registry

    workspace_root = core.get_project_path(args.project) if args.project else Path.cwd()
    registry = build_registry(workspace_root)
    specs = sorted(registry.list_specs(), key=lambda spec: spec.name)
    if not specs:
        print("目前沒有內建工具。")
        return
    for spec in specs:
        print(f"builtin:{spec.name}｜{spec.risk}｜builtin｜{spec.description}")


def _handle_builtin_run(core: AmonCore, args: argparse.Namespace) -> None:
    from .tooling.builtin import build_registry
    from .tooling.types import ToolCall

    tool_name = args.tool_name
    if tool_name.startswith("builtin:"):
        tool_name = tool_name.split(":", 1)[1]
    try:
        parsed_args = json.loads(args.args)
    except json.JSONDecodeError as exc:
        raise ValueError("args 必須是 JSON 格式") from exc
    workspace_root = core.get_project_path(args.project) if args.project else Path.cwd()
    registry = build_registry(workspace_root)
    try:
        result = registry.call(
            ToolCall(tool=tool_name, args=parsed_args, caller="cli", project_id=args.project)
        )
    except ValueError as exc:
        result = _builtin_error_result(str(exc), status="denied")
    payload = _format_builtin_result(result)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _builtin_error_result(message: str, status: str) -> "ToolResult":
    from .tooling.types import ToolResult

    return ToolResult(content=[{"type": "text", "text": message}], is_error=True, meta={"status": status})


def _format_builtin_result(result: "ToolResult") -> dict[str, object]:
    status = result.meta.get("status", "ok")
    if not result.is_error:
        return {"status": "ok", "content": result.content, "text": result.as_text()}
    label = _map_builtin_error(status)
    return {"status": status, "error": label, "content": result.content, "text": result.as_text()}


def _map_builtin_error(status: str) -> str:
    if status == "unknown_tool":
        return "Unknown tool"
    if status == "denied":
        return "DENIED"
    if status in {"approval_required", "approval_missing"}:
        return "APPROVAL_REQUIRED"
    return "ERROR"


def _handle_doctor(core: AmonCore) -> None:
    report = core.doctor()
    print("Amon Doctor")
    print(f"整體狀態：{report.get('status')}")
    checks = report.get("checks", {})
    for name, info in checks.items():
        status = info.get("status", "unknown")
        message = info.get("message", "")
        print(f"- {name}：{status}｜{message}")


def _handle_ui(args: argparse.Namespace) -> None:
    from .ui_server import serve_ui

    serve_ui(port=args.port)


def _handle_fs(core: AmonCore, args: argparse.Namespace) -> None:
    if args.fs_command == "delete":
        trash_id = core.fs_delete(args.path)
        if not trash_id:
            print("已取消操作")
            return
        print(f"已移至回收桶：{trash_id}")
        return
    if args.fs_command == "restore":
        restored_path = core.fs_restore(args.trash_id)
        print(f"已還原到：{restored_path}")
        return
    raise ValueError("請指定 fs 指令")


def _handle_export(core: AmonCore, args: argparse.Namespace) -> None:
    output_path = core.export_project(args.project, Path(args.out))
    print(f"已匯出專案：{output_path}")


def _handle_eval(core: AmonCore, args: argparse.Namespace) -> None:
    result = core.run_eval(suite=args.suite)
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))


def _handle_graph(core: AmonCore, args: argparse.Namespace) -> None:
    if args.graph_command == "run":
        variables = _parse_vars(args.var)
        if args.template:
            result = core.run_graph_template(args.template, variables)
            print(f"已完成 graph template 執行：{result.run_id}")
            print(f"結果目錄：{result.run_dir}")
            return
        if not args.project or not args.graph:
            raise ValueError("執行 graph 需要指定 --project 與 --graph")
        project_path = core.get_project_path(args.project)
        graph_path = Path(args.graph).expanduser()
        result = core.run_graph(project_path=project_path, graph_path=graph_path, variables=variables)
        print(f"已完成 graph 執行：{result.run_id}")
        print(f"結果目錄：{result.run_dir}")
        return
    if args.graph_command == "template":
        if args.template_command == "create":
            result = core.create_graph_template(args.project, args.run, args.name)
            print(f"已建立 graph template：{result['template_id']}")
            print(f"template 路徑：{result['path']}")
            return
        if args.template_command == "parametrize":
            result = core.parametrize_graph_template(args.template, args.path, args.var_name)
            print(f"已更新 graph template：{result['template_id']}")
            print(f"template 路徑：{result['path']}")
            return
        raise ValueError("請指定 graph template 指令")
    raise ValueError("請指定 graph 指令")


def _handle_chat(core: AmonCore, args: argparse.Namespace) -> None:
    from .chat.cli import run_chat_repl

    run_chat_repl(core, args.project)


def _parse_vars(items: list[str]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError("--var 格式需為 k=v")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("--var 鍵不可為空")
        variables[key] = value
    return variables


def _handle_hooks(core: AmonCore, args: argparse.Namespace) -> None:
    hooks_dir = core.data_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    if args.hooks_command == "list":
        hooks = sorted(path.stem for path in hooks_dir.glob("*.yaml"))
        if not hooks:
            print("目前沒有任何 hook。")
            return
        for hook_id in hooks:
            print(hook_id)
        return
    if args.hooks_command == "add":
        source_path = Path(args.file).expanduser()
        payload = source_path.read_text(encoding="utf-8")
        target_path = hooks_dir / f"{args.hook_id}.yaml"
        target_path.write_text(payload, encoding="utf-8")
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "hooks", "hook_id": args.hook_id, "action": "add"},
                "risk": "low",
            }
        )
        print(f"已新增 hook：{args.hook_id}")
        return
    if args.hooks_command in {"enable", "disable"}:
        target_path = hooks_dir / f"{args.hook_id}.yaml"
        if not target_path.exists():
            raise ValueError("找不到指定的 hook")
        if args.hooks_command == "disable":
            plan = make_change_plan([{"action": "停用 hook", "target": args.hook_id}])
            if not require_confirm(plan):
                print("已取消操作")
                return
        data = yaml.safe_load(target_path.read_text(encoding="utf-8")) or {}
        data["enabled"] = args.hooks_command == "enable"
        target_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "hooks", "hook_id": args.hook_id, "action": args.hooks_command},
                "risk": "low",
            }
        )
        print(f"已更新 hook：{args.hook_id}")
        return
    if args.hooks_command == "delete":
        target_path = hooks_dir / f"{args.hook_id}.yaml"
        if not target_path.exists():
            raise ValueError("找不到指定的 hook")
        plan = make_change_plan([{"action": "刪除 hook", "target": args.hook_id}])
        if not require_confirm(plan):
            print("已取消操作")
            return
        target_path.unlink()
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "hooks", "hook_id": args.hook_id, "action": "delete"},
                "risk": "medium",
            }
        )
        print(f"已刪除 hook：{args.hook_id}")
        return
    raise ValueError("請指定 hooks 指令")


def _handle_schedules(core: AmonCore, args: argparse.Namespace) -> None:
    from .scheduler.engine import load_schedules, write_schedules

    core.ensure_base_structure()
    payload = load_schedules(data_dir=core.data_dir)
    schedules = payload.get("schedules", [])
    if args.schedules_command == "list":
        if not schedules:
            print("目前沒有任何排程。")
            return
        for schedule in schedules:
            schedule_id = schedule.get("schedule_id", "")
            enabled = schedule.get("enabled", True)
            status = "啟用" if enabled else "停用"
            print(f"{schedule_id}｜{status}")
        return
    if args.schedules_command == "add":
        try:
            schedule = json.loads(args.payload)
        except json.JSONDecodeError as exc:
            raise ValueError("payload 必須是 JSON 格式") from exc
        schedule_id = schedule.get("schedule_id")
        if not schedule_id:
            raise ValueError("payload 需要 schedule_id")
        schedules = [entry for entry in schedules if entry.get("schedule_id") != schedule_id]
        schedules.append(schedule)
        write_schedules({"schedules": schedules}, data_dir=core.data_dir)
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "schedules", "schedule_id": schedule_id, "action": "add"},
                "risk": "low",
            }
        )
        print(f"已新增排程：{schedule_id}")
        return
    if args.schedules_command in {"enable", "disable"}:
        target = next((item for item in schedules if item.get("schedule_id") == args.schedule_id), None)
        if not target:
            raise ValueError("找不到指定的排程")
        if args.schedules_command == "disable":
            plan = make_change_plan([{"action": "停用排程", "target": args.schedule_id}])
            if not require_confirm(plan):
                print("已取消操作")
                return
        target["enabled"] = args.schedules_command == "enable"
        write_schedules({"schedules": schedules}, data_dir=core.data_dir)
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "schedules", "schedule_id": args.schedule_id, "action": args.schedules_command},
                "risk": "low",
            }
        )
        print(f"已更新排程：{args.schedule_id}")
        return
    if args.schedules_command == "delete":
        plan = make_change_plan([{"action": "刪除排程", "target": args.schedule_id}])
        if not require_confirm(plan):
            print("已取消操作")
            return
        schedules = [entry for entry in schedules if entry.get("schedule_id") != args.schedule_id]
        write_schedules({"schedules": schedules}, data_dir=core.data_dir)
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "schedules", "schedule_id": args.schedule_id, "action": "delete"},
                "risk": "medium",
            }
        )
        print(f"已刪除排程：{args.schedule_id}")
        return
    if args.schedules_command == "run-now":
        target = next((item for item in schedules if item.get("schedule_id") == args.schedule_id), None)
        if not target:
            raise ValueError("找不到指定的排程")
        target["enabled"] = True
        target["next_fire_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
        write_schedules({"schedules": schedules}, data_dir=core.data_dir)
        emit_event(
            {
                "type": "config.changed",
                "scope": "config",
                "actor": "system",
                "payload": {"domain": "schedules", "schedule_id": args.schedule_id, "action": "run-now"},
                "risk": "low",
            }
        )
        print(f"已安排立即執行：{args.schedule_id}")
        return
    raise ValueError("請指定 schedules 指令")


def _handle_jobs(core: AmonCore, args: argparse.Namespace) -> None:
    from .jobs.runner import start_job, status_job, stop_job

    jobs_dir = core.data_dir / "jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    if args.jobs_command == "list":
        jobs = sorted(path.stem for path in jobs_dir.glob("*.yaml"))
        if not jobs:
            print("目前沒有任何 job。")
            return
        for job_id in jobs:
            print(job_id)
        return
    if args.jobs_command == "start":
        config_path = jobs_dir / f"{args.job_id}.yaml"
        if not config_path.exists():
            config_path.write_text(yaml.safe_dump({}, allow_unicode=True), encoding="utf-8")
        status = start_job(args.job_id, data_dir=core.data_dir, heartbeat_interval_seconds=args.heartbeat_interval)
        print(f"已啟動 job：{status.job_id}｜{status.status}")
        return
    if args.jobs_command == "stop":
        plan = make_change_plan([{"action": "停止 job", "target": args.job_id}])
        if not require_confirm(plan):
            print("已取消操作")
            return
        status = stop_job(args.job_id, data_dir=core.data_dir)
        print(f"已停止 job：{status.job_id}｜{status.status}")
        return
    if args.jobs_command == "restart":
        plan = make_change_plan([{"action": "重啟 job", "target": args.job_id}])
        if not require_confirm(plan):
            print("已取消操作")
            return
        stop_job(args.job_id, data_dir=core.data_dir)
        status = start_job(args.job_id, data_dir=core.data_dir, heartbeat_interval_seconds=5)
        print(f"已重啟 job：{status.job_id}｜{status.status}")
        return
    if args.jobs_command == "status":
        status = status_job(args.job_id, data_dir=core.data_dir)
        print(f"job_id：{status.job_id}")
        print(f"狀態：{status.status}")
        print(f"last_heartbeat_ts：{status.last_heartbeat_ts}")
        print(f"last_error：{status.last_error}")
        print(f"last_event_id：{status.last_event_id}")
        return
    raise ValueError("請指定 jobs 指令")


def _handle_sandbox(core: AmonCore, args: argparse.Namespace) -> None:
    if args.sandbox_command != "exec":
        raise ValueError("請指定 sandbox 指令")

    loader = ConfigLoader(data_dir=core.data_dir)
    effective = loader.resolve(project_id=args.project).effective
    settings = parse_runner_settings(effective)
    client = SandboxRunnerClient(settings)

    code = Path(args.code_file).read_text(encoding="utf-8")

    inputs: list[dict[str, str]] = []
    for mapping in args.input_files:
        if "=" not in mapping:
            raise ValueError("--in 格式錯誤，需為 runner/path=local_file_path")
        runner_path, local_path = mapping.split("=", 1)
        content = Path(local_path).read_bytes()
        inputs.append(build_input_file(runner_path, content))

    result = client.run_code(language=args.language, code=code, input_files=inputs)
    written = decode_output_files(result.get("output_files", []), Path(args.out_dir))

    summary = {
        "id": result.get("id"),
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out"),
        "duration_ms": result.get("duration_ms"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
        "written_files": [str(path) for path in written],
    }
    print(yaml.safe_dump(summary, allow_unicode=True, sort_keys=False))
