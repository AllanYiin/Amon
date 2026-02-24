from pathlib import Path
import unittest


class AgentsContractDocTests(unittest.TestCase):
    def test_root_agents_title_is_codex_contract(self) -> None:
        content = Path('AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('# Codex 工作契約（Repo Root）', content)


if __name__ == '__main__':
    unittest.main()
