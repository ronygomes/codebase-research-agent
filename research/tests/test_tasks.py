from typing import Any

import pytest

from repos.models import Repository
from research.models import ResearchSession
from research.tasks import run_research_session


@pytest.mark.django_db
def test_run_research_session_records_celery_task_id() -> None:
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    session = ResearchSession.objects.create(
        repository=repo,
        question="x",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    result = run_research_session.delay(session.id)

    session.refresh_from_db()
    assert session.celery_task_id == result.id


@pytest.mark.django_db
def test_run_research_session_clones_repo_and_invokes_agent(
    mock_ensure_cloned: Any, mock_agent_in_task: Any
) -> None:
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    session = ResearchSession.objects.create(
        repository=repo,
        question="x",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    run_research_session.delay(session.id)

    mock_ensure_cloned.assert_called_once()
    mock_agent_in_task.assert_called_once()
    mock_agent_in_task.return_value.run.assert_called_once()
