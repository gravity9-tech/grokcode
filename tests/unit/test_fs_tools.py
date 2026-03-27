from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from grokcode.tools.fs import ToolError, edit_file, read_directory, read_file, write_file


async def test_read_file(tmp_path: Path) -> None:
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await read_file(str(f))
    assert result == "hello world"


async def test_read_file_not_found() -> None:
    with pytest.raises(ToolError, match="not found"):
        await read_file("/nonexistent/path/file.txt")


async def test_read_file_too_large(tmp_path: Path) -> None:
    f = tmp_path / "big.txt"
    f.write_bytes(b"x" * (101 * 1024))
    with pytest.raises(ToolError, match="too large"):
        await read_file(str(f))


async def test_read_directory(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("a")
    (tmp_path / "b.py").write_text("b")
    result = await read_directory(str(tmp_path))
    assert "a.py" in result
    assert "b.py" in result


async def test_read_directory_recursive(tmp_path: Path) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.py").write_text("n")
    result = await read_directory(str(tmp_path), recursive=True)
    assert "nested.py" in result


async def test_write_file_new(tmp_path: Path) -> None:
    path = str(tmp_path / "new.py")
    result = await write_file(path, "print('hello')", auto_confirm=True)
    assert "Written" in result
    assert Path(path).read_text() == "print('hello')"


async def test_write_file_overwrite_confirmed(tmp_path: Path) -> None:
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    with patch("grokcode.tools.fs.confirm", return_value=True):
        result = await write_file(str(f), "new content")
    assert Path(str(f)).read_text() == "new content"


async def test_write_file_overwrite_denied(tmp_path: Path) -> None:
    f = tmp_path / "existing.txt"
    f.write_text("original")
    with patch("grokcode.tools.fs.confirm", return_value=False):
        result = await write_file(str(f), "new content")
    assert "Skipped" in result
    assert f.read_text() == "original"


async def test_edit_file(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("def foo():\n    return 1\n")
    result = await edit_file(str(f), "return 1", "return 42")
    assert "Edited" in result
    assert f.read_text() == "def foo():\n    return 42\n"


async def test_edit_file_not_found() -> None:
    with pytest.raises(ToolError, match="not found"):
        await edit_file("/tmp/nonexistent_xyz.py", "old", "new")


async def test_edit_file_zero_matches(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("def foo(): pass\n")
    with pytest.raises(ToolError, match="not found"):
        await edit_file(str(f), "def bar()", "def baz()")


async def test_edit_file_multiple_matches(tmp_path: Path) -> None:
    f = tmp_path / "code.py"
    f.write_text("x = 1\nx = 1\n")
    with pytest.raises(ToolError, match="found 2 times"):
        await edit_file(str(f), "x = 1", "x = 2")
