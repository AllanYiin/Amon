from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from amon.core import AmonCore
from amon.project_registry import ProjectRegistry, load_project_config


class ProjectRegistryTests(unittest.TestCase):
    def test_load_project_config_backfills_missing_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project_path = Path(tmp) / "human-readable-name"
            project_path.mkdir(parents=True, exist_ok=True)
            config_path = project_path / "amon.project.yaml"
            config_path.write_text(
                yaml.safe_dump({"amon": {"project_name": "測試專案", "mode": "auto"}}, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            identity = load_project_config(project_path)

            self.assertEqual(identity.project_id, "human-readable-name")
            saved = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            self.assertEqual(saved.get("amon", {}).get("project_id"), "human-readable-name")



    def test_registry_migrates_legacy_project_folder_to_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            projects_dir = Path(tmp) / "projects"
            legacy_dir = projects_dir / "project-123456"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            config_path = legacy_dir / "amon.project.yaml"
            config_path.write_text(
                yaml.safe_dump({"amon": {"project_name": "開發俄羅斯方塊", "project_id": "project-123456"}}, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            registry = ProjectRegistry(projects_dir, slug_builder=lambda _name, _existing: "俄羅斯方塊")
            registry.scan()

            migrated_path = projects_dir / "俄羅斯方塊"
            self.assertTrue(migrated_path.exists())
            self.assertTrue(legacy_dir.is_symlink() or not legacy_dir.exists())
            self.assertEqual(registry.get_path("project-123456"), migrated_path)
            saved = yaml.safe_load((migrated_path / "amon.project.yaml").read_text(encoding="utf-8")) or {}
            self.assertEqual(saved.get("amon", {}).get("project_slug"), "俄羅斯方塊")

    def test_registry_keeps_canonical_project_id_after_folder_rename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            core = AmonCore(data_dir=Path(tmp))
            project = core.create_project("registry-rename")
            old_path = core.get_project_path(project.project_id)
            new_path = old_path.parent / f"renamed-{old_path.name}"
            shutil.move(str(old_path), str(new_path))

            registry = ProjectRegistry(core.projects_dir)
            registry.scan()

            self.assertEqual(registry.get_path(project.project_id), new_path)
            listed = registry.list_projects()
            self.assertTrue(any(item["project_id"] == project.project_id for item in listed))

    def test_core_list_projects_uses_config_project_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            core = AmonCore(data_dir=Path(tmp))
            project = core.create_project("list-projects-id")
            old_path = core.get_project_path(project.project_id)
            new_path = old_path.parent / f"friendly-{old_path.name}"
            shutil.move(str(old_path), str(new_path))

            listed = core.list_projects()

            target = next(item for item in listed if item.project_id == project.project_id)
            self.assertEqual(Path(target.path), new_path)



if __name__ == "__main__":
    unittest.main()
