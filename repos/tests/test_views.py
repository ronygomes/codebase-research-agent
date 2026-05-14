import pytest
from rest_framework import status
from rest_framework.test import APIClient

from repos.models import Repository
from research.models import ResearchSession


@pytest.mark.django_db
def test_list_repos_returns_paginated_payload(api_client: APIClient) -> None:
    Repository.objects.create(url="https://github.com/a/b", name="a/b")
    Repository.objects.create(url="https://github.com/c/d", name="c/d")

    response = api_client.get("/api/v1/repos/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 2
    assert len(response.data["results"]) == 2


@pytest.mark.django_db
def test_list_repos_includes_session_count(api_client: APIClient) -> None:
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    ResearchSession.objects.create(
        repository=repo,
        question="q1",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )
    ResearchSession.objects.create(
        repository=repo,
        question="q2",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    response = api_client.get("/api/v1/repos/")

    assert response.data["results"][0]["session_count"] == 2


@pytest.mark.django_db
def test_get_repo_detail_returns_full_fields(api_client: APIClient, repository: Repository) -> None:
    response = api_client.get(f"/api/v1/repos/{repository.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["url"] == repository.url
    assert response.data["name"] == repository.name


@pytest.mark.django_db
def test_get_repo_404_for_unknown_id(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/repos/99999/")

    assert response.status_code == status.HTTP_404_NOT_FOUND
