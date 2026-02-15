import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore
from amon.skills.injection import build_skill_injection_preview, build_system_prefix_injection
from amon.ui_server import AmonUIHandler


class SkillInjectionTests(unittest.TestCase):
    def test_preview_contains_targets_and_segments(self) -> None:
        skill = {
            "name": "triage",
            "description": "事故處理",
            "source": "global",
            "path": "/tmp/skills/triage/SKILL.md",
            "frontmatter": {
                "name": "triage",
                "description": "事故處理",
                "inject_to": ["system", "run_constraints"],
                "tool_policy": ["filesystem.read"],
            },
            "content": "---\nname: triage\ndescription: 事故處理\n---\n先收斂問題，再執行修復。",
        }

        preview = build_skill_injection_preview([skill])
        self.assertEqual(preview["skills"][0]["targets"], ["system_prefix", "run_constraints", "tool_policy_hint"])
        self.assertIn("先收斂問題", preview["skills"][0]["injected_text"])
        segments = {item["segment"]: item["text"] for item in preview["segments"]}
        self.assertIn("triage", segments["system_prefix"])
        self.assertIn("triage", segments["run_constraints"])
        self.assertIn("tool_policy_hint", {item["segment"] for item in preview["segments"]})

    def test_system_prefix_injection_is_deterministic(self) -> None:
        skills = [
            {"name": "alpha", "description": "A", "frontmatter": {}},
            {"name": "beta", "description": "B", "frontmatter": {"description": "B2"}},
        ]
        result = build_system_prefix_injection(skills)
        self.assertEqual(result, "## Skills (frontmatter)\n- alpha：A\n- beta：B2")

    def test_ui_preview_endpoint_payload_structure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                skill_dir = Path(temp_dir) / "skills" / "preview-skill"
                skill_dir.mkdir(parents=True, exist_ok=True)
                (skill_dir / "SKILL.md").write_text(
                    "---\nname: preview-skill\ndescription: 預覽技能\ninject_to: [system_prefix, run_constraints]\n---\n請先列出限制。",
                    encoding="utf-8",
                )
                core.scan_skills()
                handler = object.__new__(AmonUIHandler)
                handler.core = core
                payload = handler._build_skill_trigger_preview(skill_name="preview-skill", project_id=None)
                self.assertIn("skills", payload["injection_preview"])
                self.assertEqual(payload["skill"]["name"], "preview-skill")
                self.assertIn("不會觸發模型", payload["note"])
            finally:
                os.environ.pop("AMON_HOME", None)

    def test_scan_and_load_skill_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            os.environ["AMON_HOME"] = temp_dir
            try:
                core = AmonCore()
                core.initialize()
                archive_path = Path(temp_dir) / "skills" / "archive-demo.skill"
                archive_path.parent.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(archive_path, "w") as archive:
                    archive.writestr(
                        "archive-demo/SKILL.md",
                        "---\nname: archive-demo\ndescription: 壓縮技能\n---\n壓縮內容",
                    )
                    archive.writestr("archive-demo/references/readme.txt", "archive ref")

                scanned = core.scan_skills()
                names = {item["name"] for item in scanned}
                self.assertIn("archive-demo", names)

                loaded = core.load_skill("archive-demo")
                self.assertIn("壓縮內容", loaded["content"])
                self.assertEqual(loaded["references"][0]["path"], "readme.txt")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
