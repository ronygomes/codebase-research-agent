from typing import Any

import pytest
from rest_framework.test import APIClient

from repos.models import Repository


@pytest.fixture(autouse=True)
def _eager_celery(settings: Any) -> None:
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def repository(db: Any) -> Repository:
    return Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )
