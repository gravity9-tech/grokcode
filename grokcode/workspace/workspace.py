"""Business logic for workspace (Collections) operations."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from grokcode.workspace.collections_client import CollectionsClient, Document

logger = logging.getLogger(__name__)

WORKSPACE_INDEX_PATH = Path(".grokcode") / "workspace-index.json"
WORKSPACE_CONFIG_FILENAME = "grokcode.workspace.json"

INDEXABLE_EXTENSIONS = {
    ".py",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".rst",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rs",
    ".java",
    ".kt",
    ".html",
    ".css",
    ".sh",
    ".sql",
}
MAX_FILE_SIZE = 100 * 1024  # 100 KB


async def init_workspace(
    name: str,
    team_id: str,
    client: CollectionsClient,
) -> dict:
    """
    Create a new xAI Collection and write grokcode.workspace.json.
    Returns the workspace config dict.
    """
    collection = await client.create_collection(name)

    workspace_data = {
        "workspace": name,
        "collection_id": collection.id,
        "team_id": team_id,
        "rules": [],
        "mcp_servers": [],
    }

    config_path = Path.cwd() / WORKSPACE_CONFIG_FILENAME
    config_path.write_text(json.dumps(workspace_data, indent=2))
    logger.info("Workspace config written to %s", config_path)

    return workspace_data


async def index_paths(
    paths: list[Path],
    collection_id: str,
    client: CollectionsClient,
    tag: str = "",
) -> tuple[list[Document], list[str]]:
    """
    Walk paths, upload eligible files to the collection.
    Returns (uploaded_docs, skipped_paths).
    """
    uploaded: list[Document] = []
    skipped: list[str] = []

    files = _collect_files(paths)

    for file_path in files:
        size = file_path.stat().st_size
        if size > MAX_FILE_SIZE:
            skipped.append(f"{file_path} (too large: {size // 1024}KB)")
            continue
        if file_path.suffix.lower() not in INDEXABLE_EXTENSIONS:
            skipped.append(f"{file_path} (unsupported extension)")
            continue

        try:
            content = file_path.read_text(errors="replace")
            metadata: dict = {
                "path": str(file_path),
                "size": size,
            }
            if tag:
                metadata["tag"] = tag

            doc = await client.upload_document(
                collection_id=collection_id,
                content=content,
                metadata=metadata,
            )
            uploaded.append(doc)
            _persist_doc_id(file_path, doc.id)
        except Exception as e:
            skipped.append(f"{file_path} (upload error: {e})")

    return uploaded, skipped


async def remove_document(
    collection_id: str,
    doc_id: str,
    client: CollectionsClient,
) -> None:
    """Delete a document from the collection and remove it from the local index."""
    await client.delete_document(collection_id, doc_id)
    _remove_doc_from_index(doc_id)


def _collect_files(paths: list[Path]) -> list[Path]:
    """Recursively expand directories; return all eligible file paths."""
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for child in sorted(p.rglob("*")):
                if child.is_file() and not _is_ignored(child):
                    files.append(child)
    return files


def _is_ignored(path: Path) -> bool:
    """Return True for paths that should never be indexed."""
    ignored_parts = {
        ".git",
        ".grokcode",
        "__pycache__",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        ".eggs",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
    }
    return any(part in ignored_parts for part in path.parts)


def _load_index() -> dict:
    if WORKSPACE_INDEX_PATH.exists():
        try:
            return json.loads(WORKSPACE_INDEX_PATH.read_text())
        except Exception:
            pass
    return {}


def _persist_doc_id(file_path: Path, doc_id: str) -> None:
    index = _load_index()
    index[str(file_path)] = doc_id
    WORKSPACE_INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    WORKSPACE_INDEX_PATH.write_text(json.dumps(index, indent=2))


def _remove_doc_from_index(doc_id: str) -> None:
    index = _load_index()
    updated = {k: v for k, v in index.items() if v != doc_id}
    WORKSPACE_INDEX_PATH.write_text(json.dumps(updated, indent=2))


def load_workspace_index() -> dict[str, str]:
    """Return {file_path: doc_id} mapping from the local index."""
    return _load_index()
