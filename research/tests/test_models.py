import pytest

from repos.models import Repository
from research.models import ResearchSession


def _make_repo() -> Repository:
    return Repository.objects.create(
        url="https://github.com/tiangolo/fastapi",
        name="tiangolo/fastapi",
    )


def _make_session(
    repository: Repository,
    question: str = "test question",
    llm_provider: str = "gemini",
    llm_model: str = "gemini-2.0-flash",
) -> ResearchSession:
    return ResearchSession.objects.create(
        repository=repository,
        question=question,
        llm_provider=llm_provider,
        llm_model=llm_model,
    )


@pytest.mark.django_db
def test_session_can_be_created_with_minimum_required_fields() -> None:
    repo = _make_repo()

    session = _make_session(repo)

    assert session.pk is not None
    assert session.repository_id == repo.id


@pytest.mark.django_db
def test_session_status_defaults_to_queued() -> None:
    repo = _make_repo()

    session = _make_session(repo)

    assert session.status == ResearchSession.Status.QUEUED


@pytest.mark.django_db
def test_session_token_counts_and_iteration_count_default_to_zero() -> None:
    repo = _make_repo()

    session = _make_session(repo)

    assert session.input_tokens == 0
    assert session.output_tokens == 0
    assert session.iteration_count == 0


@pytest.mark.django_db
def test_deleting_repository_cascades_to_sessions() -> None:
    repo = _make_repo()
    _make_session(repo, question="Q1")
    _make_session(repo, question="Q2")
    assert ResearchSession.objects.count() == 2

    repo.delete()

    assert ResearchSession.objects.count() == 0
