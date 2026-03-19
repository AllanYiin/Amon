from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable, Protocol, Sequence


def _dot(left: Sequence[float], right: Sequence[float]) -> float:
    return sum(float(a) * float(b) for a, b in zip(left, right))


def _norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    left_norm = _norm(left)
    right_norm = _norm(right)
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return _dot(left, right) / (left_norm * right_norm)


def mean_vector(vectors: Sequence[Sequence[float]]) -> list[float]:
    if not vectors:
        return []
    totals = [0.0] * len(vectors[0])
    for vector in vectors:
        for index, value in enumerate(vector):
            totals[index] += float(value)
    return [value / len(vectors) for value in totals]


def l2_normalize(vector: Sequence[float]) -> list[float]:
    denom = _norm(vector)
    if denom == 0.0:
        return [0.0 for _ in vector]
    return [float(value) / denom for value in vector]


def _min_max_scale(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    low = min(values.values())
    high = max(values.values())
    if math.isclose(low, high):
        if high <= 0.0:
            return {key: 0.0 for key in values}
        return {key: 1.0 for key in values}
    spread = high - low
    return {key: (value - low) / spread for key, value in values.items()}


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _tokenize(text: str) -> list[str]:
    lowered = text.lower()
    latin = re.findall(r"[a-z0-9]+", lowered)
    cjk = re.findall(r"[\u4e00-\u9fff]", text)
    return latin + cjk


class TextEmbedder(Protocol):
    def embed_texts(self, texts: Sequence[str], *, is_query: bool) -> list[list[float]]:
        ...


class Reranker(Protocol):
    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        ...


@dataclass(slots=True)
class SemanticChunkConfig:
    similarity_threshold: float = 0.72
    max_sentences: int = 5
    max_chars: int = 700


@dataclass(slots=True)
class RetrievalWeights:
    dense: float = 0.45
    bm25: float = 0.25
    graph: float = 0.15
    rerank: float = 0.15


@dataclass(slots=True)
class RecencyPolicy:
    half_life_days: float = 45.0
    min_weight: float = 0.4

    def weight(self, created_at: datetime | None, *, now: datetime | None = None) -> float:
        if created_at is None:
            return 1.0
        reference = now or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        age_days = max((reference - created_at).total_seconds() / 86400.0, 0.0)
        if self.half_life_days <= 0:
            return 1.0
        decay = math.pow(0.5, age_days / self.half_life_days)
        return max(self.min_weight, decay)


@dataclass(slots=True)
class RAGDocument:
    document_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str | datetime | None = None
    images: list[dict[str, Any]] = field(default_factory=list)
    tables: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class RAGNode:
    node_id: str
    document_id: str
    text: str
    embedding_text: str
    vector: list[float]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime | None = None
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)
    neighbor_ids: list[str] = field(default_factory=list)
    graph_vector: list[float] = field(default_factory=list)
    cluster_id: str | None = None
    depth: int = 0


@dataclass(slots=True)
class QueryOptions:
    top_k: int | None = None
    min_top_k: int = 3
    max_top_k: int = 8
    dynamic_margin: float = 0.05
    min_score: float = 0.1
    parent_top_k: int = 3
    cluster_probe: int = 2
    diversity_max_cosine: float = 0.96
    rerank_pool_size: int = 16
    use_rerank: bool = True
    query_variants: Sequence[str] = field(default_factory=tuple)
    negative_texts: Sequence[str] = field(default_factory=tuple)
    negative_vectors: Sequence[Sequence[float]] = field(default_factory=tuple)
    negative_weight: float = 0.35
    reference_time: str | datetime | None = None


@dataclass(slots=True)
class SearchHit:
    node_id: str
    document_id: str
    text: str
    metadata: dict[str, Any]
    score: float
    dense_score: float
    bm25_score: float
    graph_score: float
    rerank_score: float
    recency_weight: float
    cluster_id: str | None
    parent_id: str | None


