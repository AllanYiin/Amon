"""Command line interface for Amon."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
        if args.command == "project":
            _handle_project(core, args)
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
