"""Legacy taskgraph/preset importer backed by the built-in template library."""

from __future__ import annotations

import json
from typing import Any

from amon.templates.instantiate import instantiate_builtin_template
from amon.templates.library import TemplateLibrary


def import_legacy_graph_payload(
    graph_payload: dict[str, Any],
    *,
    library: TemplateLibrary | None = None,
) -> dict[str, Any]:
    template_library = library or TemplateLibrary()
    normalized_input = _normalize_graph(graph_payload)
    for template_id in template_library.list_template_ids():
        instantiation = instantiate_builtin_template(template_id, library=template_library)
        if _normalize_graph(instantiation.graph_payload) == normalized_input:
            return {
                "template_id": template_id,
                "template_name": instantiation.template_name,
                "graph_payload": instantiation.graph_payload,
                "source": "builtin_template",
            }
    return {
        "template_id": None,
        "template_name": None,
        "graph_payload": json.loads(json.dumps(graph_payload, ensure_ascii=False)),
        "source": "legacy_graph",
    }


def _normalize_graph(graph_payload: dict[str, Any]) -> dict[str, Any]:
    normalized = json.loads(json.dumps(graph_payload, ensure_ascii=False))
    normalized.pop("version", None)
    return normalized