@dataclass(slots=True)
class SearchTrace:
    query_variants: list[str]
    selected_parent_ids: list[str]
    selected_cluster_ids: list[str]
    candidate_node_ids: list[str]


@dataclass(slots=True)
class SearchResponse:
    hits: list[SearchHit]
    trace: SearchTrace


class StandardTextPreprocessor:
    _relative_date_offsets = {
        "前天": -2,
        "昨天": -1,
        "今天": 0,
        "今日": 0,
        "明天": 1,
        "後天": 2,
    }

    def preprocess_document(
        self,
        text: str,
        *,
        created_at: str | datetime | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        normalized = self._normalize_relative_dates(text, created_at)
        normalized = self._normalize_sentence_punctuation(normalized)
        if metadata and metadata.get("coreference_map"):
            normalized = self._resolve_coreferences(normalized, metadata["coreference_map"])
        return normalized.strip()

    def preprocess_query(self, text: str, *, reference_time: str | datetime | None = None) -> str:
        normalized = self._normalize_relative_dates(text, reference_time)
        return self._normalize_sentence_punctuation(normalized).strip()

    def _normalize_relative_dates(self, text: str, created_at: str | datetime | None) -> str:
        base = _coerce_datetime(created_at) or datetime.now(timezone.utc)
        normalized = text
        for token, offset in self._relative_date_offsets.items():
            target = (base + timedelta(days=offset)).date().isoformat()
            normalized = normalized.replace(token, target)
        normalized = re.sub(r"(\d{4})[./年](\d{1,2})[./月](\d{1,2})日?", r"\1-\2-\3", normalized)
        return normalized

    def _normalize_sentence_punctuation(self, text: str) -> str:
        normalized = text.replace("：", ": ").replace("，", ", ").replace("；", "; ")
        normalized = normalized.replace("。", ". ").replace("？", "? ").replace("！", "! ")
        return re.sub(r"\s+", " ", normalized)

    def _resolve_coreferences(self, text: str, coreference_map: dict[str, str]) -> str:
        resolved = text
        for pronoun, entity in coreference_map.items():
            resolved = re.sub(rf"\b{re.escape(pronoun)}\b", entity, resolved)
        return resolved


class BM25Index:
    def __init__(self, documents: dict[str, list[str]]) -> None:
        self.documents = documents
        self.avgdl = 0.0
        self.doc_lengths: dict[str, int] = {}
        self.doc_freqs: dict[str, int] = defaultdict(int)
        self.k1 = 1.5
        self.b = 0.75
        self._build()

    def _build(self) -> None:
        total = 0
        for doc_id, tokens in self.documents.items():
            self.doc_lengths[doc_id] = len(tokens)
            total += len(tokens)
            for token in set(tokens):
                self.doc_freqs[token] += 1
        self.avgdl = total / max(len(self.documents), 1)

    def score(self, query: str, candidates: Iterable[str] | None = None) -> dict[str, float]:
        query_terms = _tokenize(query)
        if not query_terms:
            return {}
        targets = list(candidates) if candidates is not None else list(self.documents)
        corpus_size = max(len(self.documents), 1)
        scores: dict[str, float] = {}
        for doc_id in targets:
            tokens = self.documents.get(doc_id, [])
            if not tokens:
                scores[doc_id] = 0.0
                continue
            term_counts = Counter(tokens)
            dl = self.doc_lengths.get(doc_id, 0)
            total = 0.0
            for term in query_terms:
                freq = term_counts.get(term, 0)
                if freq == 0:
                    continue
                df = self.doc_freqs.get(term, 0)
                idf = math.log(1 + (corpus_size - df + 0.5) / (df + 0.5))
                numerator = freq * (self.k1 + 1.0)
                denominator = freq + self.k1 * (1.0 - self.b + self.b * dl / max(self.avgdl, 1.0))
                total += idf * numerator / max(denominator, 1e-9)
            scores[doc_id] = total
        return scores


class JinaOnnxTextNanoRetrievalEmbedder:
    def __init__(
        self,
        model_id: str = "jinaai/jina-embeddings-v5-text-nano-retrieval",
        *,
        provider: str = "CPUExecutionProvider",
        file_name: str = "model.onnx",
    ) -> None:
        self.model_id = model_id
        self.provider = provider
        self.file_name = file_name
        self._tokenizer = None
        self._model = None
        self._torch = None

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            from optimum.onnxruntime import ORTModelForFeatureExtraction
            import torch
            from transformers import AutoTokenizer
        except ImportError as exc:
            raise RuntimeError(
                "使用 Jina ONNX embedder 需要安裝 optimum[onnxruntime]、transformers 與 torch。"
            ) from exc
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        self._model = ORTModelForFeatureExtraction.from_pretrained(
            self.model_id,
            subfolder="onnx",
            file_name=self.file_name,
            provider=self.provider,
            trust_remote_code=True,
        )

    def embed_texts(self, texts: Sequence[str], *, is_query: bool) -> list[list[float]]:
        self._lazy_load()
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        prefix = "Query: " if is_query else "Document: "
        prepared = [text if text.startswith(("Query: ", "Document: ")) else f"{prefix}{text}" for text in texts]
        inputs = self._tokenizer(prepared, padding=True, truncation=True, return_tensors="pt")
        with self._torch.no_grad():
            outputs = self._model(**inputs)
        last_hidden_state = outputs.last_hidden_state
        lengths = inputs.attention_mask.sum(dim=1) - 1
        embeddings = last_hidden_state[self._torch.arange(last_hidden_state.size(0)), lengths]
        embeddings = self._torch.nn.functional.normalize(embeddings, p=2, dim=1)
        return embeddings.detach().cpu().tolist()


class JinaRerankerV3:
    def __init__(
        self,
        model_id: str = "jinaai/jina-reranker-v3",
        *,
        max_length: int = 1024,
        device: str | None = None,
    ) -> None:
        self.model_id = model_id
        self.max_length = max_length
        self.device = device
        self._tokenizer = None
        self._model = None
        self._torch = None

    def _lazy_load(self) -> None:
        if self._model is not None:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError as exc:
            raise RuntimeError("使用 Jina reranker 需要安裝 transformers 與 torch。") from exc
        self._torch = torch
        runtime_device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = runtime_device
        self._tokenizer = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.model_id,
            trust_remote_code=True,
            torch_dtype="auto",
        ).to(runtime_device)
        self._model.eval()

    def score(self, query: str, documents: Sequence[str]) -> list[float]:
        self._lazy_load()
        assert self._tokenizer is not None
        assert self._model is not None
        assert self._torch is not None
        if not documents:
            return []
        pairs = [(query, document) for document in documents]
        inputs = self._tokenizer(
            pairs,
            padding=True,
            truncation=True,
            max_length=self.max_length,
            return_tensors="pt",
        ).to(self.device)
        with self._torch.no_grad():
            logits = self._model(**inputs).logits.squeeze(-1)
        if logits.ndim == 0:
            return [float(logits.item())]
        return [float(item) for item in logits.detach().cpu().tolist()]


