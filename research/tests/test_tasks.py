import pytest

from repos.models import Repository
from research.models import ResearchSession
from research.tasks import run_research_session


@pytest.mark.django_db
def test_run_research_session_marks_running_and_records_task_id() -> None:
    repo = Repository.objects.create(url="https://github.com/a/b", name="a/b")
    session = ResearchSession.objects.create(
        repository=repo,
        question="x",
        llm_provider="gemini",
        llm_model="gemini-2.0-flash",
    )

    result = run_research_session.delay(session.id)

    session.refresh_from_db()
    assert session.status == ResearchSession.Status.RUNNING
    assert session.started_at is not None
    assert session.celery_task_id == result.id
