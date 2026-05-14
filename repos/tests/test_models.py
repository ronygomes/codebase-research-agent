import pytest
from django.db import IntegrityError

from repos.models import Repository


@pytest.mark.django_db
def test_repository_can_be_created_with_url_and_name() -> None:
    repo = Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )

    assert repo.id is not None
    assert repo.url == "https://github.com/tiangolo/fastapi"
    assert repo.name == "tiangolo/fastapi"


@pytest.mark.django_db
def test_repository_url_must_be_unique() -> None:
    Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )

    with pytest.raises(IntegrityError):
        Repository.objects.create(
            url="https://github.com/tiangolo/fastapi",
            name="tiangolo/fastapi",
        )


@pytest.mark.django_db
def test_repository_sync_and_analyzed_timestamps_default_to_none() -> None:
    repo = Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )

    assert repo.last_synced_at is None
    assert repo.last_analyzed_at is None


def test_repository_str_returns_name_or_falls_back_to_url() -> None:
    with_name = Repository(url="https://github.com/x/y", name="x/y")
    without_name = Repository(url="https://github.com/a/b", name="")

    assert str(with_name) == "x/y"
    assert str(without_name) == "https://github.com/a/b"
