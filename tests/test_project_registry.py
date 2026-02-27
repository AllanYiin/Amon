from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml
from unittest.mock import patch

from amon.core import AmonCore
from amon.project_registry import ProjectRegistry, generate_project_slug, load_project_config


class ProjectRegistryTests(unittest.TestCase):
    def test_generate_project_slug_chinese_compression(self) -> None:
        with patch("amon.project_registry._summarize_slug_with_llm", return_value="俄羅斯方塊遊戲"):
            slug = generate_project_slug("請協助製作一個俄羅斯方塊遊戲專案")
        self.assertEqual(slug, "俄羅斯方塊遊戲")
        self.assertLessEqual(len(slug), 10)

    def test_generate_project_slug_english_compression(self) -> None:
        with patch("amon.project_registry._summarize_slug_with_llm", return_value="complete-web-dashboard"):
            slug = generate_project_slug("Please help me create a complete web dashboard application project")
        self.assertEqual(slug, "complete-web-dashboard")
        self.assertLessEqual(len(slug.split("-")), 5)

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

    def test_registry_migrates_legacy_project_folder_to_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "project-123456"
            legacy.mkdir(parents=True, exist_ok=True)
            (legacy / "workspace").mkdir(parents=True, exist_ok=True)
            config_path = legacy / "amon.project.yaml"
            config_path.write_text(
                yaml.safe_dump({"amon": {"project_name": "俄羅斯方塊單頁網頁專案"}}, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            with patch("amon.project_registry._summarize_slug_with_llm", return_value="俄羅斯方塊單頁網頁"):
                registry = ProjectRegistry(root)
                registry.scan()

            listed = registry.list_projects()
            self.assertEqual(len(listed), 1)
            record = listed[0]
            self.assertEqual(record["project_id"], "project-123456")
            migrated_path = Path(record["project_path"])
            self.assertEqual(migrated_path.name, "俄羅斯方塊單頁網頁")
            self.assertTrue((migrated_path / "workspace").exists())
            saved = yaml.safe_load((migrated_path / "amon.project.yaml").read_text(encoding="utf-8")) or {}
            self.assertEqual(saved.get("amon", {}).get("project_id"), "project-123456")
            self.assertEqual(saved.get("amon", {}).get("project_slug"), "俄羅斯方塊單頁網頁")

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

    def test_core_create_project_uses_human_readable_slug_folder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            core = AmonCore(data_dir=Path(tmp))
            with patch("amon.project_registry._summarize_slug_with_llm", return_value="俄羅斯方塊單頁網頁"):
                record = core.create_project("請協助建立俄羅斯方塊單頁網頁專案")
            project_path = Path(record.path)

            self.assertNotEqual(project_path.name, record.project_id)
            self.assertEqual(project_path.name, "俄羅斯方塊單頁網頁")
            saved = yaml.safe_load((project_path / "amon.project.yaml").read_text(encoding="utf-8")) or {}
            self.assertEqual(saved.get("amon", {}).get("project_id"), record.project_id)
            self.assertEqual(saved.get("amon", {}).get("project_slug"), project_path.name)



if __name__ == "__main__":
    unittest.main()
