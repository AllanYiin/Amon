import json
import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.core import AmonCore


class MemoryIngestTests(unittest.TestCase):
    def test_ingest_session_writes_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            sessions_dir = project_path / "sessions"
            sessions_dir.mkdir(parents=True, exist_ok=True)
            session_id = "session-123"
            session_path = sessions_dir / f"{session_id}.jsonl"

            events = [
                {"event": "prompt", "role": "user", "content": "hi"},
                {"event": "chunk", "content": "ignored"},
                {"event": "final", "content": "hello"},
            ]
            with session_path.open("w", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event, ensure_ascii=False))
                    handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            chunk_count = core.ingest_session_memory(project_path, session_id, project_id="proj-1", lang="zh-TW")

            chunks_path = project_path / "memory" / "chunks.jsonl"
            self.assertTrue(chunks_path.exists())
            lines = chunks_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(chunk_count, 2)
            self.assertEqual(len(lines), 2)
            for line in lines:
                chunk = json.loads(line)
                self.assertIn("chunk_id", chunk)
                self.assertEqual(chunk["project_id"], "proj-1")
                self.assertEqual(chunk["session_id"], session_id)
                self.assertEqual(chunk["source_path"], f"sessions/{session_id}.jsonl")
                self.assertIn("text", chunk)
                self.assertIn("created_at", chunk)
                self.assertEqual(chunk["lang"], "zh-TW")

    def test_normalize_relative_date_yesterday(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            chunks_path = memory_dir / "chunks.jsonl"

            chunk = {
                "chunk_id": "chunk-1",
                "project_id": "proj-1",
                "session_id": "session-1",
                "source_path": "sessions/session-1.jsonl",
                "text": "昨天去開會",
                "created_at": "2026-02-03T10:00:00+08:00",
                "lang": "zh-TW",
            }
            with chunks_path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(chunk, ensure_ascii=False))
                handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            normalized_count = core.normalize_memory_dates(project_path)

            normalized_path = memory_dir / "normalized.jsonl"
            self.assertEqual(normalized_count, 1)
            self.assertTrue(normalized_path.exists())
            normalized_lines = normalized_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(normalized_lines), 1)
            normalized = json.loads(normalized_lines[0])
            mentions = normalized["time"]["mentions"]
            self.assertEqual(len(mentions), 1)
            self.assertEqual(mentions[0]["raw"], "昨天")
            self.assertEqual(mentions[0]["resolved_date"], "2026-02-02")

    def test_normalize_geo_mentions_taipei(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            chunks_path = memory_dir / "chunks.jsonl"

            chunk = {
                "chunk_id": "chunk-geo-1",
                "project_id": "proj-geo-1",
                "session_id": "session-geo-1",
                "source_path": "sessions/session-geo-1.jsonl",
                "text": "台北、臺北、Taipei 都是同一個城市",
                "created_at": "2026-02-03T10:00:00+08:00",
                "lang": "zh-TW",
            }
            with chunks_path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(chunk, ensure_ascii=False))
                handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            normalized_count = core.normalize_memory_dates(project_path)

            normalized_path = memory_dir / "normalized.jsonl"
            self.assertEqual(normalized_count, 1)
            normalized_lines = normalized_path.read_text(encoding="utf-8").splitlines()
            normalized = json.loads(normalized_lines[0])
            mentions = normalized["geo"]["mentions"]
            self.assertEqual(len(mentions), 3)
            geocode_ids = {mention["geocode_id"] for mention in mentions}
            self.assertEqual(geocode_ids, {"tw-tpe"})

    def test_resolve_pronoun_uses_last_explicit_entity(self) -> None:
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
                    "text": "他說會準時交付。",
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

            entities_path = memory_dir / "entities.jsonl"
            self.assertTrue(entities_path.exists())
            entity_lines = entities_path.read_text(encoding="utf-8").splitlines()
            self.assertGreaterEqual(len(entity_lines), 1)
            records = [json.loads(line) for line in entity_lines]
            pronoun_records = [record for record in records if record.get("mention", {}).get("pronoun") == "他"]
            self.assertEqual(len(pronoun_records), 1)
            mention = pronoun_records[0]["mention"]
            self.assertEqual(mention["pronoun"], "他")
            self.assertEqual(mention["resolved_to"], "王小明")

    def test_generate_tags_includes_embedding_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir) / "data"
            project_path = Path(temp_dir) / "project"
            memory_dir = project_path / "memory"
            memory_dir.mkdir(parents=True, exist_ok=True)
            chunks_path = memory_dir / "chunks.jsonl"

            chunk = {
                "chunk_id": "chunk-tag-1",
                "project_id": "proj-tag-1",
                "session_id": "session-tag-1",
                "source_path": "sessions/session-tag-1.jsonl",
                "text": "昨天到台北開會。",
                "created_at": "2026-02-03T10:00:00+08:00",
                "lang": "zh-TW",
            }
            with chunks_path.open("w", encoding="utf-8") as handle:
                handle.write(json.dumps(chunk, ensure_ascii=False))
                handle.write("\n")

            core = AmonCore(data_dir=data_dir)
            core.normalize_memory_dates(project_path)

            tags_path = memory_dir / "tags.jsonl"
            self.assertTrue(tags_path.exists())
            tags_lines = tags_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(tags_lines), 1)
            record = json.loads(tags_lines[0])
            embedding_text = record["embedding_text"]
            self.assertIn("昨天到台北開會。", embedding_text)
            self.assertIn("## AMON_MEMORY_TAGS", embedding_text)


if __name__ == "__main__":
    unittest.main()
