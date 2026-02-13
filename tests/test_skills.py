import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class SkillsTests(unittest.TestCase):
    def test_scan_list_show_and_inject(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("技能測試專案")
                project_path = Path(project.path)

                global_skill_dir = Path(temp_dir) / "skills" / "global-skill"
                global_skill_dir.mkdir(parents=True, exist_ok=True)
                global_skill_file = global_skill_dir / "SKILL.md"
                global_skill_file.write_text(
                    "---\nname: global-skill\ndescription: 全域技能\ncategory: utility\n---\n全域內容\n",
                    encoding="utf-8",
                )

                project_skill_dir = project_path / ".claude" / "skills" / "project-skill"
                project_skill_dir.mkdir(parents=True, exist_ok=True)
                project_skill_file = project_skill_dir / "SKILL.md"
                project_skill_file.write_text(
                    "---\nname: project-skill\ndescription: 專案技能\n---\n專案內容\n",
                    encoding="utf-8",
                )
                references_dir = project_skill_dir / "references"
                references_dir.mkdir(parents=True, exist_ok=True)
                (references_dir / "note.txt").write_text("note", encoding="utf-8")

                skills = core.scan_skills(project_path=project_path)
                skill_names = {skill["name"] for skill in skills}
                self.assertTrue({"global-skill", "project-skill"}.issubset(skill_names))
                self.assertTrue(all(skill.get("updated_at") for skill in skills))
                sources = {skill["name"]: skill.get("source") for skill in skills}
                self.assertEqual(sources["global-skill"], "global")
                self.assertEqual(sources["project-skill"], "project")
                global_meta = next(skill for skill in skills if skill["name"] == "global-skill")
                self.assertEqual(global_meta.get("frontmatter", {}).get("category"), "utility")

                listed = core.list_skills()
                listed_names = {skill["name"] for skill in listed}
                self.assertTrue({"global-skill", "project-skill"}.issubset(listed_names))

                skill = core.load_skill("global-skill", project_path=project_path)
                self.assertIn("全域內容", skill["content"])

                project_loaded = core.load_skill("project-skill", project_path=project_path)
                self.assertEqual(project_loaded.get("references")[0]["path"], "note.txt")

                injected = core._resolve_skill_context("/global-skill 請幫忙", project_path=project_path)
                self.assertIn("## Skills (frontmatter)", injected)
                self.assertIn("- global-skill：全域技能", injected)
                self.assertNotIn("全域內容", injected)
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_selected_skill_updates_system_message(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                project = core.create_project("技能系統訊息測試")
                project_path = Path(project.path)

                skill_dir = Path(temp_dir) / "skills" / "review-skill"
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\nname: review-skill\ndescription: 專注 code review\n---\n請專注 code review。",
                    encoding="utf-8",
                )

                config = core.load_config(project_path)
                base_message = core._build_system_message("測試", project_path, config=config)
                skill_message = core._build_system_message(
                    "測試",
                    project_path,
                    config=config,
                    skill_names=["review-skill"],
                )

                self.assertNotIn("## Skills (frontmatter)", base_message)
                self.assertIn("回覆必須先交付可執行內容", base_message)
                self.assertIn("## First-party tools", base_message)
                self.assertIn("- filesystem.read", base_message)
                self.assertIn("## Skills (frontmatter)", skill_message)
                self.assertIn("- review-skill：專注 code review", skill_message)
                self.assertIn("## First-party tools", skill_message)
                self.assertLess(skill_message.index("## First-party tools"), skill_message.index("## Skills (frontmatter)"))
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_invalid_frontmatter_is_tolerant(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()

                skill_dir = Path(temp_dir) / "skills" / "broken-skill"
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\nname: [\n---\n內容\n",
                    encoding="utf-8",
                )

                skills = core.scan_skills()
                broken = next(skill for skill in skills if skill["name"] == "broken-skill")
                self.assertEqual(broken["description"], "")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
