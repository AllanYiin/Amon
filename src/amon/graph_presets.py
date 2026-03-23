from __future__ import annotations

from amon.templates.builtin_graphs import (
    TEAMWORK_EXECUTION_SYSTEM_PROMPT,
    TEAMWORK_SYSTEM_PROMPTS,
    TEAM_ROLE_PROTOTYPES,
    team_role_prototypes_json,
)
from amon.templates.instantiate import instantiate_builtin_template


def build_single_graph_payload() -> dict:
    return instantiate_builtin_template("single").graph_payload


def build_self_critique_graph_payload() -> dict:
    return instantiate_builtin_template("self_critique").graph_payload


def build_team_graph_payload() -> dict:
    return instantiate_builtin_template("team").graph_payload


__all__ = [
    "TEAMWORK_EXECUTION_SYSTEM_PROMPT",
    "TEAMWORK_SYSTEM_PROMPTS",
    "TEAM_ROLE_PROTOTYPES",
    "build_self_critique_graph_payload",
    "build_single_graph_payload",
    "build_team_graph_payload",
    "team_role_prototypes_json",
]
