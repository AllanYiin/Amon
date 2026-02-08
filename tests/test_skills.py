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
                self.assertEqual({skill["name"] for skill in skills}, {"global-skill", "project-skill"})
                self.assertTrue(all(skill.get("updated_at") for skill in skills))
                sources = {skill["name"]: skill.get("source") for skill in skills}
                self.assertEqual(sources["global-skill"], "global")
                self.assertEqual(sources["project-skill"], "project")
                global_meta = next(skill for skill in skills if skill["name"] == "global-skill")
                self.assertEqual(global_meta.get("frontmatter", {}).get("category"), "utility")

                listed = core.list_skills()
                self.assertEqual(len(listed), 2)

                skill = core.load_skill("global-skill", project_path=project_path)
                self.assertIn("全域內容", skill["content"])

                project_loaded = core.load_skill("project-skill", project_path=project_path)
                self.assertEqual(project_loaded.get("references")[0]["path"], "note.txt")

                injected = core._resolve_skill_context("/global-skill 請幫忙", project_path=project_path)
                self.assertIn("全域內容", injected)
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
                self.assertEqual(skills[0]["name"], "broken-skill")
                self.assertEqual(skills[0]["description"], "")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
