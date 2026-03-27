from __future__ import annotations

"""
Integration tests for the local workspace (Collections) store.
No HTTP mocking needed — the client is fully local.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from grokcode.workspace.collections_client import (
    CollectionsClient,
    CollectionsClientError,
)
from grokcode.workspace.local_store import DOCS_DIR


# ---------------------------------------------------------------------------
# Fixture: redirect local store to tmp_path
# ---------------------------------------------------------------------------


@pytest.fixture
def local_docs_dir(tmp_path: Path):
    """Patch DOCS_DIR to a temp directory for test isolation."""
    docs_dir = tmp_path / ".grokcode" / "workspace-docs"
    with (
        patch("grokcode.workspace.local_store.DOCS_DIR", docs_dir),
        patch("grokcode.workspace.collections_client.DOCS_DIR", docs_dir, create=True),
    ):
        yield docs_dir


@pytest.fixture
def client() -> CollectionsClient:
    return CollectionsClient()


# ---------------------------------------------------------------------------
# create_collection
# ---------------------------------------------------------------------------


async def test_create_collection(client: CollectionsClient, local_docs_dir: Path) -> None:
    collection = await client.create_collection("my-project")
    assert collection.id.startswith("local_")
    assert collection.name == "my-project"
    await client.close()


async def test_create_collection_deterministic(client: CollectionsClient, local_docs_dir: Path) -> None:
    """Same name always produces the same collection ID."""
    c1 = await client.create_collection("stable-name")
    c2 = await client.create_collection("stable-name")
    assert c1.id == c2.id
    await client.close()


# ---------------------------------------------------------------------------
# upload + list documents
# ---------------------------------------------------------------------------


async def test_upload_and_list_documents(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("test-col")

    doc1 = await client.upload_document(
        collection_id=collection.id,
        content="FastAPI is a modern Python web framework.",
        metadata={"path": "docs/ARCH.md"},
    )
    doc2 = await client.upload_document(
        collection_id=collection.id,
        content="Use Redis for rate limiting with fastapi-limiter.",
        metadata={"path": "CODING_STANDARDS.md"},
    )

    docs = await client.list_documents(collection.id)
    assert len(docs) == 2
    ids = {d.id for d in docs}
    assert doc1.id in ids
    assert doc2.id in ids
    await client.close()


async def test_list_documents_empty(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("empty-col")
    docs = await client.list_documents(collection.id)
    assert docs == []
    await client.close()


# ---------------------------------------------------------------------------
# delete_document
# ---------------------------------------------------------------------------


async def test_delete_document(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("del-col")
    doc = await client.upload_document(
        collection_id=collection.id,
        content="Content to delete.",
        metadata={"path": "delete_me.md"},
    )

    await client.delete_document(collection.id, doc.id)

    docs = await client.list_documents(collection.id)
    assert all(d.id != doc.id for d in docs)
    await client.close()


async def test_delete_document_not_found(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("col")
    with pytest.raises(CollectionsClientError, match="not found"):
        await client.delete_document(collection.id, "nonexistent_doc_id")
    await client.close()


# ---------------------------------------------------------------------------
# query_collection
# ---------------------------------------------------------------------------


async def test_query_collection_returns_relevant_doc(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("search-col")

    await client.upload_document(
        collection_id=collection.id,
        content="FastAPI is a modern Python web framework built on Starlette.",
        metadata={"path": "docs/ARCHITECTURE.md"},
    )
    await client.upload_document(
        collection_id=collection.id,
        content="Redis is an in-memory data structure store used for caching.",
        metadata={"path": "docs/INFRA.md"},
    )

    results = await client.query_collection(collection.id, "FastAPI framework", top_k=3)
    assert len(results) >= 1
    top = results[0]
    assert "FastAPI" in top.content or "framework" in top.content
    await client.close()


async def test_query_collection_empty(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("empty-search-col")
    results = await client.query_collection(collection.id, "anything", top_k=5)
    assert results == []
    await client.close()


async def test_query_collection_returns_source_metadata(
    client: CollectionsClient, local_docs_dir: Path
) -> None:
    collection = await client.create_collection("meta-col")
    await client.upload_document(
        collection_id=collection.id,
        content="Use Pydantic v2 for all data models.",
        metadata={"path": "CODING_STANDARDS.md", "tag": "standards"},
    )

    results = await client.query_collection(collection.id, "Pydantic models")
    assert len(results) >= 1
    assert results[0].metadata.get("path") == "CODING_STANDARDS.md"
    await client.close()


# ---------------------------------------------------------------------------
# Full init → index → query flow
# ---------------------------------------------------------------------------


async def test_workspace_init_and_index(tmp_path: Path, local_docs_dir: Path) -> None:
    """Integration: init workspace → index two files → query returns relevant result."""
    (tmp_path / "main.py").write_text("def hello(): return 'world'")
    (tmp_path / "README.md").write_text("# FastAPI Project\nThis project uses FastAPI.")

    index_path = tmp_path / ".grokcode" / "workspace-index.json"

    async with CollectionsClient() as client:
        from grokcode.workspace.workspace import init_workspace, index_paths

        with patch("pathlib.Path.cwd", return_value=tmp_path):
            workspace_data = await init_workspace(
                name="demo-project",
                team_id="demo-team",
                client=client,
            )

        collection_id = workspace_data["collection_id"]
        assert collection_id.startswith("local_")

        with patch("grokcode.workspace.workspace.WORKSPACE_INDEX_PATH", index_path):
            uploaded, skipped = await index_paths(
                paths=[tmp_path],
                collection_id=collection_id,
                client=client,
            )

        assert len(uploaded) >= 2  # main.py + README.md (+ possibly grokcode.workspace.json)
        assert len(skipped) == 0

        results = await client.query_collection(collection_id, "FastAPI project")
        assert len(results) >= 1
        assert any("FastAPI" in r.content for r in results)
