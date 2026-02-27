from __future__ import annotations

import re
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Protocol

from .config import ConfigLoader, read_yaml, write_yaml
from .models import ProviderError, build_provider


@dataclass
class ProjectConfigIdentity:
    project_id: str
    project_name: str
    config: dict[str, Any]


class LLMClient(Protocol):
    def generate_stream(self, messages: list[dict[str, str]], model: str | None = None) -> Iterable[str]:
        ...


def _contains_cjk(text: str) -> bool:
    return any("\u4e00" <= ch <= "\u9fff" for ch in text)


def _sanitize_slug_chars(text: str, *, keep_space: bool) -> str:
    if not text:
        return ""
    if keep_space:
        text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff _-]+", "", text)
        text = re.sub(r"[_-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    text = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff._-]+", "", text)
    text = re.sub(r"\s+", "", text)
    return text.strip("._-")


def _build_slug_default_client(*, model: str | None) -> tuple[LLMClient, str | None]:
    loader = ConfigLoader()
    config = loader.resolve().effective
    provider_name = str(config.get("amon", {}).get("provider") or "openai")
    provider_cfg = dict((config.get("providers", {}) or {}).get(provider_name) or {})
    resolved_model = model or provider_cfg.get("default_model") or provider_cfg.get("model")
    client = build_provider(provider_cfg, model=resolved_model)
    return client, resolved_model


def _collect_stream(llm_client: LLMClient, messages: list[dict[str, str]], model: str | None) -> str:
    return "".join(token for token in llm_client.generate_stream(messages, model=model)).strip()


def _slug_system_prompt() -> str:
    return (
        "你是專案資料夾命名助手。"
        "請把輸入 project_name 濃縮成可讀 slug，回傳 JSON：{\"slug\": string}。"
        "規則：中文最多10字，英文最多5 words，保留語意，不要加解釋。"
    )


def _parse_slug_response(raw: str) -> str:
    text = raw.strip()
    if not text:
        return ""
    payload: dict[str, Any] = {}
    if text.startswith("{"):
        payload = json.loads(text)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            payload = json.loads(text[start : end + 1])
    slug = str(payload.get("slug") or "").strip()
    return slug


def _summarize_slug_with_llm(
    project_name: str,
    *,
    llm_client: LLMClient | None,
    model: str | None,
) -> str:
    source = " ".join(str(project_name or "").split()).strip()
    if not source:
        return ""
    try:
        client = llm_client
        resolved_model = model
        if client is None:
            client, resolved_model = _build_slug_default_client(model=model)
        messages = [
            {"role": "system", "content": _slug_system_prompt()},
            {
                "role": "user",
                "content": json.dumps({"project_name": source, "output_schema": {"slug": "string"}}, ensure_ascii=False),
            },
        ]
        raw = _collect_stream(client, messages, resolved_model)
        return _parse_slug_response(raw)
    except (ProviderError, OSError, ValueError, json.JSONDecodeError):
        return ""


def _enforce_slug_limits(slug: str, *, fallback: str) -> str:
    cleaned = _sanitize_slug_chars(slug, keep_space=False)
    if not cleaned:
        cleaned = _sanitize_slug_chars(fallback, keep_space=False) or "project"
    if _contains_cjk(cleaned):
        if len(cleaned) <= 10:
            return cleaned
        return cleaned[:10]
    words = [part for part in cleaned.replace("_", "-").split("-") if part]
    if not words:
        return "project"
    return "-".join(words[:5]).lower()


def generate_project_slug(
    project_name: str,
    *,
    fallback: str = "project",
    llm_client: LLMClient | None = None,
    model: str | None = None,
) -> str:
    source = str(project_name or "").strip() or fallback
    llm_slug = _summarize_slug_with_llm(source, llm_client=llm_client, model=model)
    return _enforce_slug_limits(llm_slug or source, fallback=fallback)


def uniquify_project_slug(base_slug: str, *, root_dir: Path, max_attempts: int = 5000) -> str:
    base = _sanitize_slug_chars(base_slug, keep_space=False) or "project"
    if not (root_dir / base).exists():
        return base

    cjk = _contains_cjk(base)
    for idx in range(1, max_attempts + 1):
        suffix = f"·{idx:03d}" if cjk else f"-{idx:03d}"
        if cjk:
            candidate_base = base[: max(1, 10 - len(suffix))]
            candidate = f"{candidate_base}{suffix}"
        else:
            candidate = f"{base}{suffix}"
        if not (root_dir / candidate).exists():
            return candidate
    raise RuntimeError("無法產生唯一 project slug")


