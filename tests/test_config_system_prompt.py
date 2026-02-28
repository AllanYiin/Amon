import os
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.config import ConfigLoader, resolve_system_prompt


class ConfigSystemPromptTests(unittest.TestCase):
    def test_resolve_system_prompt_prefers_canonical_prompts_system(self) -> None:
        config = {
            "prompts": {"system": "canonical"},
            "agent": {"system_prompt": "agent"},
            "chat": {"system_prompt": "chat"},
        }
        self.assertEqual(resolve_system_prompt(config), "canonical")

    def test_resolve_system_prompt_falls_back_to_legacy_keys(self) -> None:
        self.assertEqual(resolve_system_prompt({"agent": {"system_prompt": "agent"}}), "agent")
        self.assertEqual(resolve_system_prompt({"chat": {"system_prompt": "chat"}}), "chat")

    def test_config_loader_normalizes_legacy_system_prompt_to_prompts_system(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            os.environ["AMON_HOME"] = str(data_dir)
            try:
                config_path = data_dir / "config.yaml"
                config_path.parent.mkdir(parents=True, exist_ok=True)
                config_path.write_text("agent:\n  system_prompt: legacy from agent\n", encoding="utf-8")

                resolved = ConfigLoader(data_dir=data_dir).resolve()
                effective = resolved.effective
                sources = resolved.sources

                self.assertEqual(effective["prompts"]["system"], "legacy from agent")
                self.assertEqual(sources["prompts"]["system"], "global")
            finally:
                os.environ.pop("AMON_HOME", None)


if __name__ == "__main__":
    unittest.main()
