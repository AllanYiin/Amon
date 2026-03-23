"""Template instantiation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .library import BuiltinTemplate, TemplateLibrary


@dataclass(frozen=True)
class TemplateInstantiation:
    template_id: str
    template_name: str
    graph_payload: dict[str, Any]
    variables: dict[str, Any] = field(default_factory=dict)


def instantiate_builtin_template(
    template_id: str,
    variables: dict[str, Any] | None = None,
    *,
    library: TemplateLibrary | None = None,
) -> TemplateInstantiation:
    template_library = library or TemplateLibrary()
    template = template_library.get(template_id)
    return TemplateInstantiation(
        template_id=template.template_id,
        template_name=template.name,
        graph_payload=template_library.build_graph(template_id),
        variables=_merge_variables(template, variables),
    )


def _merge_variables(template: BuiltinTemplate, variables: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(template.defaults)
    merged.update(dict(variables or {}))
    return merged
