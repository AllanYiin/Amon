import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class MemorySearchTests(unittest.TestCase):
    def test_time_range_filters_before_vector_sort(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            normalized_path = memory_dir / "normalized.jsonl"
            tags_path = memory_dir / "tags.jsonl"

            normalized_records = [
                {
                    "chunk_id": "chunk-1",
                    "text": "決議：採用 A 方案。",
                    "created_at": "2026-02-02T10:00:00+08:00",
                    "source_path": "sessions/session-1.jsonl",
                    "time": {"mentions": [{"raw": "昨天", "resolved_date": "2026-02-02"}]},
                },
                {
                    "chunk_id": "chunk-2",
                    "text": "決議：採用 B 方案。",
                    "created_at": "2026-02-03T10:00:00+08:00",
                    "source_path": "sessions/session-2.jsonl",
                    "time": {"mentions": [{"raw": "今天", "resolved_date": "2026-02-03"}]},
                },
            ]
            with normalized_path.open("w", encoding="utf-8") as handle:
                for record in normalized_records:
                    handle.write(json.dumps(record, ensure_ascii=False))
                    handle.write("\n")

            tag_records = [
                {"chunk_id": "chunk-1", "embedding_text": "決議：採用 A 方案。"},
                {"chunk_id": "chunk-2", "embedding_text": "決議：採用 B 方案。"},
            ]
            with tags_path.open("w", encoding="utf-8") as handle:
                for record in tag_records:
                    handle.write(json.dumps(record, ensure_ascii=False))
                    handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            results = core.search_memory(
                project_path,
                "採用 B",
                time_range={"start": "2026-02-02", "end": "2026-02-02"},
                top_k=5,
            )
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["chunk_id"], "chunk-1")

    def test_vector_sort_after_time_range(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            normalized_path = memory_dir / "normalized.jsonl"
            tags_path = memory_dir / "tags.jsonl"

            normalized_records = [
                {
                    "chunk_id": "chunk-1",
                    "text": "決議：採用 A 方案。",
                    "created_at": "2026-02-02T10:00:00+08:00",
                    "source_path": "sessions/session-1.jsonl",
                    "time": {"mentions": [{"raw": "昨天", "resolved_date": "2026-02-02"}]},
                },
                {
                    "chunk_id": "chunk-2",
                    "text": "決議：採用 B 方案。",
                    "created_at": "2026-02-03T10:00:00+08:00",
                    "source_path": "sessions/session-2.jsonl",
                    "time": {"mentions": [{"raw": "今天", "resolved_date": "2026-02-03"}]},
                },
            ]
            with normalized_path.open("w", encoding="utf-8") as handle:
                for record in normalized_records:
                    handle.write(json.dumps(record, ensure_ascii=False))
                    handle.write("\n")

            tag_records = [
                {"chunk_id": "chunk-1", "embedding_text": "決議：採用 A 方案。"},
                {"chunk_id": "chunk-2", "embedding_text": "決議：採用 B 方案。"},
            ]
            with tags_path.open("w", encoding="utf-8") as handle:
                for record in tag_records:
                    handle.write(json.dumps(record, ensure_ascii=False))
                    handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            results = core.search_memory(
                project_path,
                "採用 B",
                time_range={"start": "2026-02-02", "end": "2026-02-03"},
                top_k=2,
            )
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["chunk_id"], "chunk-2")


class EntityAliasTests(unittest.TestCase):
    def test_alias_merge_uses_existing_canonical_id(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            chunks_path = memory_dir / "chunks.jsonl"

            chunks = [
                {
                    "chunk_id": "chunk-entity-1",
                    "project_id": "proj-entity-1",
                    "session_id": "session-entity-1",
                    "source_path": "sessions/session-entity-1.jsonl",
                    "text": "王小明今天來開會。",
                    "created_at": "2026-02-03T10:00:00+08:00",
                    "lang": "zh-TW",
                },
                {
                    "chunk_id": "chunk-entity-2",
                    "project_id": "proj-entity-1",
                    "session_id": "session-entity-1",
                    "source_path": "sessions/session-entity-1.jsonl",
                    "text": "小明說他晚點補資料。",
                    "created_at": "2026-02-03T10:05:00+08:00",
                    "lang": "zh-TW",
                },
            ]
            with chunks_path.open("w", encoding="utf-8") as handle:
                for chunk in chunks:
                    handle.write(json.dumps(chunk, ensure_ascii=False))
                    handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            core.normalize_memory_dates(project_path)

            aliases_path = memory_dir / "entity_aliases.json"
            self.assertTrue(aliases_path.exists())
            alias_payload = json.loads(aliases_path.read_text(encoding="utf-8"))
            alias_map = alias_payload["aliases"]
            key_full = core._normalize_alias_key("王小明")
            key_short = core._normalize_alias_key("小明")
            self.assertEqual(alias_map[key_full], alias_map[key_short])


if __name__ == "__main__":
    unittest.main()
