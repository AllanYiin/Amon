import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.memory.model_store import LocalModelStore, ModelSpec, default_onnx_files
from amon.memory.rag import JinaOnnxTextNanoRetrievalEmbedder, JinaRerankerV3


class LocalModelStoreTests(unittest.TestCase):
    def test_ensure_model_downloads_to_explicit_store(self) -> None:
        downloaded: list[tuple[str, Path]] = []

        def fake_downloader(url: str, destination: Path) -> None:
            downloaded.append((url, destination))
            destination.write_text("ok", encoding="utf-8")

        with tempfile.TemporaryDirectory() as temp_dir:
            store = LocalModelStore(temp_dir, downloader=fake_downloader)
            model_dir = store.ensure_model(
                ModelSpec(
                    repo_id="jinaai/jina-embeddings-v5-text-nano-retrieval",
                    revision="rev-123",
                    files=("config.json", "onnx/model.onnx"),
                )
            )

            self.assertEqual(
                model_dir,
                Path(temp_dir) / "jinaai__jina-embeddings-v5-text-nano-retrieval" / "rev-123",
            )
            self.assertEqual(len(downloaded), 2)
            self.assertTrue((model_dir / "config.json").exists())
            self.assertTrue((model_dir / "onnx" / "model.onnx").exists())

    def test_default_onnx_files_include_external_data_pair(self) -> None:
        files = default_onnx_files("model.onnx")
        self.assertIn("onnx/model.onnx", files)
        self.assertIn("onnx/model.onnx_data", files)


class LocalModelLoadTests(unittest.TestCase):
    def test_onnx_embedder_loads_from_local_model_dir(self) -> None:
        fake_tokenizer = mock.Mock()
        fake_model = mock.Mock()
        fake_ort_cls = mock.Mock()
        fake_ort_cls.from_pretrained.return_value = fake_model
        fake_tokenizer_cls = mock.Mock()
        fake_tokenizer_cls.from_pretrained.return_value = fake_tokenizer
        fake_torch = types.SimpleNamespace()
        fake_store = mock.Mock()
        fake_store.ensure_model.return_value = Path("D:/tmp/local-embed-model")

        with mock.patch.dict(
            sys.modules,
            {
                "optimum": types.ModuleType("optimum"),
                "optimum.onnxruntime": types.SimpleNamespace(ORTModelForFeatureExtraction=fake_ort_cls),
                "transformers": types.SimpleNamespace(AutoTokenizer=fake_tokenizer_cls),
                "torch": fake_torch,
            },
        ):
            embedder = JinaOnnxTextNanoRetrievalEmbedder(model_store=fake_store)
            embedder._lazy_load()

        fake_store.ensure_model.assert_called_once()
        tokenizer_args, tokenizer_kwargs = fake_tokenizer_cls.from_pretrained.call_args
        self.assertEqual(Path(tokenizer_args[0]), Path("D:/tmp/local-embed-model"))
        self.assertEqual(tokenizer_kwargs, {"trust_remote_code": True})
        fake_ort_cls.from_pretrained.assert_called_once_with(
            str(Path("D:/tmp/local-embed-model")),
            subfolder="onnx",
            file_name="model.onnx",
            provider="CPUExecutionProvider",
            trust_remote_code=True,
        )

    def test_reranker_loads_from_local_model_dir(self) -> None:
        fake_tokenizer = mock.Mock()
        fake_model = mock.Mock()
        fake_model.to.return_value = fake_model
        fake_model_cls = mock.Mock()
        fake_model_cls.from_pretrained.return_value = fake_model
        fake_tokenizer_cls = mock.Mock()
        fake_tokenizer_cls.from_pretrained.return_value = fake_tokenizer
        fake_torch = types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False))
        fake_store = mock.Mock()
        fake_store.ensure_model.return_value = Path("D:/tmp/local-rerank-model")

        with mock.patch.dict(
            sys.modules,
            {
                "transformers": types.SimpleNamespace(
                    AutoModelForSequenceClassification=fake_model_cls,
                    AutoTokenizer=fake_tokenizer_cls,
                ),
                "torch": fake_torch,
            },
        ):
            reranker = JinaRerankerV3(model_store=fake_store)
            reranker._lazy_load()

        fake_store.ensure_model.assert_called_once()
        tokenizer_args, tokenizer_kwargs = fake_tokenizer_cls.from_pretrained.call_args
        self.assertEqual(Path(tokenizer_args[0]), Path("D:/tmp/local-rerank-model"))
        self.assertEqual(tokenizer_kwargs, {"trust_remote_code": True})
        fake_model_cls.from_pretrained.assert_called_once_with(
            str(Path("D:/tmp/local-rerank-model")),
            trust_remote_code=True,
            torch_dtype="auto",
        )


if __name__ == "__main__":
    unittest.main()
