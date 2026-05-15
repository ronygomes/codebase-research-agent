from pathlib import Path
from string import Template

from research.models import ResearchSession

_PROMPTS_DIR = Path(__file__).parent

SYSTEM_PROMPT: str = (_PROMPTS_DIR / "system.md").read_text(encoding="utf-8")

_INITIAL_TEMPLATE = Template(
    (_PROMPTS_DIR / "user_initial.md").read_text(encoding="utf-8")
)

FALLBACK_USER_MESSAGE: str = (
    _PROMPTS_DIR / "user_fallback.md"
).read_text(encoding="utf-8")


def build_first_user_message(session: ResearchSession) -> str:
    past_count = (
        ResearchSession.objects.filter(
            repository=session.repository,
            status=ResearchSession.Status.COMPLETED,
        )
        .exclude(id=session.id)
        .count()
    )

    if past_count > 0:
        hint = (
            f"\n\nNote: This repository has {past_count} prior completed "
            "research session(s). Consider calling get_previous_findings "
            "before exploring from scratch."
        )
    else:
        hint = ""

    return _INITIAL_TEMPLATE.substitute(
        question=session.question,
        repo_url=session.repository.url,
        past_findings_hint=hint,
    )
