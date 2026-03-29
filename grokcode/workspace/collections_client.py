"""
Workspace Collections client.

Uses local document storage (.grokcode/workspace-docs/) as the primary
backend. xAI does not yet expose a public /vector_stores endpoint, so
the local store ensures the workspace feature works reliably for the PoC.

The interface (create_collection, upload_document, query_collection, …)
is unchanged — callers are unaffected.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from grokcode.workspace.local_store import (
    LocalDocument,
    LocalSearchResult,
    add_document,
    delete_document,
    load_all_documents,
    query_documents,
)


class CollectionsClientError(Exception):
    pass


# ---------------------------------------------------------------------------
# Thin wrappers to keep the same public interface
# ---------------------------------------------------------------------------


class Collection:
    def __init__(self, id: str, name: str, created_at: datetime) -> None:
        self.id = id
        self.name = name
        self.created_at = created_at

    @classmethod
    def from_api(cls, data: dict) -> Collection:
        return cls(
            id=data["id"],
            name=data.get("name", ""),
            created_at=datetime.fromtimestamp(data.get("created_at", 0)),
        )


class Document:
    def __init__(self, id: str, collection_id: str, metadata: dict, created_at: datetime) -> None:
        self.id = id
        self.collection_id = collection_id
        self.metadata = metadata
        self.created_at = created_at

    @classmethod
    def from_local(cls, doc: LocalDocument) -> Document:
        return cls(
            id=doc.id,
            collection_id=doc.collection_id,
            metadata=doc.metadata,
            created_at=doc.created_at,
        )


class SearchResult:
    def __init__(self, doc_id: str, content: str, score: float, metadata: dict) -> None:
        self.doc_id = doc_id
        self.content = content
        self.score = score
        self.metadata = metadata

    @classmethod
    def from_local(cls, r: LocalSearchResult) -> SearchResult:
        return cls(
            doc_id=r.doc_id,
            content=r.content,
            score=r.score,
            metadata=r.metadata,
        )


class CollectionsClient:
    """
    Workspace collections client backed by local storage.
    All operations are async for interface compatibility.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key  # kept for future remote backend

    async def close(self) -> None:
        pass  # nothing to close for local backend

    async def __aenter__(self) -> CollectionsClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        pass

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    async def create_collection(self, name: str) -> Collection:
        """Create a new local collection (generates a stable ID from the name)."""
        collection_id = f"local_{uuid.uuid5(uuid.NAMESPACE_DNS, name).hex[:16]}"
        return Collection(
            id=collection_id,
            name=name,
            created_at=datetime.now(),
        )

    async def get_collection(self, collection_id: str) -> Collection:
        """Return collection metadata (derived from local docs)."""
        docs = load_all_documents(collection_id)
        name = collection_id.replace("local_", "")
        return Collection(
            id=collection_id,
            name=name,
            created_at=docs[0].created_at if docs else datetime.now(),
        )

    async def list_collections(self) -> list[Collection]:
        """List collections by scanning local storage directories."""
        from grokcode.workspace.local_store import DOCS_DIR

        if not DOCS_DIR.exists():
            return []
        return [
            Collection(id=d.name, name=d.name.replace("local_", ""), created_at=datetime.now())
            for d in DOCS_DIR.iterdir()
            if d.is_dir()
        ]

    # ------------------------------------------------------------------
    # Document management
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        collection_id: str,
        content: str,
        metadata: dict,
    ) -> Document:
        """Store a document in the local collection."""
        local_doc = add_document(
            collection_id=collection_id,
            content=content,
            metadata=metadata,
        )
        return Document.from_local(local_doc)

    async def delete_document(self, collection_id: str, doc_id: str) -> None:
        """Remove a document from the local collection."""
        if not delete_document(collection_id=collection_id, doc_id=doc_id):
            raise CollectionsClientError(
                f"Document not found: {doc_id} in collection {collection_id}"
            )

    async def list_documents(self, collection_id: str) -> list[Document]:
        """List all documents in a local collection."""
        return [Document.from_local(doc) for doc in load_all_documents(collection_id)]

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    async def query_collection(
        self,
        collection_id: str,
        query: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search the local collection with TF-IDF keyword ranking."""
        local_results = query_documents(
            collection_id=collection_id,
            query=query,
            top_k=top_k,
        )
        return [SearchResult.from_local(r) for r in local_results]
