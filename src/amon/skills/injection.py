from __future__ import annotations

from typing import Any

_SEGMENT_ORDER = ("system_prefix", "run_constraints", "tool_policy_hint")


def _extract_body(content: str) -> str:
    if not content.startswith("---"):
        return content.strip()
    lines = content.splitlines()
    if len(lines) < 3:
        return content.strip()
    try:
        end_index = lines[1:].index("---") + 1
    except ValueError:
        return content.strip()
    return "\n".join(lines[end_index + 1 :]).strip()


def _normalize_targets(frontmatter: dict[str, Any]) -> list[str]:
    raw_targets = frontmatter.get("inject_to") or frontmatter.get("injection_target")
    if isinstance(raw_targets, str):
        tokens = [raw_targets]
    elif isinstance(raw_targets, list):
        tokens = [str(item) for item in raw_targets]
    else:
        tokens = ["system_prefix"]

    alias = {
        "system": "system_prefix",
        "system_prefix": "system_prefix",
        "run": "run_constraints",
        "run_constraints": "run_constraints",
        "tool": "tool_policy_hint",
        "tool_policy": "tool_policy_hint",
        "tool_policy_hint": "tool_policy_hint",
    }

    normalized: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        key = alias.get(token.strip().lower())
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    if "run_constraints" not in seen and ("run_constraints" in frontmatter or "constraints" in frontmatter):
        normalized.append("run_constraints")
    if "tool_policy_hint" not in seen and ("tool_policy" in frontmatter or "tools" in frontmatter):
        normalized.append("tool_policy_hint")
    return normalized or ["system_prefix"]


def _skill_name(skill: dict[str, Any], frontmatter: dict[str, Any]) -> str:
    return str(frontmatter.get("name") or skill.get("name") or "")


def _skill_description(skill: dict[str, Any], frontmatter: dict[str, Any]) -> str:
    return str(frontmatter.get("description") or skill.get("description") or "").strip() or "無描述"


def build_system_prefix_injection(skills: list[dict[str, Any]]) -> str:
    if not skills:
        return ""
    lines = ["## Skills (frontmatter)"]
    for skill in skills:
        frontmatter = skill.get("frontmatter") if isinstance(skill.get("frontmatter"), dict) else {}
        lines.append(f"- {_skill_name(skill, frontmatter)}：{_skill_description(skill, frontmatter)}")
    return "\n".join(lines)


def build_skill_injection_preview(skills: list[dict[str, Any]]) -> dict[str, Any]:
    by_segment: dict[str, list[str]] = {key: [] for key in _SEGMENT_ORDER}
    skill_previews: list[dict[str, Any]] = []

    for skill in skills:
        frontmatter = skill.get("frontmatter") if isinstance(skill.get("frontmatter"), dict) else {}
        name = _skill_name(skill, frontmatter)
        description = _skill_description(skill, frontmatter)
        body = _extract_body(str(skill.get("content") or ""))
        targets = _normalize_targets(frontmatter)

        preview_text = body or description
        for target in targets:
            by_segment[target].append(f"[{name}]\n{preview_text}")

        skill_previews.append(
            {
                "name": name,
                "source": skill.get("source"),
                "path": skill.get("path"),
                "frontmatter": frontmatter,
                "targets": targets,
                "injected_text": preview_text,
            }
        )

    segment_payload = []
    for segment in _SEGMENT_ORDER:
        joined = "\n\n".join(by_segment[segment]).strip()
        if joined:
            segment_payload.append({"segment": segment, "text": joined})

    return {
        "skills": skill_previews,
        "segments": segment_payload,
        "system_prefix": build_system_prefix_injection(skills),
    }
