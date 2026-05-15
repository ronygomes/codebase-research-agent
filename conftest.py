from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from repos.models import Repository


@pytest.fixture(autouse=True)
def _eager_celery(settings: Any) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture(autouse=True)
def mock_ensure_cloned() -> Iterator[Any]:
    with patch("research.tasks.ensure_cloned") as mock:
        yield mock


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def repository(db: Any) -> Repository:
    return Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )
