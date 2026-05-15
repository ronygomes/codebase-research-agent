from pathlib import Path
from unittest.mock import patch

from repos.git_client import (
    DulwichGitClient,
    SystemGitClient,
    get_git_client,
)


def test_system_git_client_clones_via_subprocess() -> None:
    client = SystemGitClient()

    with patch("repos.git_client.subprocess.run") as mock_run:
        client.clone("https://github.com/a/b", Path("/tmp/x"), depth=1)

    mock_run.assert_called_once_with(
        ["git", "clone", "--depth", "1", "https://github.com/a/b", "/tmp/x"],
        check=True,
        capture_output=True,
    )


def test_dulwich_git_client_clones_via_porcelain() -> None:
    client = DulwichGitClient()

    with patch("dulwich.porcelain.clone") as mock_clone:
        client.clone("https://github.com/a/b", Path("/tmp/x"), depth=1)

    mock_clone.assert_called_once_with(
        "https://github.com/a/b",
        target="/tmp/x",
        depth=1,
    )


def test_get_git_client_returns_system_when_git_on_path() -> None:
    with patch("repos.git_client.shutil.which", return_value="/usr/bin/git"):
        client = get_git_client()

    assert isinstance(client, SystemGitClient)


def test_get_git_client_returns_dulwich_when_git_missing() -> None:
    with patch("repos.git_client.shutil.which", return_value=None):
        client = get_git_client()

    assert isinstance(client, DulwichGitClient)
