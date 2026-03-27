from __future__ import annotations

"""
Local workspace document store.

Documents are stored as JSON files under .grokcode/workspace-docs/.
Querying uses simple TF-IDF-style keyword ranking — fast, offline,
no API dependency for the PoC.

This is the primary backend for workspace init/index/query.
When xAI publishes a stable Collections/RAG endpoint it can be
swapped in as an optional remote backend.
"""

import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

DOCS_DIR = Path(".grokcode") / "workspace-docs"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LocalDocument:
    def __init__(
        self,
        doc_id: str,
        collection_id: str,
        path: str,
        content: str,
        metadata: dict,
        created_at: datetime,
    ) -> None:
        self.id = doc_id
        self.collection_id = collection_id
        self.path = path
        self.content = content
        self.metadata = metadata
        self.created_at = created_at

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "collection_id": self.collection_id,
            "path": self.path,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "LocalDocument":
        return cls(
            doc_id=data["id"],
            collection_id=data["collection_id"],
            path=data["path"],
            content=data["content"],
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


class LocalSearchResult:
    def __init__(self, doc_id: str, content: str, score: float, metadata: dict) -> None:
        self.doc_id = doc_id
        self.content = content
        self.score = score
        self.metadata = metadata


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


def _docs_dir(collection_id: str) -> Path:
    return DOCS_DIR / collection_id


def save_document(doc: LocalDocument) -> None:
    d = _docs_dir(doc.collection_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{doc.id}.json").write_text(json.dumps(doc.to_dict(), indent=2))


def load_all_documents(collection_id: str) -> list[LocalDocument]:
    d = _docs_dir(collection_id)
    if not d.exists():
        return []
    docs = []
    for f in sorted(d.glob("*.json")):
        try:
            docs.append(LocalDocument.from_dict(json.loads(f.read_text())))
        except Exception:
            continue
    return docs


def delete_document(collection_id: str, doc_id: str) -> bool:
    path = _docs_dir(collection_id) / f"{doc_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


def add_document(
    collection_id: str,
    content: str,
    metadata: dict,
) -> LocalDocument:
    doc = LocalDocument(
        doc_id=f"local_{uuid.uuid4().hex[:12]}",
        collection_id=collection_id,
        path=metadata.get("path", ""),
        content=content,
        metadata=metadata,
        created_at=datetime.now(),
    )
    save_document(doc)
    return doc


# ---------------------------------------------------------------------------
# Keyword search (TF-IDF cosine similarity)
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z0-9_]+", text.lower())


def _tf(tokens: list[str]) -> dict[str, float]:
    count = Counter(tokens)
    total = len(tokens) or 1
    return {t: c / total for t, c in count.items()}


def query_documents(
    collection_id: str,
    query: str,
    top_k: int = 5,
) -> list[LocalSearchResult]:
    """Return the top_k most relevant document chunks for a query."""
    docs = load_all_documents(collection_id)
    if not docs:
        return []

    q_tokens = _tokenise(query)
    if not q_tokens:
        # Return first top_k docs as fallback
        return [
            LocalSearchResult(
                doc_id=d.id,
                content=_best_chunk(d.content, query),
                score=0.5,
                metadata={**d.metadata, "path": d.path},
            )
            for d in docs[:top_k]
        ]

    q_tf = _tf(q_tokens)
    q_set = set(q_tokens)

    # Build IDF over corpus
    df: Counter = Counter()
    for doc in docs:
        doc_tokens = set(_tokenise(doc.content))
        df.update(doc_tokens & q_set)

    N = len(docs)
    idf = {t: math.log((N + 1) / (df.get(t, 0) + 1)) + 1 for t in q_set}

    # Score each document
    scored: list[tuple[float, LocalDocument]] = []
    for doc in docs:
        d_tokens = _tokenise(doc.content)
        d_tf = _tf(d_tokens)
        score = sum(q_tf.get(t, 0) * d_tf.get(t, 0) * idf.get(t, 0) for t in q_set)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [
        LocalSearchResult(
            doc_id=doc.id,
            content=_best_chunk(doc.content, query),
            score=score,
            metadata={**doc.metadata, "path": doc.path},
        )
        for score, doc in scored[:top_k]
    ]


def _best_chunk(content: str, query: str, chunk_size: int = 800) -> str:
    """Return the most query-relevant chunk of a document."""
    if len(content) <= chunk_size:
        return content

    q_words = set(_tokenise(query))
    lines = content.splitlines()
    best_start = 0
    best_score = -1
    window: list[str] = []
    char_count = 0

    # Slide a window of ~chunk_size chars across the document
    i = 0
    while i < len(lines):
        window.append(lines[i])
        char_count += len(lines[i])
        if char_count > chunk_size:
            score = sum(1 for w in _tokenise(" ".join(window)) if w in q_words)
            if score > best_score:
                best_score = score
                best_start = max(0, i - len(window) + 1)
            window.pop(0)
            char_count -= len(window[0]) if window else 0
        i += 1

    result_lines = lines[best_start : best_start + 40]
    return "\n".join(result_lines)[:chunk_size]
