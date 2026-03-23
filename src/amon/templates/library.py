"""Built-in workflow template library for Stage 4 compatibility."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .builtin_graphs import (
    build_self_critique_graph_payload,
    build_single_graph_payload,
    build_team_graph_payload,
)


TemplateBuilder = Callable[[], dict[str, Any]]


@dataclass(frozen=True)
class BuiltinTemplate:
    template_id: str
    name: str
    description: str
    builder: str
    parameters: dict[str, Any] = field(default_factory=dict)
    defaults: dict[str, Any] = field(default_factory=dict)


_BUILDERS: dict[str, TemplateBuilder] = {
    "single": build_single_graph_payload,
    "self_critique": build_self_critique_graph_payload,
    "team": build_team_graph_payload,
}


class TemplateLibrary:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parent
        self._templates = self._load_templates()

    def list_templates(self) -> list[BuiltinTemplate]:
        return [self._templates[key] for key in sorted(self._templates)]

    def list_template_ids(self) -> list[str]:
        return [template.template_id for template in self.list_templates()]

    def get(self, template_id: str) -> BuiltinTemplate:
        try:
            return self._templates[template_id]
        except KeyError as exc:
            raise KeyError(f"未知的 template：{template_id}") from exc

    def build_graph(self, template_id: str) -> dict[str, Any]:
        template = self.get(template_id)
        return _deep_copy(_BUILDERS[template.builder]())

    def _load_templates(self) -> dict[str, BuiltinTemplate]:
        templates: dict[str, BuiltinTemplate] = {}
        for path in sorted(self.root.glob("*.json")):
            payload = json.loads(path.read_text(encoding="utf-8"))
            template = BuiltinTemplate(
                template_id=str(payload.get("id") or path.stem),
                name=str(payload.get("name") or path.stem),
                description=str(payload.get("description") or ""),
                builder=str(payload.get("builder") or path.stem),
                parameters=dict(payload.get("parameters") or {}),
                defaults=dict(payload.get("defaults") or {}),
            )
            if template.builder not in _BUILDERS:
                raise ValueError(f"template builder 不存在：{template.builder}")
            templates[template.template_id] = template
        return templates


def _deep_copy(payload: Any) -> Any:
    return json.loads(json.dumps(payload, ensure_ascii=False))
