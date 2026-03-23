from __future__ import annotations

from pathlib import Path
from typing import Any

from ...domain.entities import AgentProfile, ExecutorBinding, TaskDefinition, Template, ToolPolicy, WorkflowDefinition
from ..common import read_json, write_json
from ..migrations import bootstrap_manifest_storage

DEFINITION_TYPES = {
    "tasks": TaskDefinition,
    "agents": AgentProfile,
    "executors": ExecutorBinding,
    "workflows": WorkflowDefinition,
    "templates": Template,
    "tool_policies": ToolPolicy,
}


class DefinitionRepository:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.definitions_dir = self.project_root / ".amon" / "definitions"
        bootstrap_manifest_storage(project_root)

    def _path(self, entity_type: str, entity_id: str) -> Path:
        if entity_type not in DEFINITION_TYPES:
            raise KeyError(f"未知的 definition type：{entity_type}")
        return self.definitions_dir / entity_type / f"{entity_id}.json"

    def save(self, entity_type: str, entity: Any) -> Any:
        write_json(self._path(entity_type, entity.id), entity.to_dict())
        return entity

    def get(self, entity_type: str, entity_id: str) -> Any:
        payload = read_json(self._path(entity_type, entity_id), default={})
        return DEFINITION_TYPES[entity_type].from_dict(payload)

    def list(self, entity_type: str) -> list[Any]:
        if entity_type not in DEFINITION_TYPES:
            raise KeyError(f"未知的 definition type：{entity_type}")
        results: list[Any] = []
        for path in sorted((self.definitions_dir / entity_type).glob("*.json")):
            results.append(DEFINITION_TYPES[entity_type].from_dict(read_json(path, default={})))
        return results

    def soft_delete(self, entity_type: str, entity_id: str, *, in_use: bool = False) -> Any:
        entity = self.get(entity_type, entity_id)
        entity.update(status="deprecated" if in_use else "archived")
        return self.save(entity_type, entity)

    def restore(self, entity_type: str, entity_id: str, *, target_status: str = "active") -> Any:
        entity = self.get(entity_type, entity_id)
        entity.update(status=target_status)
        return self.save(entity_type, entity)
