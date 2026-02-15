"""Native tool manifest parsing and loader."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.util
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml

from amon._tooling_legacy import ToolingError, ensure_tool_name
from .types import ToolCall, ToolResult, ToolSpec
from .registry import ToolRegistry


_REQUIRED_FIELDS = ("name", "version", "description", "risk", "input_schema", "default_permission")
_VALID_PERMISSIONS = ("allow", "ask", "deny")


@dataclass(frozen=True)
class NativeToolManifest:
    name: str
    version: str
    description: str
    risk: str
    input_schema: dict[str, Any]
    default_permission: str
    output_schema: dict[str, Any] | None = None
    examples: list[dict[str, Any]] | None = None
    permissions: dict[str, list[str]] | None = None

    @property
    def namespaced_name(self) -> str:
        return f"native:{self.name}"

    @property
    def effective_permission(self) -> str:
        if self.risk.lower() == "high" and self.default_permission == "allow":
            return "ask"
        return self.default_permission


@dataclass(frozen=True)
class NativeToolInfo:
    name: str
    version: str
    description: str
    risk: str
    default_permission: str
    path: Path
    scope: str
    project_id: str | None
    sha256: str
    violations: list[str]
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "risk": self.risk,
            "default_permission": self.default_permission,
            "path": str(self.path),
            "scope": self.scope,
            "project_id": self.project_id,
            "sha256": self.sha256,
            "violations": list(self.violations),
            "status": self.status,
        }


@dataclass(frozen=True)
class NativeToolRuntime:
    manifest: NativeToolManifest
    handler: Callable[[ToolCall], ToolResult]
    spec: ToolSpec
    path: Path


def parse_native_manifest(tool_dir: Path, *, strict: bool = True) -> tuple[NativeToolManifest, list[str]]:
    tool_yaml = tool_dir / "tool.yaml"
    violations: list[str] = []
    if not tool_yaml.exists():
        raise ToolingError(f"找不到 tool.yaml：{tool_yaml}")
    try:
        raw = yaml.safe_load(tool_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ToolingError(f"讀取 tool.yaml 失敗：{tool_yaml}") from exc
    if isinstance(raw, dict) and "inputs_schema" in raw and "input_schema" not in raw:
        raise ToolingError("此 tool.yaml 為舊版格式，非 native toolforge")
    missing = [key for key in _REQUIRED_FIELDS if key not in raw]
    if missing:
        violations.append(f"缺少欄位：{', '.join(missing)}")
    name = str(raw.get("name", tool_dir.name))
    try:
        ensure_tool_name(name)
    except ToolingError as exc:
        violations.append(str(exc))
    version = str(raw.get("version", "unknown"))
    description = str(raw.get("description", ""))
    risk = str(raw.get("risk", "unknown"))
    input_schema = raw.get("input_schema") or {}
    if not isinstance(input_schema, dict):
        violations.append("input_schema 必須為物件")
        input_schema = {}
    default_permission = str(raw.get("default_permission", "deny"))
    if default_permission not in _VALID_PERMISSIONS:
        violations.append("default_permission 必須為 allow/ask/deny 之一")
        default_permission = "deny"
    if risk.lower() == "high" and default_permission == "allow":
        violations.append("risk=high 工具不得預設 allow")
    output_schema = raw.get("output_schema")
    if output_schema is not None and not isinstance(output_schema, dict):
        violations.append("output_schema 必須為物件")
        output_schema = None
    examples = raw.get("examples")
    if examples is not None:
        if not isinstance(examples, list):
            violations.append("examples 必須為陣列")
            examples = None
        else:
            normalized_examples: list[dict[str, Any]] = []
            for idx, example in enumerate(examples):
                if not isinstance(example, dict):
                    violations.append(f"examples[{idx}] 必須為物件")
                    continue
                normalized_examples.append(example)
            examples = normalized_examples

    permissions = raw.get("permissions")
    if permissions is not None:
        if not isinstance(permissions, dict):
            violations.append("permissions 必須為物件")
            permissions = None
        else:
            normalized_permissions: dict[str, list[str]] = {}
            unknown_keys = sorted(set(permissions) - {"allow", "ask", "deny"})
            if unknown_keys:
                violations.append(f"permissions 不支援欄位：{', '.join(unknown_keys)}")
            for key in ("allow", "ask", "deny"):
                value = permissions.get(key)
                if value is None:
                    continue
                if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
                    violations.append(f"permissions.{key} 必須為字串陣列")
                    continue
                normalized_permissions[key] = value
            permissions = normalized_permissions
    if strict and violations:
        raise ToolingError("; ".join(violations))
    manifest = NativeToolManifest(
        name=name,
        version=version,
        description=description,
        risk=risk,
        input_schema=input_schema,
        default_permission=default_permission,
        output_schema=output_schema,
        examples=examples,
        permissions=permissions,
    )
    return manifest, violations


def scan_native_tools(
    base_dirs: Iterable[tuple[str, Path]],
    *,
    project_id: str | None = None,
    status_lookup: dict[tuple[str, str, str | None], str] | None = None,
) -> list[NativeToolInfo]:
    tools: list[NativeToolInfo] = []
    for scope, base in base_dirs:
        if not base.exists():
            continue
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            tool_yaml = entry / "tool.yaml"
            if not tool_yaml.exists():
                continue
            try:
                manifest, violations = parse_native_manifest(entry, strict=False)
            except ToolingError:
                continue
            if not (entry / "tool.py").exists():
                violations.append("缺少 tool.py")
            sha256 = compute_tool_sha256(entry)
            tools.append(
                NativeToolInfo(
                    name=manifest.name,
                    version=manifest.version,
                    description=manifest.description,
                    risk=manifest.risk,
                    default_permission=manifest.default_permission,
                    path=entry,
                    scope=scope,
                    project_id=project_id if scope == "project" else None,
                    sha256=sha256,
                    violations=violations,
                    status=(
                        status_lookup.get((manifest.name, scope, project_id if scope == "project" else None), "active")
                        if status_lookup
                        else "active"
                    ),
                )
            )
    return tools


def compute_tool_sha256(tool_dir: Path) -> str:
    digest = hashlib.sha256()
    try:
        for path in sorted(tool_dir.rglob("*")):
            if not path.is_file():
                continue
            digest.update(path.relative_to(tool_dir).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    except OSError:
        return "unknown"
    return digest.hexdigest()


def load_native_runtimes(base_dirs: Iterable[tuple[str, Path]]) -> list[NativeToolRuntime]:
    runtimes: list[NativeToolRuntime] = []
    for scope, base in base_dirs:
        if not base.exists():
            continue
        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            tool_yaml = entry / "tool.yaml"
            if not tool_yaml.exists():
                continue
            try:
                manifest, _ = parse_native_manifest(entry, strict=True)
            except ToolingError:
                continue
            if not (entry / "tool.py").exists():
                continue
            runtimes.append(_load_native_runtime(entry, manifest))
    return runtimes


def register_native_tools(registry: ToolRegistry, runtimes: Iterable[NativeToolRuntime]) -> None:
    for runtime in runtimes:
        registry.register(runtime.spec, runtime.handler)


def _load_native_runtime(tool_dir: Path, manifest: NativeToolManifest) -> NativeToolRuntime:
    module = _import_tool_module(tool_dir)
    if hasattr(module, "register") and callable(module.register):
        registry = ToolRegistry()
        module.register(registry)
        expected_name = manifest.namespaced_name
        spec = registry.get_spec(expected_name)
        if not spec:
            raise ToolingError(f"register() 必須註冊 {expected_name}")
        if spec.risk != manifest.risk:
            raise ToolingError("tool.py risk 與 manifest 不一致")
        handler = registry.get_handler(expected_name)
        if handler is None:
            raise ToolingError(f"找不到已註冊的 handler：{expected_name}")
        return NativeToolRuntime(manifest=manifest, handler=handler, spec=spec, path=tool_dir)
    if not hasattr(module, "TOOL_SPEC") or not hasattr(module, "handle"):
        raise ToolingError("tool.py 必須提供 register(registry) 或 TOOL_SPEC + handle()")
    tool_spec = module.TOOL_SPEC
    if not isinstance(tool_spec, ToolSpec):
        raise ToolingError("TOOL_SPEC 必須是 ToolSpec")
    if tool_spec.name != manifest.namespaced_name:
        raise ToolingError("TOOL_SPEC.name 必須與 manifest 名稱一致")
    handler = module.handle
    if not callable(handler):
        raise ToolingError("handle 必須是可呼叫函式")
    annotations = dict(tool_spec.annotations)
    annotations.update(
        {
            "native": True,
            "tool_path": str(tool_dir),
            "default_permission": manifest.default_permission,
            "registered_at": datetime.now(tz=timezone.utc).isoformat(),
        }
    )
    spec = ToolSpec(
        name=manifest.namespaced_name,
        description=manifest.description,
        input_schema=manifest.input_schema,
        output_schema=tool_spec.output_schema,
        risk=manifest.risk,
        annotations=annotations,
    )
    return NativeToolRuntime(manifest=manifest, handler=handler, spec=spec, path=tool_dir)


def _import_tool_module(tool_dir: Path):
    tool_path = tool_dir / "tool.py"
    module_name = f"amon_native_tool_{tool_dir.name}_{compute_tool_sha256(tool_dir)[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, tool_path)
    if spec is None or spec.loader is None:
        raise ToolingError(f"無法載入 tool.py：{tool_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
