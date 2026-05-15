import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class GitClient(ABC):
    @abstractmethod
    def clone(self, url: str, target: Path, depth: int = 1) -> None: ...

    @property
    @abstractmethod
    def backend_name(self) -> str: ...


class SystemGitClient(GitClient):
    def clone(self, url: str, target: Path, depth: int = 1) -> None:
        subprocess.run(
            ["git", "clone", "--depth", str(depth), url, str(target)],
            check=True,
            capture_output=True,
        )

    @property
    def backend_name(self) -> str:
        return "system-git"


class DulwichGitClient(GitClient):
    def clone(self, url: str, target: Path, depth: int = 1) -> None:
        from dulwich import porcelain

        porcelain.clone(url, target=str(target), depth=depth)

    @property
    def backend_name(self) -> str:
        return "dulwich"


def get_git_client() -> GitClient:
    if shutil.which("git"):
        return SystemGitClient()
    return DulwichGitClient()
