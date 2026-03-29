from __future__ import annotations

from pathlib import Path

INCLUDE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".cs",
    ".cpp",
    ".c",
    ".h",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}
INCLUDE_FILENAMES = {".env.example", "Dockerfile", "docker-compose.yml"}
SKIP_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    "target",
    "vendor",
    ".grokcode",
}
MAX_FILE_SIZE = 50 * 1024  # 50 KB
KEY_FILES = {
    "README.md",
    "pyproject.toml",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "Dockerfile",
    "docker-compose.yml",
}
KEY_FILE_LINES = 100
OTHER_FILE_LINES = 30
OTHER_FILES_CAP = 60  # avoid enormous summaries


def collect_files(path: Path) -> list[Path]:
    """Recursively collect relevant source files, skipping ignored dirs and large files."""
    result: list[Path] = []
    for entry in path.rglob("*"):
        if any(part in SKIP_DIRS for part in entry.parts):
            continue
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in INCLUDE_EXTENSIONS and entry.name not in INCLUDE_FILENAMES:
            continue
        try:
            if entry.stat().st_size > MAX_FILE_SIZE:
                continue
        except OSError:
            continue
        result.append(entry)
    return sorted(result)


def _build_tree(path: Path, max_depth: int = 2) -> str:
    """Build a directory tree string up to max_depth levels."""
    lines: list[str] = [str(path) + "/"]

    def _walk(p: Path, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        except PermissionError:
            return
        for entry in entries:
            if entry.name in SKIP_DIRS:
                continue
            indent = "  " * (depth - 1)
            suffix = "/" if entry.is_dir() else ""
            lines.append(f"{indent}├── {entry.name}{suffix}")
            if entry.is_dir() and depth < max_depth:
                _walk(entry, depth + 1)

    _walk(path, 1)
    return "\n".join(lines)


def build_summary(path: Path, files: list[Path]) -> str:
    """Build a structured codebase summary string to send to Grok."""
    sections: list[str] = []

    sections.append("## Directory Structure\n" + _build_tree(path))

    key_found: list[Path] = []
    other_files: list[Path] = []
    test_files: list[Path] = []
    ci_files: list[Path] = []

    for f in files:
        try:
            rel = f.relative_to(path)
        except ValueError:
            rel = Path(f.name)

        if f.name in KEY_FILES:
            key_found.append(f)
        elif "test" in f.name.lower() or any("test" in part.lower() for part in rel.parts):
            test_files.append(rel)
        elif ".github" in rel.parts and "workflows" in rel.parts:
            ci_files.append(rel)
        else:
            other_files.append(f)

    if key_found:
        sections.append("## Key Files")
        for f in key_found:
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()[:KEY_FILE_LINES]
                sections.append(f"### {f.name}\n```\n" + "\n".join(lines) + "\n```")
            except OSError:
                pass

    if other_files:
        sections.append("## Source Files (first 30 lines each)")
        for f in other_files[:OTHER_FILES_CAP]:
            try:
                rel = f.relative_to(path)
            except ValueError:
                rel = Path(f.name)
            try:
                lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()[
                    :OTHER_FILE_LINES
                ]
                sections.append(f"### {rel}\n```\n" + "\n".join(lines) + "\n```")
            except OSError:
                pass

    if test_files:
        sections.append("## Test Files\n" + "\n".join(f"- {p}" for p in test_files))

    if ci_files:
        sections.append("## CI/CD Config\n" + "\n".join(f"- {p}" for p in ci_files))

    return "\n\n".join(sections)
