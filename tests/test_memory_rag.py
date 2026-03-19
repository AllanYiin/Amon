import sys
import math
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from amon.memory.rag import (
    GenericRAG,
    QueryOptions,
    RAGDocument,
    RetrievalWeights,
    SemanticChunkConfig,
)


class StubEmbedder:
    def __init__(self) -> None:
        self.vocabulary = {
            "alpha": (1.0, 0.0, 0.0, 0.0),
            "beta": (0.7, 0.0, 0.0, 0.0),
            "launch": (0.5, 0.0, 0.0, 0.0),
            "finance": (0.0, 1.0, 0.0, 0.0),
            "budget": (0.0, 0.8, 0.0, 0.0),
            "rocket": (0.0, 0.0, 1.0, 0.0),
            "diagram": (0.0, 0.0, 0.6, 0.0),
            "table": (0.0, 0.0, 0.0, 1.0),
            "revenue": (0.0, 0.0, 0.0, 0.7),
            "2026-03-18": (0.2, 0.0, 0.0, 0.0),
        }

    def embed_texts(self, texts, *, is_query: bool):
        embeddings = []
        for text in texts:
            vector = [0.0, 0.0, 0.0, 0.0]
            lowered = text.lower()
            for token, basis in self.vocabulary.items():
                if token in lowered:
                    for index, value in enumerate(basis):
                        vector[index] += value
            if is_query:
                vector[0] += 0.1
            norm = math.sqrt(sum(value * value for value in vector)) or 1.0
            embeddings.append([value / norm for value in vector])
        return embeddings


class StubReranker:
    def score(self, query, documents):
        query_terms = set(query.lower().split())
        scores = []
        for document in documents:
            doc_terms = set(document.lower().split())
            scores.append(float(len(query_terms & doc_terms)))
        return scores


class GenericRAGTests(unittest.TestCase):
    def test_semantic_chunking_parent_average_and_metadata_vectorization(self) -> None:
        rag = GenericRAG(
            embedder=StubEmbedder(),
            reranker=StubReranker(),
            chunk_config=SemanticChunkConfig(similarity_threshold=0.6, max_sentences=3, max_chars=200),
        )
        rag.index_documents(
            [
                RAGDocument(
                    document_id="doc-alpha",
                    text="昨天 alpha launch. alpha beta launch. finance budget.",
                    created_at="2026-03-19T09:00:00+00:00",
                    images=[{"caption": "rocket diagram"}],
                    tables=[{"title": "Revenue", "summary": "table revenue"}],
                )
            ]
        )

        parent = rag.document_nodes["doc-alpha"]
        children = [rag.leaf_nodes[node_id] for node_id in parent.child_ids]

        self.assertEqual(len(children), 2)
        self.assertIn("2026-03-18", children[0].text)
        self.assertIn("[image] rocket diagram", children[0].embedding_text)
        self.assertIn("[table] Revenue | table revenue", children[0].embedding_text)

        expected = [
            sum(child.vector[index] for child in children) / len(children)
            for index in range(len(children[0].vector))
        ]
        for actual, want in zip(parent.vector, expected):
            self.assertAlmostEqual(actual, want, places=6)

    def test_search_supports_negative_examples_recency_and_diversity(self) -> None:
        rag = GenericRAG(
            embedder=StubEmbedder(),
            reranker=StubReranker(),
            weights=RetrievalWeights(dense=0.5, bm25=0.2, graph=0.1, rerank=0.2),
        )
        rag.index_documents(
            [
                RAGDocument(
                    document_id="recent-alpha",
                    text="alpha launch roadmap.",
                    created_at="2026-03-18T10:00:00+00:00",
                ),
                RAGDocument(
                    document_id="old-alpha",
                    text="alpha launch roadmap.",
                    created_at="2025-01-01T10:00:00+00:00",
                ),
                RAGDocument(
                    document_id="finance-note",
                    text="finance budget memo.",
                    created_at="2026-03-18T10:00:00+00:00",
                ),
            ]
        )

        response = rag.search(
            "alpha launch",
            options=QueryOptions(
                max_top_k=3,
                min_top_k=2,
                negative_texts=["finance budget"],
                diversity_max_cosine=0.9,
                reference_time=datetime(2026, 3, 19, tzinfo=timezone.utc),
            ),
        )

        self.assertGreaterEqual(len(response.hits), 2)
        self.assertEqual(response.hits[0].document_id, "recent-alpha")
        self.assertNotEqual(response.hits[1].document_id, "old-alpha")

        negative_response = rag.search(
            "finance budget",
            options=QueryOptions(
                top_k=1,
                negative_texts=["finance budget"],
                reference_time=datetime(2026, 3, 19, tzinfo=timezone.utc),
            ),
        )
        self.assertLess(negative_response.hits[0].dense_score, 1.0)

    def test_cluster_then_member_search_with_graph_score(self) -> None:
        rag = GenericRAG(
            embedder=StubEmbedder(),
            reranker=StubReranker(),
            chunk_config=SemanticChunkConfig(similarity_threshold=0.4, max_sentences=2, max_chars=150),
            cluster_similarity_threshold=0.5,
        )
        rag.index_documents(
            [
                RAGDocument(document_id="alpha-1", text="alpha launch."),
                RAGDocument(document_id="alpha-2", text="alpha beta launch."),
                RAGDocument(document_id="finance-1", text="finance budget."),
            ]
        )

        response = rag.search("alpha beta", options=QueryOptions(top_k=2, cluster_probe=1))

        self.assertEqual(len(response.trace.selected_cluster_ids), 1)
        self.assertTrue(response.trace.candidate_node_ids)
        self.assertEqual(response.hits[0].document_id, "alpha-2")
        self.assertGreater(response.hits[0].graph_score, 0.0)


if __name__ == "__main__":
    unittest.main()
