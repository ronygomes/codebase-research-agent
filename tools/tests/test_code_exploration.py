import json
from pathlib import Path
from typing import Any

import pytest

from tools.base import ToolContext
from tools.code_exploration import (
    GetFileSummaryTool,
    ListFilesTool,
    ReadFileTool,
    SearchCodeTool,
)


@pytest.fixture
def fake_repo(tmp_path: Any) -> Path:
    (tmp_path / "fastapi").mkdir()
    (tmp_path / "fastapi" / "__init__.py").write_text(
        "from fastapi.applications import FastAPI\n"
    )
    (tmp_path / "fastapi" / "applications.py").write_text(
        "class FastAPI:\n    def __init__(self):\n        pass\n"
    )
    (tmp_path / "README.md").write_text("# Test repo\n\nA test repository.\n")
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\nsecret.txt\n")
    (tmp_path / "secret.txt").write_text("hidden")
    return tmp_path


def _ctx(repo: Path) -> ToolContext:
    return ToolContext(session_id=1, repository_id=1, repo_path=repo)


def test_list_files_returns_immediate_children(fake_repo: Path) -> None:
    tool = ListFilesTool()

    result = tool.execute(_ctx(fake_repo), ListFilesTool.args_model(path="/"))

    data = json.loads(result)
    names = {e["name"] for e in data["entries"]}
    assert "fastapi" in names
    assert "README.md" in names
    assert "applications.py" not in names


def test_list_files_respects_gitignore(fake_repo: Path) -> None:
    tool = ListFilesTool()

    result = tool.execute(_ctx(fake_repo), ListFilesTool.args_model(path="/"))

    names = {e["name"] for e in json.loads(result)["entries"]}
    assert "secret.txt" not in names


def test_list_files_rejects_path_escape(fake_repo: Path) -> None:
    tool = ListFilesTool()

    with pytest.raises(ValueError, match="escapes"):
        tool.execute(_ctx(fake_repo), ListFilesTool.args_model(path="../../../etc"))


def test_read_file_returns_numbered_lines(fake_repo: Path) -> None:
    tool = ReadFileTool()

    result = tool.execute(
        _ctx(fake_repo), ReadFileTool.args_model(path="fastapi/__init__.py")
    )

    assert "1| from fastapi.applications import FastAPI" in result
    assert "lines 1-1 of 1 total" in result


def test_read_file_supports_line_range(fake_repo: Path) -> None:
    (fake_repo / "long.py").write_text("\n".join(f"line {i}" for i in range(1, 21)))
    tool = ReadFileTool()

    result = tool.execute(
        _ctx(fake_repo), ReadFileTool.args_model(path="long.py", line_start=5, line_end=8)
    )

    assert "5| line 5" in result
    assert "8| line 8" in result
    assert "4| line 4" not in result
    assert "9| line 9" not in result


def test_read_file_rejects_binary(fake_repo: Path) -> None:
    (fake_repo / "image.bin").write_bytes(b"\x00\x01\x02header\x00\x00")
    tool = ReadFileTool()

    with pytest.raises(ValueError, match="binary"):
        tool.execute(_ctx(fake_repo), ReadFileTool.args_model(path="image.bin"))


def test_read_file_requires_range_for_files_over_1mb(fake_repo: Path) -> None:
    (fake_repo / "big.txt").write_text("x" * 1_100_000)
    tool = ReadFileTool()

    with pytest.raises(ValueError, match="1 MB"):
        tool.execute(_ctx(fake_repo), ReadFileTool.args_model(path="big.txt"))


def test_search_code_finds_pattern_matches(fake_repo: Path) -> None:
    tool = SearchCodeTool()

    result = tool.execute(_ctx(fake_repo), SearchCodeTool.args_model(query="FastAPI"))

    data = json.loads(result)
    assert data["match_count"] >= 2
    files = {m["file"] for m in data["matches"]}
    assert "fastapi/__init__.py" in files
    assert "fastapi/applications.py" in files


def test_search_code_filters_by_file_pattern(fake_repo: Path) -> None:
    tool = SearchCodeTool()

    result = tool.execute(
        _ctx(fake_repo),
        SearchCodeTool.args_model(query="repo", file_pattern="**/*.md"),
    )

    files = {m["file"] for m in json.loads(result)["matches"]}
    assert files == {"README.md"}


def test_search_code_returns_invalid_regex_error(fake_repo: Path) -> None:
    tool = SearchCodeTool()

    with pytest.raises(ValueError, match="Invalid regex"):
        tool.execute(_ctx(fake_repo), SearchCodeTool.args_model(query="["))


def test_get_file_summary_returns_stats_and_preview(fake_repo: Path) -> None:
    tool = GetFileSummaryTool()

    result = tool.execute(
        _ctx(fake_repo), GetFileSummaryTool.args_model(path="fastapi/applications.py")
    )

    assert "fastapi/applications.py" in result
    assert "Python" in result
    assert "class FastAPI:" in result
    assert "lines" in result
