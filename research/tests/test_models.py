import pytest
from django.db import IntegrityError
from django.utils import timezone

from repos.models import Repository
from research.models import Finding, ResearchSession, ToolCall


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


@pytest.mark.django_db
def test_finding_can_be_created_with_required_fields() -> None:
    repo = _make_repo()
    session = _make_session(repo)

    finding = Finding.objects.create(
        session=session,
        file_path="fastapi/dependencies/utils.py",
        note="Core dependency resolution is in solve_dependencies()",
    )

    assert finding.pk is not None
    assert finding.session_id == session.id
    assert finding.line_start is None
    assert finding.line_end is None


@pytest.mark.django_db
def test_deleting_session_cascades_to_findings() -> None:
    repo = _make_repo()
    session = _make_session(repo)
    Finding.objects.create(session=session, file_path="a.py", note="n1")
    Finding.objects.create(session=session, file_path="b.py", note="n2")
    assert Finding.objects.count() == 2

    session.delete()

    assert Finding.objects.count() == 0


def test_finding_str_includes_file_path_and_optional_line_range() -> None:
    no_lines = Finding(file_path="a.py", note="x")
    one_line = Finding(file_path="a.py", line_start=42, note="x")
    range_lines = Finding(file_path="a.py", line_start=42, line_end=89, note="x")

    assert str(no_lines) == "Finding at a.py"
    assert str(one_line) == "Finding at a.py:42"
    assert str(range_lines) == "Finding at a.py:42-89"


def _make_tool_call(session: ResearchSession, sequence: int = 1, **kwargs: object) -> ToolCall:
    now = timezone.now()
    defaults: dict[str, object] = {
        "session": session,
        "sequence": sequence,
        "tool_name": "read_file",
        "arguments": {"path": "main.py"},
        "result_content": "",
        "started_at": now,
        "completed_at": now,
    }
    defaults.update(kwargs)
    return ToolCall.objects.create(**defaults)


@pytest.mark.django_db
def test_tool_call_can_be_created_with_required_fields_and_defaults() -> None:
    repo = _make_repo()
    session = _make_session(repo)

    call = _make_tool_call(session)

    assert call.pk is not None
    assert call.session_id == session.id
    assert call.result_truncated is False
    assert call.is_error is False


@pytest.mark.django_db
def test_tool_call_sequence_is_unique_per_session() -> None:
    repo = _make_repo()
    session = _make_session(repo)
    _make_tool_call(session, sequence=1)

    with pytest.raises(IntegrityError):
        _make_tool_call(session, sequence=1)


@pytest.mark.django_db
def test_tool_call_same_sequence_allowed_across_different_sessions() -> None:
    repo = _make_repo()
    session_a = _make_session(repo, question="A")
    session_b = _make_session(repo, question="B")

    _make_tool_call(session_a, sequence=1)
    _make_tool_call(session_b, sequence=1)

    assert ToolCall.objects.count() == 2


@pytest.mark.django_db
def test_deleting_session_cascades_to_tool_calls() -> None:
    repo = _make_repo()
    session = _make_session(repo)
    _make_tool_call(session, sequence=1)
    _make_tool_call(session, sequence=2)
    assert ToolCall.objects.count() == 2

    session.delete()

    assert ToolCall.objects.count() == 0
