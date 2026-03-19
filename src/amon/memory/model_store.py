from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_AMON_HOME = Path("~/.amon").expanduser()
MODEL_CACHE_ENV = "AMON_MODEL_CACHE_DIR"
JINA_EMBEDDINGS_V5_REVISION = "f78e3eca89d031542d392ecba158b248caa1e8c7"
JINA_RERANKER_V3_REVISION = "a871c62a64b9f5df7ed7e10d4a0d6c7a64e81a79"
JINA_RERANKER_V3_FILES = (
    "added_tokens.json",
    "config.json",
    "generation_config.json",
    "merges.txt",
    "model.safetensors",
    "modeling.py",
    "special_tokens_map.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "vocab.json",
)


@dataclass(frozen=True, slots=True)
class ModelSpec:
    repo_id: str
    revision: str
    files: tuple[str, ...]


def resolve_model_cache_dir() -> Path:
    explicit = os.environ.get(MODEL_CACHE_ENV)
    if explicit:
        return Path(explicit).expanduser()
    amon_home = Path(os.environ.get("AMON_HOME", str(DEFAULT_AMON_HOME))).expanduser()
    return amon_home / "cache" / "models"


class LocalModelStore:
    def __init__(
        self,
        base_dir: str | Path | None = None,
        *,
        downloader: Callable[[str, Path], None] | None = None,
    ) -> None:
        self.base_dir = Path(base_dir).expanduser() if base_dir else resolve_model_cache_dir()
        self._downloader = downloader or self._download_file

    def ensure_model(self, spec: ModelSpec) -> Path:
        model_dir = self._model_dir(spec.repo_id, spec.revision)
        model_dir.mkdir(parents=True, exist_ok=True)
        for relative_path in spec.files:
            destination = model_dir / relative_path
            if destination.exists() and destination.stat().st_size > 0:
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            self._downloader(self._resolve_url(spec.repo_id, spec.revision, relative_path), destination)
        return model_dir

    def _model_dir(self, repo_id: str, revision: str) -> Path:
        safe_repo_id = repo_id.replace("/", "__")
        return self.base_dir / safe_repo_id / revision

    @staticmethod
    def _resolve_url(repo_id: str, revision: str, relative_path: str) -> str:
        quoted_path = quote(relative_path, safe="/")
        return f"https://huggingface.co/{repo_id}/resolve/{revision}/{quoted_path}?download=true"

    @staticmethod
    def _download_file(url: str, destination: Path) -> None:
        request = Request(url, headers={"User-Agent": "amon-model-store/0.1"})
        temp_path: str | None = None
        with urlopen(request) as response:
            with tempfile.NamedTemporaryFile(delete=False, dir=str(destination.parent)) as temp_handle:
                temp_path = temp_handle.name
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    temp_handle.write(chunk)
        assert temp_path is not None
        os.replace(temp_path, destination)


def default_onnx_files(file_name: str) -> tuple[str, ...]:
    onnx_path = f"onnx/{file_name}"
    files = [
        "config.json",
        "tokenizer.json",
        "tokenizer_config.json",
        "configuration_eurobert.py",
        "modeling_eurobert.py",
        onnx_path,
    ]
    if file_name.endswith(".onnx"):
        data_file = f"{onnx_path}_data"
        files.append(data_file)
    return tuple(files)


KNOWN_MODEL_SPECS: dict[str, ModelSpec] = {
    "jina-embeddings-v5-text-nano-retrieval": ModelSpec(
        repo_id="jinaai/jina-embeddings-v5-text-nano-retrieval",
        revision=JINA_EMBEDDINGS_V5_REVISION,
        files=default_onnx_files("model.onnx"),
    ),
    "jina-reranker-v3": ModelSpec(
        repo_id="jinaai/jina-reranker-v3",
        revision=JINA_RERANKER_V3_REVISION,
        files=JINA_RERANKER_V3_FILES,
    ),
}

KNOWN_MODEL_ALIASES: dict[str, str] = {
    "embedding": "jina-embeddings-v5-text-nano-retrieval",
    "embedder": "jina-embeddings-v5-text-nano-retrieval",
    "jina-embeddings": "jina-embeddings-v5-text-nano-retrieval",
    "reranker": "jina-reranker-v3",
}


def list_known_models() -> list[str]:
    return sorted(KNOWN_MODEL_SPECS)


def resolve_model_specs(targets: Sequence[str] | None = None) -> list[tuple[str, ModelSpec]]:
    normalized_targets = [str(target).strip() for target in (targets or ()) if str(target).strip()]
    if not normalized_targets or any(target == "all" for target in normalized_targets):
        return [(name, KNOWN_MODEL_SPECS[name]) for name in list_known_models()]
    resolved_names: list[str] = []
    for target in normalized_targets:
        model_name = KNOWN_MODEL_ALIASES.get(target, target)
        if model_name not in KNOWN_MODEL_SPECS:
            raise ValueError(f"未知模型：{target}")
        if model_name not in resolved_names:
            resolved_names.append(model_name)
    return [(name, KNOWN_MODEL_SPECS[name]) for name in resolved_names]
