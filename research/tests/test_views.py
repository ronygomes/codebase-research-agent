from unittest.mock import patch

import pytest
from django.conf import settings
from rest_framework import status
from rest_framework.test import APIClient

from repos.models import Repository
from research.models import ResearchSession


@pytest.mark.django_db
def test_post_session_creates_queued_session_and_enqueues_task(api_client: APIClient) -> None:
    with patch("research.views.run_research_session.delay") as mock_delay:
        response = api_client.post(
            "/api/v1/sessions/",
            {
                "repo_url": "https://github.com/tiangolo/fastapi",
                "question": "How does dependency injection work?",
            },
            format="json",
        )

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.data["status"] == "queued"
    assert response.data["question"] == "How does dependency injection work?"
    assert response.data["polling_url"] == f"/api/v1/sessions/{response.data['id']}/"

    session = ResearchSession.objects.get(id=response.data["id"])
    assert session.status == ResearchSession.Status.QUEUED
    assert session.llm_provider == settings.LLM_PROVIDER
    assert session.llm_model == settings.LLM_MODEL
    mock_delay.assert_called_once_with(session.id)


@pytest.mark.django_db
def test_post_session_creates_repository_on_first_use(api_client: APIClient) -> None:
    assert Repository.objects.count() == 0

    api_client.post(
        "/api/v1/sessions/",
        {"repo_url": "https://github.com/tiangolo/fastapi", "question": "test"},
        format="json",
    )

    assert Repository.objects.count() == 1
    repo = Repository.objects.get()
    assert repo.url == "https://github.com/tiangolo/fastapi"
    assert repo.name == "tiangolo/fastapi"


@pytest.mark.django_db
def test_post_session_normalizes_trailing_slash(api_client: APIClient) -> None:
    api_client.post(
        "/api/v1/sessions/",
        {"repo_url": "https://github.com/tiangolo/fastapi/", "question": "x"},
        format="json",
    )
    api_client.post(
        "/api/v1/sessions/",
        {"repo_url": "https://github.com/tiangolo/fastapi", "question": "x"},
        format="json",
    )

    assert Repository.objects.count() == 1


@pytest.mark.django_db
def test_post_session_rejects_invalid_repo_url(api_client: APIClient) -> None:
    response = api_client.post(
        "/api/v1/sessions/",
        {"repo_url": "not-a-url", "question": "x"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "repo_url" in response.data


@pytest.mark.django_db
def test_post_session_rejects_blank_question(api_client: APIClient) -> None:
    response = api_client.post(
        "/api/v1/sessions/",
        {"repo_url": "https://github.com/tiangolo/fastapi", "question": ""},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "question" in response.data


@pytest.mark.django_db
def test_get_session_returns_detail_with_nested_relations(
    api_client: APIClient, repository: Repository
) -> None:
    session = ResearchSession.objects.create(
        repository=repository,
        question="test",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    response = api_client.get(f"/api/v1/sessions/{session.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == session.id
    assert response.data["question"] == "test"
    assert response.data["repository"]["url"] == repository.url
    assert response.data["findings"] == []
    assert response.data["tool_calls"] == []


@pytest.mark.django_db
def test_get_session_404_for_unknown_id(api_client: APIClient) -> None:
    response = api_client.get("/api/v1/sessions/99999/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_list_sessions_filters_by_repo_url(api_client: APIClient) -> None:
    repo_a = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    repo_b = Repository.objects.create(url="https://github.com/c/d", name="c/d")
    ResearchSession.objects.create(
        repository=repo_a,
        question="q1",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )
    ResearchSession.objects.create(
        repository=repo_b,
        question="q2",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    response = api_client.get("/api/v1/sessions/?repo_url=https://github.com/a/b")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["question"] == "q1"
