import shutil
from datetime import timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.utils import timezone

from repos.git_client import GitClient
from repos.models import Repository


def _cache_key(url: str) -> str:
    return sha256(url.encode()).hexdigest()[:16]


def _is_fresh(repo: Repository) -> bool:
    if repo.last_synced_at is None:
        return False
    ttl = timedelta(hours=settings.REPO_SYNC_TTL_HOURS)
    return timezone.now() - repo.last_synced_at < ttl


def ensure_cloned(repo: Repository, git_client: GitClient) -> Path:
    repos_dir = Path(settings.WORKDIR) / "repos"
    repos_dir.mkdir(parents=True, exist_ok=True)
    target = repos_dir / _cache_key(repo.url)

    if target.exists() and _is_fresh(repo):
        return target

    temp = repos_dir / f"_clone_{uuid4().hex}"
    git_client.clone(repo.url, temp)

    if target.exists():
        shutil.rmtree(target)
    try:
        temp.rename(target)
    except OSError:
        shutil.rmtree(temp, ignore_errors=True)

    repo.last_synced_at = timezone.now()
    repo.clone_path = str(target)
    repo.save(update_fields=["last_synced_at", "clone_path"])
    return target
