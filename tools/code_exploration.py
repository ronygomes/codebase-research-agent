import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

from pathspec import PathSpec
from pydantic import BaseModel, Field

from tools.base import Tool, ToolContext


NOISE_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    ".venv",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".DS_Store",
}


_EXTENSION_TO_LANGUAGE = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".rs": "Rust",
    ".go": "Go",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C",
    ".md": "Markdown",
    ".html": "HTML",
    ".css": "CSS",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".sh": "Shell",
}


def _load_gitignore(repo_path: Path) -> PathSpec:
    gitignore = repo_path / ".gitignore"
    patterns = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    return PathSpec.from_lines("gitignore", patterns)


def _resolve_safe(repo_path: Path, raw_path: str) -> Path:
    target = (repo_path / raw_path.lstrip("/")).resolve()
    if not target.is_relative_to(repo_path.resolve()):
        raise ValueError("Path escapes repository root")
    return target


def _is_binary(path: Path) -> bool:
    with path.open("rb") as f:
        return b"\x00" in f.read(8192)


def _is_ignored(repo_path: Path, target: Path, spec: PathSpec) -> bool:
    if target.name in NOISE_NAMES:
        return True
    relative = target.relative_to(repo_path)
    if any(part in NOISE_NAMES for part in relative.parts):
        return True
    return spec.match_file(str(relative))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


class ListFilesArgs(BaseModel):
    path: str = Field(description="Path within the repo, '/' or '' for root")


class ListFilesTool(Tool):
    name: ClassVar[str] = "list_files"
    description: ClassVar[str] = (
        "List files and directories directly under a path within the repository. "
        "Does not recurse — call again on a subdirectory to descend."
    )
    args_model: ClassVar[type[BaseModel]] = ListFilesArgs

    def execute(self, ctx: ToolContext, args: ListFilesArgs) -> str:
        target = _resolve_safe(ctx.repo_path, args.path)
        if not target.exists():
            raise FileNotFoundError(f"Path not found: {args.path}")
        if target.is_file():
            raise ValueError("Path is a file, use read_file instead")

        spec = _load_gitignore(ctx.repo_path)
        entries: list[dict[str, Any]] = []
        for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if _is_ignored(ctx.repo_path, entry, spec):
                continue
            item: dict[str, Any] = {
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
            }
            if entry.is_file():
                item["size_bytes"] = entry.stat().st_size
            entries.append(item)

        return json.dumps({"path": args.path, "entries": entries})


class ReadFileArgs(BaseModel):
    path: str = Field(description="File path within the repo")
    line_start: int | None = Field(default=None, ge=1)
    line_end: int | None = Field(default=None, ge=1)


class ReadFileTool(Tool):
    name: ClassVar[str] = "read_file"
    description: ClassVar[str] = (
        "Read a file's contents. Optionally limit to a 1-indexed inclusive line range. "
        "Output is line-numbered. Files larger than 1 MB require a line range."
    )
    args_model: ClassVar[type[BaseModel]] = ReadFileArgs

    MAX_SIZE_BYTES: ClassVar[int] = 1_000_000

    def execute(self, ctx: ToolContext, args: ReadFileArgs) -> str:
        target = _resolve_safe(ctx.repo_path, args.path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {args.path}")
        if target.is_dir():
            raise ValueError("Path is a directory, use list_files instead")
        if _is_binary(target):
            raise ValueError(f"Cannot read binary file: {args.path}")
        if (
            args.line_start is None
            and args.line_end is None
            and target.stat().st_size > self.MAX_SIZE_BYTES
        ):
            size_mb = target.stat().st_size / 1024 / 1024
            raise ValueError(
                f"File is {size_mb:.1f} MB (>1 MB limit). "
                "Specify line_start and line_end to read a portion."
            )
        if args.line_start and args.line_end and args.line_end < args.line_start:
            raise ValueError("line_end must be >= line_start")

        lines = _read_text(target).splitlines()
        total = len(lines)
        start = args.line_start or 1
        end = min(args.line_end or total, total)

        header = f"File: {args.path} (lines {start}-{end} of {total} total)"
        body = "\n".join(f"{i:>4}| {lines[i - 1]}" for i in range(start, end + 1))
        return f"{header}\n\n{body}"


class SearchCodeArgs(BaseModel):
    query: str = Field(description="Regex pattern")
    file_pattern: str | None = Field(
        default=None, description="Glob like '*.py' or '**/*.ts'"
    )


class SearchCodeTool(Tool):
    name: ClassVar[str] = "search_code"
    description: ClassVar[str] = (
        "Search the repository for a regex pattern. "
        "Returns up to 50 matches with file path and line number."
    )
    args_model: ClassVar[type[BaseModel]] = SearchCodeArgs

    MAX_MATCHES: ClassVar[int] = 50
    MAX_LINE_LENGTH: ClassVar[int] = 200

    def execute(self, ctx: ToolContext, args: SearchCodeArgs) -> str:
        try:
            pattern = re.compile(args.query)
        except re.error as e:
            raise ValueError(f"Invalid regex: {e}") from e

        spec = _load_gitignore(ctx.repo_path)
        matches: list[dict[str, Any]] = []
        total = 0

        for path in _walk_files(ctx.repo_path, args.file_pattern, spec):
            if _is_binary(path):
                continue
            try:
                text = _read_text(path)
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    total += 1
                    if len(matches) < self.MAX_MATCHES:
                        matches.append(
                            {
                                "file": str(path.relative_to(ctx.repo_path)),
                                "line": lineno,
                                "content": line[: self.MAX_LINE_LENGTH],
                            }
                        )

        return json.dumps(
            {
                "query": args.query,
                "match_count": total,
                "truncated": total > self.MAX_MATCHES,
                "matches": matches,
            }
        )


def _walk_files(root: Path, file_pattern: str | None, spec: PathSpec) -> Iterator[Path]:
    pattern = file_pattern or "**/*"
    for path in root.glob(pattern):
        if not path.is_file():
            continue
        if _is_ignored(root, path, spec):
            continue
        yield path


class GetFileSummaryArgs(BaseModel):
    path: str = Field(description="File path within the repo")


class GetFileSummaryTool(Tool):
    name: ClassVar[str] = "get_file_summary"
    description: ClassVar[str] = (
        "Quick overview of a file: size, line count, detected language, and first 30 lines."
    )
    args_model: ClassVar[type[BaseModel]] = GetFileSummaryArgs

    PREVIEW_LINES: ClassVar[int] = 30

    def execute(self, ctx: ToolContext, args: GetFileSummaryArgs) -> str:
        target = _resolve_safe(ctx.repo_path, args.path)
        if not target.exists():
            raise FileNotFoundError(f"File not found: {args.path}")
        if target.is_dir():
            raise ValueError("Path is a directory, use list_files instead")

        size = target.stat().st_size
        language = _EXTENSION_TO_LANGUAGE.get(target.suffix.lower(), "unknown")

        if _is_binary(target):
            return (
                f"File: {args.path} ({size} bytes)\n"
                f"Language: {language} (binary, no preview)\n"
            )

        lines = _read_text(target).splitlines()
        preview = lines[: self.PREVIEW_LINES]
        preview_body = "\n".join(f"{i:>4}| {line}" for i, line in enumerate(preview, 1))

        return (
            f"File: {args.path} ({len(lines)} lines, {size} bytes)\n"
            f"Language: {language}\n\n"
            f"First {len(preview)} lines:\n"
            f"{preview_body}"
        )