class GenericRAG:
    def __init__(
        self,
        *,
        embedder: TextEmbedder,
        reranker: Reranker | None = None,
        preprocessor: StandardTextPreprocessor | None = None,
        chunk_config: SemanticChunkConfig | None = None,
        weights: RetrievalWeights | None = None,
        recency_policy: RecencyPolicy | None = None,
        query_variant_generator: Callable[[str], Sequence[str]] | None = None,
        graph_degree: int = 4,
        graph_similarity_floor: float = 0.45,
        cluster_similarity_threshold: float = 0.8,
    ) -> None:
        self.embedder = embedder
        self.reranker = reranker
        self.preprocessor = preprocessor or StandardTextPreprocessor()
        self.chunk_config = chunk_config or SemanticChunkConfig()
        self.weights = weights or RetrievalWeights()
        self.recency_policy = recency_policy or RecencyPolicy()
        self.query_variant_generator = query_variant_generator or self._default_query_variants
        self.graph_degree = graph_degree
        self.graph_similarity_floor = graph_similarity_floor
        self.cluster_similarity_threshold = cluster_similarity_threshold
        self.document_nodes: dict[str, RAGNode] = {}
        self.leaf_nodes: dict[str, RAGNode] = {}
        self.cluster_centroids: dict[str, list[float]] = {}
        self.cluster_members: dict[str, list[str]] = {}
        self._bm25: BM25Index | None = None

    def index_documents(self, documents: Sequence[RAGDocument]) -> None:
        for document in documents:
            normalized_text = self.preprocessor.preprocess_document(
                document.text,
                created_at=document.created_at,
                metadata=document.metadata,
            )
            metadata_text = self._render_multimodal_metadata(document)
            chunks = self._semantic_chunk(normalized_text)
            if not chunks:
                chunks = [normalized_text]
            embedding_inputs = [self._build_embedding_text(chunk_text, metadata_text) for chunk_text in chunks]
            vectors = self.embedder.embed_texts(embedding_inputs, is_query=False)
            child_ids: list[str] = []
            created_at = _coerce_datetime(document.created_at)
            for index, (chunk_text, embedding_text, vector) in enumerate(zip(chunks, embedding_inputs, vectors)):
                node_id = f"{document.document_id}::chunk-{index}"
                node = RAGNode(
                    node_id=node_id,
                    document_id=document.document_id,
                    text=chunk_text,
                    embedding_text=embedding_text,
                    vector=l2_normalize(vector),
                    metadata=dict(document.metadata),
                    created_at=created_at,
                    parent_id=document.document_id,
                    depth=1,
                )
                self.leaf_nodes[node_id] = node
                child_ids.append(node_id)
            parent_node = RAGNode(
                node_id=document.document_id,
                document_id=document.document_id,
                text=normalized_text,
                embedding_text=self._build_embedding_text(normalized_text, metadata_text),
                vector=mean_vector([self.leaf_nodes[node_id].vector for node_id in child_ids]),
                metadata=dict(document.metadata),
                created_at=created_at,
                child_ids=child_ids,
                depth=0,
            )
            self.document_nodes[parent_node.node_id] = parent_node
        self._rebuild_indexes()

    def search(self, query: str, *, options: QueryOptions | None = None) -> SearchResponse:
        if not self.leaf_nodes:
            return SearchResponse(hits=[], trace=SearchTrace([], [], [], []))
        opts = options or QueryOptions()
        normalized_query = self.preprocessor.preprocess_query(query, reference_time=opts.reference_time)
        query_variants = self._collect_query_variants(normalized_query, opts)
        query_vectors = self.embedder.embed_texts(query_variants, is_query=True)
        selected_parent_ids = self._select_parents(query_vectors, opts)
        candidate_ids = [
            child_id
            for parent_id in selected_parent_ids
            for child_id in self.document_nodes[parent_id].child_ids
        ] or list(self.leaf_nodes)
        selected_cluster_ids = self._select_clusters(query_vectors, candidate_ids, opts)
        if selected_cluster_ids:
            candidate_ids = [
                node_id
                for cluster_id in selected_cluster_ids
                for node_id in self.cluster_members.get(cluster_id, [])
                if node_id in candidate_ids
            ]
        candidate_ids = list(dict.fromkeys(candidate_ids))
        dense_scores = self._dense_scores(query_vectors, candidate_ids, opts)
        bm25_scores = self._bm25.score(query_variants[0], candidate_ids) if self._bm25 else {}
        graph_scores = self._graph_scores(query_vectors, candidate_ids)
        rerank_scores = self._rerank_scores(query_variants[0], candidate_ids, dense_scores, bm25_scores, opts)
        dense_norm = _min_max_scale(dense_scores)
        bm25_norm = _min_max_scale(bm25_scores)
        graph_norm = _min_max_scale(graph_scores)
        rerank_norm = _min_max_scale(rerank_scores)
        reference_time = _coerce_datetime(opts.reference_time) or datetime.now(timezone.utc)
        aggregate: list[SearchHit] = []
        for node_id in candidate_ids:
            node = self.leaf_nodes[node_id]
            recency_weight = self.recency_policy.weight(node.created_at, now=reference_time)
            score = (
                self.weights.dense * dense_norm.get(node_id, 0.0)
                + self.weights.bm25 * bm25_norm.get(node_id, 0.0)
                + self.weights.graph * graph_norm.get(node_id, 0.0)
                + self.weights.rerank * rerank_norm.get(node_id, 0.0)
            ) * recency_weight
            aggregate.append(
                SearchHit(
                    node_id=node_id,
                    document_id=node.document_id,
                    text=node.text,
                    metadata=node.metadata,
                    score=score,
                    dense_score=dense_scores.get(node_id, 0.0),
                    bm25_score=bm25_scores.get(node_id, 0.0),
                    graph_score=graph_scores.get(node_id, 0.0),
                    rerank_score=rerank_scores.get(node_id, 0.0),
                    recency_weight=recency_weight,
                    cluster_id=node.cluster_id,
                    parent_id=node.parent_id,
                )
            )
        aggregate.sort(key=lambda item: item.score, reverse=True)
        top_k = self._dynamic_top_k(aggregate, opts)
        hits = self._apply_diversity(aggregate, top_k, opts.diversity_max_cosine)
        trace = SearchTrace(
            query_variants=list(query_variants),
            selected_parent_ids=selected_parent_ids,
            selected_cluster_ids=selected_cluster_ids,
            candidate_node_ids=candidate_ids,
        )
        return SearchResponse(hits=hits, trace=trace)

    def _rebuild_indexes(self) -> None:
        self._bm25 = BM25Index({node_id: _tokenize(node.embedding_text) for node_id, node in self.leaf_nodes.items()})
        self._build_graph()
        self._build_clusters()

    def _build_graph(self) -> None:
        node_ids = list(self.leaf_nodes)
        for node_id in node_ids:
            current = self.leaf_nodes[node_id]
            neighbors: list[tuple[float, str]] = []
            for other_id in node_ids:
                if other_id == node_id:
                    continue
                other = self.leaf_nodes[other_id]
                score = cosine_similarity(current.vector, other.vector)
                if score >= self.graph_similarity_floor:
                    neighbors.append((score, other_id))
            neighbors.sort(reverse=True)
            current.neighbor_ids = [other_id for _, other_id in neighbors[: self.graph_degree]]
            graph_vectors = [current.vector] + [self.leaf_nodes[other_id].vector for other_id in current.neighbor_ids]
            current.graph_vector = l2_normalize(mean_vector(graph_vectors))

    def _build_clusters(self) -> None:
        self.cluster_centroids = {}
        self.cluster_members = {}
        for node_id, node in self.leaf_nodes.items():
            best_cluster = None
            best_score = -1.0
            for cluster_id, centroid in self.cluster_centroids.items():
                score = cosine_similarity(node.vector, centroid)
                if score > best_score:
                    best_score = score
                    best_cluster = cluster_id
            if best_cluster is None or best_score < self.cluster_similarity_threshold:
                best_cluster = f"cluster-{len(self.cluster_centroids)}"
                self.cluster_centroids[best_cluster] = list(node.vector)
                self.cluster_members[best_cluster] = []
            self.cluster_members.setdefault(best_cluster, []).append(node_id)
            centroid = mean_vector([self.leaf_nodes[member_id].vector for member_id in self.cluster_members[best_cluster]])
            self.cluster_centroids[best_cluster] = l2_normalize(centroid)
            node.cluster_id = best_cluster

    def _semantic_chunk(self, text: str) -> list[str]:
        sentences = self._split_sentences(text)
        if len(sentences) <= 1:
            return [text.strip()] if text.strip() else []
        sentence_vectors = self.embedder.embed_texts(sentences, is_query=False)
        chunks: list[str] = []
        buffer: list[str] = [sentences[0]]
        for index in range(1, len(sentences)):
            similarity = cosine_similarity(sentence_vectors[index - 1], sentence_vectors[index])
            projected = " ".join(buffer + [sentences[index]]).strip()
            should_split = (
                similarity < self.chunk_config.similarity_threshold
                or len(buffer) >= self.chunk_config.max_sentences
                or len(projected) > self.chunk_config.max_chars
            )
            if should_split:
                chunks.append(" ".join(buffer).strip())
                buffer = [sentences[index]]
            else:
                buffer.append(sentences[index])
        if buffer:
            chunks.append(" ".join(buffer).strip())
        return [chunk for chunk in chunks if chunk]

    def _split_sentences(self, text: str) -> list[str]:
        parts = re.split(r"(?<=[.!?。！？])\s+", text.strip())
        return [part.strip() for part in parts if part.strip()]

    def _build_embedding_text(self, text: str, metadata_text: str) -> str:
        if not metadata_text:
            return text
        return f"{text}\n\n{metadata_text}"

    def _render_multimodal_metadata(self, document: RAGDocument) -> str:
        sections: list[str] = []
        if document.images:
            for image in document.images:
                caption = str(image.get("caption") or image.get("summary") or "").strip()
                labels = ", ".join(str(label) for label in image.get("labels", []) if str(label).strip())
                if caption or labels:
                    parts = [part for part in (caption, labels) if part]
                    sections.append(f"[image] {' | '.join(parts)}")
        if document.tables:
            for table in document.tables:
                title = str(table.get("title") or "").strip()
                summary = str(table.get("summary") or "").strip()
                headers = ", ".join(str(header) for header in table.get("headers", []) if str(header).strip())
                parts = [part for part in (title, summary, headers) if part]
                if parts:
                    sections.append(f"[table] {' | '.join(parts)}")
        flat_metadata = []
        for key, value in document.metadata.items():
            if key == "coreference_map":
                continue
            if isinstance(value, (str, int, float)):
                flat_metadata.append(f"{key}: {value}")
        if flat_metadata:
            sections.append("[metadata] " + " | ".join(flat_metadata))
        return "\n".join(section for section in sections if section)

    def _collect_query_variants(self, query: str, options: QueryOptions) -> list[str]:
        variants = [query]
        variants.extend(item for item in options.query_variants if item and item not in variants)
        generated = self.query_variant_generator(query)
        variants.extend(item for item in generated if item and item not in variants)
        return variants

    def _default_query_variants(self, query: str) -> Sequence[str]:
        collapsed = re.sub(r"[?？!！]+$", "", query).strip()
        plain = re.sub(r"\s+", " ", collapsed)
        return [variant for variant in {collapsed, plain} if variant and variant != query]

    def _select_parents(self, query_vectors: Sequence[Sequence[float]], options: QueryOptions) -> list[str]:
        scored = []
        for parent_id, parent in self.document_nodes.items():
            best = max(cosine_similarity(query_vector, parent.vector) for query_vector in query_vectors)
            scored.append((best, parent_id))
        scored.sort(reverse=True)
        limit = min(max(options.parent_top_k, 1), len(scored))
        return [parent_id for _, parent_id in scored[:limit]]

    def _select_clusters(
        self,
        query_vectors: Sequence[Sequence[float]],
        candidate_ids: Sequence[str],
        options: QueryOptions,
    ) -> list[str]:
        candidate_clusters = {self.leaf_nodes[node_id].cluster_id for node_id in candidate_ids if self.leaf_nodes[node_id].cluster_id}
        if not candidate_clusters:
            return []
        scored = []
        for cluster_id in candidate_clusters:
            centroid = self.cluster_centroids.get(cluster_id or "")
            if not centroid:
                continue
            best = max(cosine_similarity(query_vector, centroid) for query_vector in query_vectors)
            scored.append((best, cluster_id or ""))
        scored.sort(reverse=True)
        probe = min(max(options.cluster_probe, 1), len(scored))
        return [cluster_id for _, cluster_id in scored[:probe]]

    def _dense_scores(
        self,
        query_vectors: Sequence[Sequence[float]],
        candidate_ids: Sequence[str],
        options: QueryOptions,
    ) -> dict[str, float]:
        negative_vectors = [list(vector) for vector in options.negative_vectors]
        if options.negative_texts:
            negative_vectors.extend(self.embedder.embed_texts(options.negative_texts, is_query=False))
        scores: dict[str, float] = {}
        for node_id in candidate_ids:
            node = self.leaf_nodes[node_id]
            positive = max(cosine_similarity(query_vector, node.vector) for query_vector in query_vectors)
            penalty = 0.0
            if negative_vectors:
                penalty = max(cosine_similarity(negative_vector, node.vector) for negative_vector in negative_vectors)
            scores[node_id] = positive - options.negative_weight * penalty
        return scores

    def _graph_scores(
        self,
        query_vectors: Sequence[Sequence[float]],
        candidate_ids: Sequence[str],
    ) -> dict[str, float]:
        scores: dict[str, float] = {}
        for node_id in candidate_ids:
            node = self.leaf_nodes[node_id]
            target = node.graph_vector or node.vector
            scores[node_id] = max(cosine_similarity(query_vector, target) for query_vector in query_vectors)
        return scores

    def _rerank_scores(
        self,
        query: str,
        candidate_ids: Sequence[str],
        dense_scores: dict[str, float],
        bm25_scores: dict[str, float],
        options: QueryOptions,
    ) -> dict[str, float]:
        if not self.reranker or not options.use_rerank:
            return {}
        prelim = []
        for node_id in candidate_ids:
            prelim.append((dense_scores.get(node_id, 0.0) + bm25_scores.get(node_id, 0.0), node_id))
        prelim.sort(reverse=True)
        rerank_ids = [node_id for _, node_id in prelim[: max(options.rerank_pool_size, 1)]]
        documents = [self.leaf_nodes[node_id].embedding_text for node_id in rerank_ids]
        raw_scores = self.reranker.score(query, documents)
        return {node_id: raw_score for node_id, raw_score in zip(rerank_ids, raw_scores)}

    def _dynamic_top_k(self, ranked_hits: Sequence[SearchHit], options: QueryOptions) -> int:
        if options.top_k is not None:
            return min(max(options.top_k, 1), len(ranked_hits))
        if not ranked_hits:
            return 0
        limit = min(max(options.max_top_k, 1), len(ranked_hits))
        target = min(max(options.min_top_k, 1), limit)
        while target < limit:
            current = ranked_hits[target - 1]
            following = ranked_hits[target]
            if current.score - following.score <= options.dynamic_margin and following.score >= options.min_score:
                target += 1
                continue
            break
        return target

    def _apply_diversity(self, ranked_hits: Sequence[SearchHit], top_k: int, max_cosine: float) -> list[SearchHit]:
        selected: list[SearchHit] = []
        deferred: list[SearchHit] = []
        for hit in ranked_hits:
            vector = self.leaf_nodes[hit.node_id].vector
            if any(cosine_similarity(vector, self.leaf_nodes[item.node_id].vector) > max_cosine for item in selected):
                deferred.append(hit)
                continue
            selected.append(hit)
            if len(selected) >= top_k:
                return selected
        for hit in deferred:
            selected.append(hit)
            if len(selected) >= top_k:
                break
        return selected
