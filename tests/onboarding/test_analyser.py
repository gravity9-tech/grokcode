from __future__ import annotations

from pathlib import Path

import pytest

from grokcode.onboarding.analyser import (
    INCLUDE_EXTENSIONS,
    MAX_FILE_SIZE,
    SKIP_DIRS,
    build_summary,
    collect_files,
)


def _make_project(tmp_path: Path) -> None:
    """Create a minimal fake project tree."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('hello')")
    (tmp_path / "src" / "service.py").write_text("class MyService: pass")
    (tmp_path / "README.md").write_text("# My Project\nA cool project.")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest]\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_service.py").write_text("def test_foo(): pass")


def test_collect_files_finds_source_files(tmp_path: Path) -> None:
    _make_project(tmp_path)
    files = collect_files(tmp_path)
    names = {f.name for f in files}
    assert "main.py" in names
    assert "service.py" in names
    assert "README.md" in names
    assert "pyproject.toml" in names


def test_collect_files_skips_git(tmp_path: Path) -> None:
    _make_project(tmp_path)
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]")
    files = collect_files(tmp_path)
    assert not any(".git" in str(f) for f in files)


def test_collect_files_skips_node_modules(tmp_path: Path) -> None:
    _make_project(tmp_path)
    nm = tmp_path / "node_modules" / "lodash"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = {}")
    files = collect_files(tmp_path)
    assert not any("node_modules" in str(f) for f in files)


def test_collect_files_skips_pycache(tmp_path: Path) -> None:
    _make_project(tmp_path)
    pc = tmp_path / "src" / "__pycache__"
    pc.mkdir()
    (pc / "main.cpython-311.pyc").write_bytes(b"\x00" * 100)
    files = collect_files(tmp_path)
    assert not any("__pycache__" in str(f) for f in files)


def test_collect_files_skips_large_files(tmp_path: Path) -> None:
    _make_project(tmp_path)
    big = tmp_path / "big.py"
    big.write_bytes(b"x" * (MAX_FILE_SIZE + 1))
    files = collect_files(tmp_path)
    assert big not in files


def test_collect_files_respects_extensions(tmp_path: Path) -> None:
    (tmp_path / "script.py").write_text("x = 1")
    (tmp_path / "binary.exe").write_bytes(b"\x00" * 100)
    (tmp_path / "data.csv").write_text("a,b,c")
    files = collect_files(tmp_path)
    names = {f.name for f in files}
    assert "script.py" in names
    assert "binary.exe" not in names
    assert "data.csv" not in names


def test_collect_files_includes_dockerfile(tmp_path: Path) -> None:
    (tmp_path / "Dockerfile").write_text("FROM python:3.11")
    files = collect_files(tmp_path)
    assert any(f.name == "Dockerfile" for f in files)


def test_build_summary_contains_tree(tmp_path: Path) -> None:
    _make_project(tmp_path)
    files = collect_files(tmp_path)
    summary = build_summary(tmp_path, files)
    assert "Directory Structure" in summary
    assert "src" in summary


def test_build_summary_contains_key_files(tmp_path: Path) -> None:
    _make_project(tmp_path)
    files = collect_files(tmp_path)
    summary = build_summary(tmp_path, files)
    assert "README.md" in summary
    assert "pyproject.toml" in summary


def test_build_summary_lists_test_files(tmp_path: Path) -> None:
    _make_project(tmp_path)
    files = collect_files(tmp_path)
    summary = build_summary(tmp_path, files)
    assert "Test Files" in summary
    assert "test_service.py" in summary


def test_build_summary_empty_directory(tmp_path: Path) -> None:
    summary = build_summary(tmp_path, [])
    assert "Directory Structure" in summary