def _legacy_project_folder(folder_name: str) -> bool:
    return bool(re.match(r"^project-(\d+|[a-z0-9]+)$", folder_name))


def migrate_legacy_project_folder(project_path: Path) -> Path:
    config_path = project_path / "amon.project.yaml"
    if not config_path.exists() or not project_path.is_dir():
        return project_path

    data = read_yaml(config_path)
    amon = data.setdefault("amon", {})
    folder_name = project_path.name
    project_id = str(amon.get("project_id") or "").strip()
    if not _legacy_project_folder(folder_name):
        return project_path
    if project_id and project_id != folder_name:
        return project_path

    stable_project_id = project_id or folder_name
    project_name = str(amon.get("project_name") or "").strip() or stable_project_id
    base_slug = generate_project_slug(project_name, fallback=stable_project_id)
    target_slug = uniquify_project_slug(base_slug, root_dir=project_path.parent)
    target_path = project_path.parent / target_slug

    amon["project_id"] = stable_project_id
    amon["project_name"] = project_name
    amon["project_slug"] = target_slug

    if target_path != project_path:
        if target_path.exists():
            raise FileExistsError(f"遷移目標資料夾已存在：{target_path}")
        try:
            project_path.rename(target_path)
        except OSError as exc:
            raise OSError(f"專案資料夾遷移失敗：{project_path} -> {target_path}") from exc

    write_yaml(target_path / "amon.project.yaml", data)
    return target_path


def load_project_config(project_path: Path) -> ProjectConfigIdentity:
    config_path = project_path / "amon.project.yaml"
    config = read_yaml(config_path)
    amon_config = config.setdefault("amon", {})

    project_id = str(amon_config.get("project_id") or "").strip()
    if not project_id:
        project_id = project_path.name
        amon_config["project_id"] = project_id

    project_name = str(amon_config.get("project_name") or "").strip() or project_id
    if not amon_config.get("project_name"):
        amon_config["project_name"] = project_name

    if not amon_config.get("project_slug"):
        amon_config["project_slug"] = project_path.name

    write_yaml(config_path, config)
    return ProjectConfigIdentity(project_id=project_id, project_name=project_name, config=config)


class ProjectRegistry:
    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir
        self._id_to_path: dict[str, Path] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def scan(self) -> None:
        self._id_to_path = {}
        self._meta = {}
        if not self.root_dir.exists():
            return
        index_map = self._load_path_to_id_index()
        candidates = [child for child in self.root_dir.iterdir() if child.is_dir()]
        for child in candidates:
            config_path = child / "amon.project.yaml"
            if not config_path.exists():
                continue
            self._backfill_project_id_from_index(config_path, child, index_map)
            migrated = migrate_legacy_project_folder(child)
            identity = load_project_config(migrated)
            self._id_to_path[identity.project_id] = migrated
            self._meta[identity.project_id] = {
                "project_id": identity.project_id,
                "project_name": identity.project_name,
                "project_path": str(migrated),
            }

    def get_path(self, project_id: str) -> Path:
        project_path = self._id_to_path.get(project_id)
        if project_path is None:
            raise KeyError(f"找不到專案：{project_id}")
        return project_path

    def list_projects(self) -> list[dict[str, Any]]:
        return [self._meta[project_id] for project_id in sorted(self._meta.keys())]

    def _load_path_to_id_index(self) -> dict[str, str]:
        cache_path = self.root_dir.parent / "cache" / "projects_index.json"
        if not cache_path.exists():
            return {}
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        mapping: dict[str, str] = {}
        for item in payload.get("projects", []) if isinstance(payload, dict) else []:
            project_id = str(item.get("project_id") or "").strip()
            path = str(item.get("path") or "").strip()
            if not project_id or not path:
                continue
            mapping[str(Path(path).resolve())] = project_id
        return mapping

    @staticmethod
    def _backfill_project_id_from_index(config_path: Path, project_path: Path, index_map: dict[str, str]) -> None:
        if not index_map:
            return
        data = read_yaml(config_path)
        amon = data.setdefault("amon", {})
        current = str(amon.get("project_id") or "").strip()
        if current:
            return
        mapped = index_map.get(str(project_path.resolve()))
        if not mapped:
            return
        amon["project_id"] = mapped
        if not amon.get("project_name"):
            amon["project_name"] = str(mapped)
        write_yaml(config_path, data)
