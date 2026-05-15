from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest
from django.utils import timezone

from repos.git_client import GitClient
from repos.models import Repository
from repos.services import ensure_cloned


def _fake_git_client() -> Mock:
    client = Mock(spec=GitClient)

    def fake_clone(url: str, target: Any, depth: int = 1) -> None:
        target.mkdir(parents=True, exist_ok=True)

    client.clone.side_effect = fake_clone
    return client


@pytest.mark.django_db
def test_ensure_cloned_clones_when_target_missing(tmp_path: Any, settings: Any) -> None:
    settings.WORKDIR = tmp_path
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    client = _fake_git_client()

    result = ensure_cloned(repo, client)

    assert result.exists()
    client.clone.assert_called_once()
    repo.refresh_from_db()
    assert repo.last_synced_at is not None
    assert repo.clone_path == str(result)


@pytest.mark.django_db
def test_ensure_cloned_skips_when_within_ttl(tmp_path: Any, settings: Any) -> None:
    settings.WORKDIR = tmp_path
    settings.REPO_SYNC_TTL_HOURS = 3
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    client = _fake_git_client()

    first = ensure_cloned(repo, client)
    second = ensure_cloned(repo, client)

    assert client.clone.call_count == 1
    assert first == second


@pytest.mark.django_db
def test_ensure_cloned_reclones_when_stale(tmp_path: Any, settings: Any) -> None:
    settings.WORKDIR = tmp_path
    settings.REPO_SYNC_TTL_HOURS = 3
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    client = _fake_git_client()

    ensure_cloned(repo, client)
    repo.last_synced_at = timezone.now() - timedelta(hours=4)
    repo.save(update_fields=["last_synced_at"])

    ensure_cloned(repo, client)

    assert client.clone.call_count == 2
