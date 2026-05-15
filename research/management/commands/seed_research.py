import time
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandParser

from agent.core import Agent
from llm.factory import get_llm_provider
from repos.git_client import get_git_client
from repos.models import Repository
from repos.services import ensure_cloned
from research.models import ResearchSession
from tools.factory import build_default_registry


SEED_SPECS: list[tuple[str, str]] = [
    ("https://github.com/psf/requests", "Where is the Session class defined and what does it manage?"),
    ("https://github.com/psf/requests", "How does the retry mechanism work in requests?"),
    ("https://github.com/pallets/flask", "Where is the routing decorator implemented?"),
    ("https://github.com/tiangolo/fastapi", "Where is the FastAPI class defined?"),
    ("https://github.com/psf/requests", "What HTTP methods does the Session class support?"),
]


def _derive_name(url: str) -> str:
    parts = url.removesuffix("/").split("/")
    return f"{parts[-2]}/{parts[-1]}"


class Command(BaseCommand):
    help = "Run the agent against a curated set of repos to populate sample data."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--delay-seconds",
            type=int,
            default=0,
            help="Seconds to sleep between sessions (helps with strict LLM rate limits).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        delay = int(options["delay_seconds"])

        for index, (url, question) in enumerate(SEED_SPECS):
            if index > 0 and delay > 0:
                self.stdout.write(f"\n  ⏸  sleeping {delay}s before next session...")
                time.sleep(delay)

            normalized = url.removesuffix("/")
            self.stdout.write(self.style.MIGRATE_HEADING(f"\n→ {normalized}"))
            self.stdout.write(f"  Question: {question}")

            repository, _ = Repository.objects.get_or_create(
                url=normalized,
                defaults={"name": _derive_name(normalized)},
            )
            session = ResearchSession.objects.create(
                repository=repository,
                question=question,
                llm_provider=settings.LLM_PROVIDER,
                llm_model=settings.LLM_MODEL,
            )

            try:
                git_client = get_git_client()
                repo_path = ensure_cloned(session.repository, git_client)
                Agent(
                    session=session,
                    llm_provider=get_llm_provider(),
                    tool_registry=build_default_registry(),
                    repo_path=repo_path,
                ).run()
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ Session {session.id} crashed: {e}"))
                continue

            session.refresh_from_db()
            total_tokens = session.input_tokens + session.output_tokens
            self.stdout.write(self.style.SUCCESS(
                f"  ✓ session {session.id}: {session.status} "
                f"({session.termination_reason}) | "
                f"{session.iteration_count} iters | "
                f"{total_tokens} tokens"
            ))
