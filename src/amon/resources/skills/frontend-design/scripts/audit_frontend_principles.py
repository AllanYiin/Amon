#!/usr/bin/env python3
"""Audit a frontend workspace for journey/flow and Gestalt evidence."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

TEXT_EXTENSIONS = {
    ".astro",
    ".css",
    ".html",
    ".htm",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mdx",
    ".svelte",
    ".ts",
    ".tsx",
    ".txt",
    ".vue",
    ".yaml",
    ".yml",
}
CODE_EXTENSIONS = {
    ".astro",
    ".css",
    ".html",
    ".htm",
    ".js",
    ".jsx",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}
DOC_EXTENSIONS = {".json", ".md", ".mdx", ".txt", ".yaml", ".yml"}
IGNORE_DIRS = {
    ".git",
    ".idea",
    ".next",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "logs",
    "node_modules",
    "out",
    "tmp",
}

CHECK_ORDER = [
    "journey_map_structure",
    "system_status_visibility",
    "guideline_doc_structure",
    "gestalt_proximity_common_region",
    "gestalt_similarity",
    "gestalt_figure_ground",
    "gestalt_continuation",
    "anti_pattern_signals",
]

MANUAL_REVIEW_ITEMS = [
    "人工確認 Closure：畫面是否靠缺口暗示整體，不靠額外文字補救理解。",
    "人工確認 Common Fate：動畫或移動中的元素是否真的屬於同一群組，且不會誤導焦點。",
    "人工確認 Praegnanz：複雜畫面是否被簡化成清楚、可掃描的形狀與層次。",
]
ALLOW_ANTI_PATTERN_MARKER = "audit: allow-anti-pattern"


@dataclass(frozen=True)
class Evidence:
    path: str
    line: int
    snippet: str

    def to_dict(self) -> dict[str, object]:
        return {"path": self.path, "line": self.line, "snippet": self.snippet}


PATTERN_GROUPS = {
    "journey_actor": [
        r"\bpersona\b",
        r"\buser\b",
        r"\bactor\b",
        "使用者",
        "角色",
        "目標客群",
    ],
    "journey_scenario": [
        r"\bscenario\b",
        r"\bgoal\b",
        r"\bjob to be done\b",
        r"\btask\b",
        "情境",
        "任務",
        "目標",
    ],
    "journey_steps": [
        r"\bjourney\b",
        r"\buser flow\b",
        r"\bwireflow\b",
        r"\bphase\b",
        r"\bstep\b",
        r"\btouchpoint\b",
        r"\bscreen\b",
        "旅程",
        "流程",
        "步驟",
        "階段",
        "觸點",
    ],
    "journey_evidence": [
        r"\bthinking\b",
        r"\bfeeling\b",
        r"\bsaying\b",
        r"\binsight\b",
        r"\bpain point\b",
        r"\bopportunit(y|ies)\b",
        "想法",
        "感受",
        "洞察",
        "痛點",
        "機會",
        "回饋",
    ],
    "system_status_visibility": [
        r"aria-current\s*=\s*['\"]step['\"]",
        r"aria-current",
        r"\bprogress(bar)?\b",
        r"\bstepper\b",
        r"\bcurrent step\b",
        r"\bcompleted\b",
        r"\bnext step\b",
        "目前步驟",
        "下一步",
        "進度",
        "完成",
        "loading",
    ],
    "gestalt_proximity_common_region": [
        r"\bgap-[a-z0-9-]+\b",
        r"\bspace-[xy]-[a-z0-9-]+\b",
        r"\bp-(x|y|t|r|b|l)?-?[a-z0-9-]+\b",
        r"<section\b",
        r"<fieldset\b",
        r"<ul\b",
        "分組",
        "群組",
        "區塊",
        "間距",
    ],
    "gestalt_similarity": [
        r"\bvariant\b",
        r"\bvariants\b",
        r"\bdesign token\b",
        r"\btokens\b",
        r"--(background|surface|text|primary|secondary)",
        r"\bclass-variance-authority\b",
        "一致",
        "同一套",
        "變體",
        "語意 token",
    ],
    "gestalt_figure_ground": [
        r"--background\b",
        r"--surface\b",
        r"--text\b",
        r"\bcontrast\b",
        r"\bforeground\b",
        r"\bbackground\b",
        "前景",
        "背景",
        "對比",
        "層次",
    ],
    "gestalt_continuation": [
        r"\btimeline\b",
        r"\bstepper\b",
        r"\bconnector\b",
        r"\bsequence\b",
        r"\bpath\b",
        r"<ol\b",
        "時間線",
        "時間軸",
        "導引",
        "連接",
        "順序",
        "流程線",
    ],
}

GUIDELINE_SECTION_PATTERNS = {
    "usage": [r"^#+\s*usage\b", "使用情境", "適用情境", "使用規範"],
    "layout": [r"^#+\s*layout\b", "版面", "佈局", "間距規範"],
    "anatomy": [r"^#+\s*anatomy\b", "結構拆解", "元件結構", "構成"],
    "states_spec": [r"^#+\s*states?\b", r"^#+\s*spec\b", "狀態", "規格"],
    "interaction": [r"^#+\s*interaction\b", "互動", "行為規範", "鍵盤操作"],
    "content_asset": [r"^#+\s*content\b", r"^#+\s*asset\b", "文案", "資產"],
}

ANTI_PATTERN_RULES = {
    "generic-font-stack": {
        "message": "偵測到過度通用的字體選擇，可能落回 skill 已禁止的 generic AI aesthetic。",
        "patterns": [
            r"font-family[^;\n]*(inter|roboto|arial|open sans|system-ui)",
            r"from ['\"]next/font/google['\"].*(Inter|Roboto)",
            r"fonts\.googleapis\.com.*(Inter|Roboto|Open\+Sans)",
        ],
    },
    "gradient-text": {
        "message": "偵測到常見的 gradient text 手法，請確認不是為了追求花俏而犧牲可讀性。",
        "patterns": [
            r"bg-clip-text",
            r"background-clip\s*:\s*text",
            r"text-transparent",
        ],
    },
    "pure-black-white": {
        "message": "偵測到純黑/純白色碼，請確認不是直接套用廉價高對比而忽略層次。",
        "patterns": [
            r"#[0]{3,6}\b",
            r"#[fF]{3,6}\b",
            r"rgb\(\s*0\s*,\s*0\s*,\s*0\s*\)",
            r"rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)",
        ],
    },
    "generic-cta-copy": {
        "message": "偵測到模糊 CTA 文案，應改成對任務更具體的動詞或結果。",
        "patterns": [
            r">\s*(OK|Submit|Yes|No)\s*<",
            r"['\"](OK|Submit|Yes|No)['\"]",
        ],
    },
    "generic-error-copy": {
        "message": "偵測到過度籠統的錯誤訊息，應補上原因、修正方式或 recovery action。",
        "patterns": [
            r"something went wrong",
            r"an error occurred",
            r"invalid input",
        ],
    },
    "glassmorphism-overuse": {
        "message": "偵測到玻璃擬態相關樣式，請確認不是無差別套用造成資訊層次模糊。",
        "patterns": [
            r"backdrop-blur",
            r"backdrop-filter",
            r"glassmorphism",
        ],
    },
}


def iter_text_files(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORE_DIRS for part in relative_parts):
            continue
        if path.is_file() and path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def iter_doc_files(root: Path) -> Iterable[Path]:
    for path in iter_text_files(root):
        if path.suffix.lower() in DOC_EXTENSIONS:
            yield path


def iter_code_files(root: Path) -> Iterable[Path]:
    for path in iter_text_files(root):
        if path.suffix.lower() in CODE_EXTENSIONS:
            yield path


def find_matches(path: Path, patterns: list[str]) -> list[Evidence]:
    text = path.read_text(encoding="utf-8")
    matches: list[Evidence] = []
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if any(regex.search(line) for regex in compiled):
            matches.append(
                Evidence(
                    path=str(path),
                    line=line_no,
                    snippet=line[:160],
                )
            )
    return matches


def collect_group_matches(root: Path, group_name: str, docs_only: bool = False) -> list[Evidence]:
    files = iter_doc_files(root) if docs_only else iter_text_files(root)
    evidence: list[Evidence] = []
    for path in files:
        evidence.extend(find_matches(path, PATTERN_GROUPS[group_name]))
    return evidence


def collect_group_matches_by_file(root: Path, group_name: str) -> dict[str, list[Evidence]]:
    matches_by_file: dict[str, list[Evidence]] = {}
    for path in iter_doc_files(root):
        matches = find_matches(path, PATTERN_GROUPS[group_name])
        if matches:
            matches_by_file[str(path)] = matches
    return matches_by_file


def collect_matches_by_file(path: Path, patterns: list[str]) -> list[Evidence]:
    return find_matches(path, patterns)


def evaluate_journey(root: Path) -> tuple[str, str, list[Evidence]]:
    actor_by_file = collect_group_matches_by_file(root, "journey_actor")
    scenario_by_file = collect_group_matches_by_file(root, "journey_scenario")
    steps_by_file = collect_group_matches_by_file(root, "journey_steps")
    context_by_file = collect_group_matches_by_file(root, "journey_evidence")

    shared_files = sorted(
        set(actor_by_file) & set(scenario_by_file) & set(steps_by_file)
    )
    if shared_files:
        best_file = max(
            shared_files,
            key=lambda path: len(actor_by_file[path]) + len(scenario_by_file[path]) + len(steps_by_file[path]),
        )
        evidence = (
            actor_by_file[best_file][:1]
            + scenario_by_file[best_file][:1]
            + steps_by_file[best_file][:2]
            + context_by_file.get(best_file, [])[:1]
        )[:5]
        if context_by_file.get(best_file):
            return (
                "pass",
                "找到含 persona/scenario/steps 並帶有想法、感受或洞察欄位的 journey/flow 證據。",
                evidence,
            )
        return (
            "pass",
            "找到 persona/scenario/steps 的 journey/flow 文件；建議補上 thinking/feeling/insight 以貼近 NNG map 結構。",
            evidence,
        )

    actor = collect_group_matches(root, "journey_actor", docs_only=True)
    scenario = collect_group_matches(root, "journey_scenario", docs_only=True)
    steps = collect_group_matches(root, "journey_steps", docs_only=True)
    context = collect_group_matches(root, "journey_evidence", docs_only=True)
    evidence = (actor[:1] + scenario[:1] + steps[:2] + context[:1])[:5]

    missing = []
    if not actor:
        missing.append("persona/actor")
    if not scenario:
        missing.append("scenario/goal")
    if not steps:
        missing.append("steps/phases")
    return (
        "fail",
        f"缺少可驗證的 journey/flow 結構：{', '.join(missing)}。",
        evidence,
    )


def evaluate_pattern(root: Path, check_id: str) -> tuple[str, str, list[Evidence]]:
    evidence = collect_group_matches(root, check_id)
    if evidence:
        messages = {
            "system_status_visibility": "找到目前步驟、進度或 next/completed 等系統狀態可見性證據。",
            "gestalt_proximity_common_region": "找到以間距、section、fieldset 或群組語意建立鄰近/共同區域的證據。",
            "gestalt_similarity": "找到 token、variant 或共享樣式系統，符合相似性原則。",
            "gestalt_figure_ground": "找到背景/前景/對比 token 或敘述，符合 figure-ground 原則。",
            "gestalt_continuation": "找到 stepper、timeline、ordered sequence 或連接線等連續性證據。",
        }
        return ("pass", messages[check_id], evidence[:5])

    warnings = {
        "system_status_visibility": "找不到 progress、aria-current 或 next/completed 等狀態回饋；多步驟介面通常需要明確回饋。",
        "gestalt_proximity_common_region": "找不到穩定的間距/群組訊號；可能違反 proximity/common region。",
        "gestalt_similarity": "找不到 token/variant/共享元件訊號；可能缺乏 similarity 與一致性。",
        "gestalt_figure_ground": "找不到背景/前景/對比訊號；figure-ground 可能不足。",
        "gestalt_continuation": "找不到明確的視覺路徑或順序訊號；請人工確認使用者視線能順著流程前進。",
    }
    level = "warn" if check_id == "gestalt_continuation" else "fail"
    return (level, warnings[check_id], [])


def evaluate_guideline_docs(root: Path, require_guideline_docs: bool) -> tuple[str, str, list[Evidence]]:
    candidates: list[tuple[Path, dict[str, list[Evidence]]]] = []
    for path in iter_doc_files(root):
        section_hits = {
            section: collect_matches_by_file(path, patterns)
            for section, patterns in GUIDELINE_SECTION_PATTERNS.items()
        }
        matched_sections = sum(bool(hits) for hits in section_hits.values())
        path_hint = path.name.lower()
        looks_like_guideline = any(
            token in path_hint for token in ("guideline", "spec", "component", "design-system", "ui")
        )
        if looks_like_guideline or matched_sections >= 3:
            candidates.append((path, section_hits))

    if not candidates:
        if require_guideline_docs:
            return (
                "fail",
                "此 audit run 要求 guideline 文件，但找不到包含 Usage/Layout/Anatomy/States/Interaction 的文件。",
                [],
            )
        return (
            "pass",
            "本次未強制要求 guideline 文件；若是元件庫或 design system，請加上 --require-guideline-docs。",
            [],
        )

    best_path, best_hits = max(
        candidates,
        key=lambda item: sum(bool(hits) for hits in item[1].values()),
    )
    matched_sections = [section for section, hits in best_hits.items() if hits]
    evidence = []
    for section in ("usage", "layout", "anatomy", "states_spec", "interaction", "content_asset"):
        evidence.extend(best_hits[section][:1])
    evidence = evidence[:6]

    if len(matched_sections) >= 5:
        return (
            "pass",
            f"找到結構完整的 guideline 文件：{Path(best_path).name}。",
            evidence,
        )

    missing = [
        section
        for section in ("usage", "layout", "anatomy", "states_spec", "interaction", "content_asset")
        if not best_hits[section]
    ]
    status = "fail" if require_guideline_docs else "warn"
    return (
        status,
        f"找到 guideline 候選文件，但缺少關鍵段落：{', '.join(missing)}。",
        evidence,
    )


def evaluate_anti_patterns(root: Path) -> tuple[str, str, list[Evidence]]:
    evidence: list[Evidence] = []
    for path in iter_code_files(root):
        lines = path.read_text(encoding="utf-8").splitlines()
        allow_window = 0
        previous_line = ""
        for rule_id, rule in ANTI_PATTERN_RULES.items():
            compiled = [re.compile(pattern, re.IGNORECASE | re.MULTILINE) for pattern in rule["patterns"]]
            allow_window = 0
            previous_line = ""
            for line_no, raw_line in enumerate(lines, start=1):
                stripped = raw_line.strip()
                if not stripped:
                    previous_line = stripped
                    continue
                if ALLOW_ANTI_PATTERN_MARKER in previous_line.lower():
                    allow_window = 4
                previous_line = stripped
                if allow_window > 0:
                    allow_window -= 1
                    continue
                if any(regex.search(stripped) for regex in compiled):
                    evidence.append(
                        Evidence(
                            path=str(path),
                            line=line_no,
                            snippet=f"[{rule_id}] {stripped[:140]}",
                        )
                    )
                    break

    if evidence:
        return (
            "warn",
            "偵測到可能的 AI slop / UX copy 反模式，請逐條確認是否違反設計意圖與可讀性。",
            evidence[:8],
        )

    return (
        "pass",
        "未偵測到明顯的 generic font、gradient text、模糊 CTA 或籠統錯誤文案反模式。",
        [],
    )


def audit_workspace(root: Path, require_guideline_docs: bool = False) -> dict[str, object]:
    results: list[dict[str, object]] = []

    journey_status, journey_message, journey_evidence = evaluate_journey(root)
    results.append(
        {
            "id": "journey_map_structure",
            "status": journey_status,
            "message": journey_message,
            "evidence": [item.to_dict() for item in journey_evidence],
        }
    )

    status_visibility_status, status_visibility_message, status_visibility_evidence = evaluate_pattern(
        root,
        "system_status_visibility",
    )
    results.append(
        {
            "id": "system_status_visibility",
            "status": status_visibility_status,
            "message": status_visibility_message,
            "evidence": [item.to_dict() for item in status_visibility_evidence],
        }
    )

    guideline_status, guideline_message, guideline_evidence = evaluate_guideline_docs(
        root,
        require_guideline_docs=require_guideline_docs,
    )
    results.append(
        {
            "id": "guideline_doc_structure",
            "status": guideline_status,
            "message": guideline_message,
            "evidence": [item.to_dict() for item in guideline_evidence],
        }
    )

    for check_id in (
        "gestalt_proximity_common_region",
        "gestalt_similarity",
        "gestalt_figure_ground",
        "gestalt_continuation",
    ):
        status, message, evidence = evaluate_pattern(root, check_id)
        results.append(
            {
                "id": check_id,
                "status": status,
                "message": message,
                "evidence": [item.to_dict() for item in evidence],
            }
        )

    anti_status, anti_message, anti_evidence = evaluate_anti_patterns(root)
    results.append(
        {
            "id": "anti_pattern_signals",
            "status": anti_status,
            "message": anti_message,
            "evidence": [item.to_dict() for item in anti_evidence],
        }
    )

    summary = {"pass": 0, "warn": 0, "fail": 0}
    for result in results:
        summary[result["status"]] += 1

    return {
        "root": str(root),
        "results": results,
        "summary": summary,
        "manual_review": MANUAL_REVIEW_ITEMS,
    }


def print_text_report(report: dict[str, object]) -> None:
    print(f"AUDIT_ROOT {report['root']}")
    for result in report["results"]:
        print(f"[{result['status'].upper()}] {result['id']}: {result['message']}")
        for evidence in result["evidence"]:
            print(f"  - {evidence['path']}:{evidence['line']} {evidence['snippet']}")
    print("MANUAL_REVIEW")
    for item in report["manual_review"]:
        print(f"  - {item}")
    summary = report["summary"]
    print(
        "SUMMARY "
        f"pass={summary['pass']} warn={summary['warn']} fail={summary['fail']}"
    )


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except ValueError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit a frontend workspace for journey/flow structure and Gestalt-aligned evidence."
    )
    parser.add_argument("root", nargs="?", default=".", help="Workspace root to audit")
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format",
    )
    parser.add_argument(
        "--strict-warnings",
        action="store_true",
        help="Return non-zero when warnings exist",
    )
    parser.add_argument(
        "--require-guideline-docs",
        action="store_true",
        help="Fail when reusable-component guideline documents are missing or incomplete.",
    )
    args = parser.parse_args()

    configure_stdout()
    root = Path(args.root).resolve()
    report = audit_workspace(root, require_guideline_docs=args.require_guideline_docs)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)

    fail_count = report["summary"]["fail"]
    warn_count = report["summary"]["warn"]
    if fail_count:
        return 1
    if args.strict_warnings and warn_count:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
