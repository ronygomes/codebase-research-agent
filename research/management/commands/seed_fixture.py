"""Hand-crafted fixture data — no LLM calls.

Used when live `seed_research` is impractical due to API quotas or local
LLM inference speed. The data references real files in real repositories
and is structured to demonstrate the same features (cross-session reuse,
varied tool calls, multiple termination reasons) that a live seed would
produce.
"""

import json
from datetime import timedelta
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from repos.models import Repository
from research.models import Finding, ResearchSession, ToolCall


_PROVIDER = "ollama"
_MODEL = "qwen2.5:7b"


REPOS: list[dict[str, Any]] = [
    {
        "url": "https://github.com/psf/requests",
        "name": "psf/requests",
        "clone_path": "workdir/repos/a1b2c3d4e5f60001",
    },
    {
        "url": "https://github.com/pallets/flask",
        "name": "pallets/flask",
        "clone_path": "workdir/repos/a1b2c3d4e5f60002",
    },
    {
        "url": "https://github.com/tiangolo/fastapi",
        "name": "tiangolo/fastapi",
        "clone_path": "workdir/repos/a1b2c3d4e5f60003",
    },
]


SESSIONS: list[dict[str, Any]] = [
    {
        "repo_url": "https://github.com/psf/requests",
        "question": "Where is the Session class defined and what does it manage?",
        "answer": (
            "The `Session` class is defined in `src/requests/sessions.py:325`. "
            "It manages persistent settings across HTTP requests: cookies (`self.cookies`), "
            "headers (`self.headers`), authentication (`self.auth`), proxies, hooks, "
            "redirect policy, and connection pooling via mounted `HTTPAdapter` instances "
            "(`self.adapters`). All `requests.get/post/...` top-level calls instantiate "
            "a one-off `Session` internally."
        ),
        "status": "completed",
        "termination_reason": "completed",
        "iteration_count": 8,
        "input_tokens": 4523,
        "output_tokens": 412,
        "minutes_ago": 120,
        "duration_seconds": 47,
        "tool_calls": [
            {
                "tool_name": "list_files",
                "arguments": {"path": "/"},
                "result_content": json.dumps({
                    "path": "/",
                    "entries": [
                        {"name": "docs", "type": "dir"},
                        {"name": "src", "type": "dir"},
                        {"name": "tests", "type": "dir"},
                        {"name": "AUTHORS.rst", "type": "file", "size_bytes": 14233},
                        {"name": "HISTORY.md", "type": "file", "size_bytes": 56892},
                        {"name": "README.md", "type": "file", "size_bytes": 4521},
                        {"name": "pyproject.toml", "type": "file", "size_bytes": 2843},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "list_files",
                "arguments": {"path": "src/requests"},
                "result_content": json.dumps({
                    "path": "src/requests",
                    "entries": [
                        {"name": "__init__.py", "type": "file", "size_bytes": 5012},
                        {"name": "adapters.py", "type": "file", "size_bytes": 24891},
                        {"name": "api.py", "type": "file", "size_bytes": 6537},
                        {"name": "auth.py", "type": "file", "size_bytes": 10421},
                        {"name": "cookies.py", "type": "file", "size_bytes": 18234},
                        {"name": "models.py", "type": "file", "size_bytes": 32156},
                        {"name": "sessions.py", "type": "file", "size_bytes": 30789},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "search_code",
                "arguments": {"query": "class Session", "file_pattern": "**/*.py"},
                "result_content": json.dumps({
                    "query": "class Session",
                    "match_count": 1,
                    "truncated": False,
                    "matches": [
                        {
                            "file": "src/requests/sessions.py",
                            "line": 325,
                            "content": "class Session(SessionRedirectMixin):",
                        }
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "read_file",
                "arguments": {"path": "src/requests/sessions.py", "line_start": 325, "line_end": 420},
                "result_content": (
                    "File: src/requests/sessions.py (lines 325-420 of 825 total)\n\n"
                    " 325| class Session(SessionRedirectMixin):\n"
                    " 326|     \"\"\"A Requests session.\n"
                    " 327|\n"
                    " 328|     Provides cookie persistence, connection-pooling, and configuration.\n"
                    " 329|     \"\"\"\n"
                    " ...\n"
                    " 360|     def __init__(self):\n"
                    " 361|         self.headers = default_headers()\n"
                    " 362|         self.auth = None\n"
                    " 363|         self.proxies = {}\n"
                    " 364|         self.hooks = default_hooks()\n"
                    " 365|         self.params = {}\n"
                    " 366|         self.stream = False\n"
                    " 367|         self.verify = True\n"
                    " 368|         self.cert = None\n"
                    " 369|         self.max_redirects = DEFAULT_REDIRECT_LIMIT\n"
                    " 370|         self.trust_env = True\n"
                    " 371|         self.cookies = cookiejar_from_dict({})\n"
                    " 372|         self.adapters = OrderedDict()\n"
                    " 373|         self.mount('https://', HTTPAdapter())\n"
                    " 374|         self.mount('http://', HTTPAdapter())\n"
                ),
                "is_error": False,
            },
            {
                "tool_name": "save_finding",
                "arguments": {
                    "file_path": "src/requests/sessions.py",
                    "note": (
                        "Session class is at line 325. Constructor initializes: headers, auth, "
                        "proxies, hooks, params, cookies, adapters (HTTPAdapter for http and https)."
                    ),
                    "line_start": 325,
                    "line_end": 374,
                },
                "result_content": json.dumps({"saved": True, "finding_id": "_PLACEHOLDER_", "message": "saved"}),
                "is_error": False,
            },
        ],
        "findings": [
            {
                "file_path": "src/requests/sessions.py",
                "line_start": 325,
                "line_end": 374,
                "note": (
                    "Session class is at line 325. Constructor initializes: headers, auth, "
                    "proxies, hooks, params, cookies, adapters (HTTPAdapter for http and https)."
                ),
            },
            {
                "file_path": "src/requests/sessions.py",
                "line_start": 371,
                "line_end": 371,
                "note": "Cookies are managed via self.cookies (a cookielib jar).",
            },
            {
                "file_path": "src/requests/sessions.py",
                "line_start": 372,
                "line_end": 374,
                "note": "Connection pooling via mounted HTTPAdapter instances on self.adapters.",
            },
        ],
    },
    {
        "repo_url": "https://github.com/psf/requests",
        "question": "How does the retry mechanism work in requests?",
        "answer": (
            "Retry behavior is controlled by `HTTPAdapter` in `src/requests/adapters.py`. "
            "The adapter accepts a `max_retries` argument (int or `urllib3.util.Retry` "
            "instance). Internally, requests delegates to `urllib3`'s `Retry` class which "
            "handles backoff, allowed methods, and status forcelist. To customize, mount a "
            "configured `HTTPAdapter(max_retries=Retry(...))` on a Session. Note: by default, "
            "`max_retries=0` — no retries unless explicitly configured."
        ),
        "status": "completed",
        "termination_reason": "completed",
        "iteration_count": 7,
        "input_tokens": 6890,
        "output_tokens": 521,
        "minutes_ago": 95,
        "duration_seconds": 52,
        "tool_calls": [
            {
                "tool_name": "get_previous_findings",
                "arguments": {"repo_url": "https://github.com/psf/requests"},
                "result_content": json.dumps({
                    "repo_url": "https://github.com/psf/requests",
                    "finding_count": 3,
                    "findings": [
                        {
                            "file_path": "src/requests/sessions.py",
                            "line_start": 372,
                            "line_end": 374,
                            "note": "Connection pooling via mounted HTTPAdapter instances on self.adapters.",
                            "from_session": "Question: Where is the Session class defined...",
                        }
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "search_code",
                "arguments": {"query": "max_retries|Retry"},
                "result_content": json.dumps({
                    "query": "max_retries|Retry",
                    "match_count": 12,
                    "truncated": False,
                    "matches": [
                        {"file": "src/requests/adapters.py", "line": 73, "content": "from urllib3.util.retry import Retry"},
                        {"file": "src/requests/adapters.py", "line": 142, "content": "    def __init__(self, pool_connections=DEFAULT_POOLSIZE, pool_maxsize=DEFAULT_POOLSIZE, max_retries=DEFAULT_RETRIES, pool_block=DEFAULT_POOLBLOCK):"},
                        {"file": "src/requests/adapters.py", "line": 152, "content": "        if max_retries == DEFAULT_RETRIES:"},
                        {"file": "src/requests/adapters.py", "line": 153, "content": "            self.max_retries = Retry(0, read=False)"},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "read_file",
                "arguments": {"path": "src/requests/adapters.py", "line_start": 140, "line_end": 175},
                "result_content": (
                    "File: src/requests/adapters.py (lines 140-175 of 720 total)\n\n"
                    " 140| class HTTPAdapter(BaseAdapter):\n"
                    " 141|     \n"
                    " 142|     def __init__(self, pool_connections=DEFAULT_POOLSIZE, pool_maxsize=DEFAULT_POOLSIZE,\n"
                    " 143|                  max_retries=DEFAULT_RETRIES, pool_block=DEFAULT_POOLBLOCK):\n"
                    " ...\n"
                    " 152|         if max_retries == DEFAULT_RETRIES:\n"
                    " 153|             self.max_retries = Retry(0, read=False)\n"
                    " 154|         else:\n"
                    " 155|             self.max_retries = Retry.from_int(max_retries)\n"
                ),
                "is_error": False,
            },
            {
                "tool_name": "save_finding",
                "arguments": {
                    "file_path": "src/requests/adapters.py",
                    "note": "HTTPAdapter accepts max_retries (int or urllib3 Retry). Default is Retry(0, read=False) - no retries.",
                    "line_start": 142,
                    "line_end": 155,
                },
                "result_content": json.dumps({"saved": True, "finding_id": "_PLACEHOLDER_", "message": "saved"}),
                "is_error": False,
            },
        ],
        "findings": [
            {
                "file_path": "src/requests/adapters.py",
                "line_start": 142,
                "line_end": 155,
                "note": "HTTPAdapter accepts max_retries (int or urllib3 Retry). Default is Retry(0, read=False) - no retries.",
            },
            {
                "file_path": "src/requests/adapters.py",
                "line_start": 73,
                "line_end": 73,
                "note": "Retry logic delegates to urllib3.util.retry.Retry — see Retry class for backoff/allowed_methods/status_forcelist.",
            },
        ],
    },
    {
        "repo_url": "https://github.com/pallets/flask",
        "question": "Where is the routing decorator implemented?",
        "answer": (
            "Flask's `@app.route()` decorator is defined on the `Scaffold` base class in "
            "`src/flask/sansio/scaffold.py` (around line 60). `Flask` (in `src/flask/app.py`) "
            "inherits from `Scaffold` and exposes `route()` as `@app.route(rule, **options)`. "
            "Internally, `route()` returns a decorator that calls `self.add_url_rule(rule, "
            "endpoint, view_func, **options)`, which delegates to the Werkzeug `Map` underlying "
            "`self.url_map`."
        ),
        "status": "completed",
        "termination_reason": "completed",
        "iteration_count": 6,
        "input_tokens": 5210,
        "output_tokens": 384,
        "minutes_ago": 60,
        "duration_seconds": 41,
        "tool_calls": [
            {
                "tool_name": "list_files",
                "arguments": {"path": "src/flask"},
                "result_content": json.dumps({
                    "path": "src/flask",
                    "entries": [
                        {"name": "sansio", "type": "dir"},
                        {"name": "__init__.py", "type": "file", "size_bytes": 1234},
                        {"name": "app.py", "type": "file", "size_bytes": 65432},
                        {"name": "blueprints.py", "type": "file", "size_bytes": 4521},
                        {"name": "ctx.py", "type": "file", "size_bytes": 14523},
                        {"name": "wrappers.py", "type": "file", "size_bytes": 6234},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "search_code",
                "arguments": {"query": "def route", "file_pattern": "src/flask/**/*.py"},
                "result_content": json.dumps({
                    "query": "def route",
                    "match_count": 3,
                    "truncated": False,
                    "matches": [
                        {"file": "src/flask/sansio/scaffold.py", "line": 60, "content": "    def route(self, rule: str, **options: t.Any) -> ft.RouteCallable:"},
                        {"file": "src/flask/sansio/blueprints.py", "line": 187, "content": "    def route(self, rule: str, **options: t.Any) -> ft.RouteCallable:"},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "read_file",
                "arguments": {"path": "src/flask/sansio/scaffold.py", "line_start": 55, "line_end": 95},
                "result_content": (
                    "File: src/flask/sansio/scaffold.py (lines 55-95 of 712 total)\n\n"
                    "  55|     def route(\n"
                    "  56|         self, rule: str, **options: t.Any\n"
                    "  57|     ) -> ft.RouteCallable:\n"
                    "  58|         \"\"\"Decorator to register a view function for the given URL rule.\"\"\"\n"
                    "  59|\n"
                    "  60|         def decorator(f: T_route) -> T_route:\n"
                    "  61|             endpoint = options.pop('endpoint', None)\n"
                    "  62|             self.add_url_rule(rule, endpoint, f, **options)\n"
                    "  63|             return f\n"
                    "  64|\n"
                    "  65|         return decorator\n"
                ),
                "is_error": False,
            },
            {
                "tool_name": "save_finding",
                "arguments": {
                    "file_path": "src/flask/sansio/scaffold.py",
                    "note": "route() decorator at line 60. Inner decorator pops 'endpoint' option, calls self.add_url_rule(rule, endpoint, f, **options).",
                    "line_start": 55,
                    "line_end": 65,
                },
                "result_content": json.dumps({"saved": True, "finding_id": "_PLACEHOLDER_", "message": "saved"}),
                "is_error": False,
            },
        ],
        "findings": [
            {
                "file_path": "src/flask/sansio/scaffold.py",
                "line_start": 55,
                "line_end": 65,
                "note": "route() decorator at line 60. Inner decorator pops 'endpoint' option, calls self.add_url_rule(rule, endpoint, f, **options).",
            },
        ],
    },
    {
        "repo_url": "https://github.com/tiangolo/fastapi",
        "question": "Where is the FastAPI class defined?",
        "answer": (
            "The `FastAPI` class is defined in `fastapi/applications.py:48`. It inherits "
            "from Starlette's `Starlette` class and adds OpenAPI generation, dependency "
            "injection, automatic request validation via Pydantic, and a `Router` for "
            "path operations."
        ),
        "status": "completed",
        "termination_reason": "max_iterations",
        "iteration_count": 20,
        "input_tokens": 28432,
        "output_tokens": 1289,
        "minutes_ago": 30,
        "duration_seconds": 234,
        "tool_calls": [
            {
                "tool_name": "list_files",
                "arguments": {"path": "/"},
                "result_content": json.dumps({
                    "path": "/",
                    "entries": [
                        {"name": "fastapi", "type": "dir"},
                        {"name": "tests", "type": "dir"},
                        {"name": "docs", "type": "dir"},
                        {"name": "README.md", "type": "file", "size_bytes": 28432},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "search_code",
                "arguments": {"query": "class FastAPI"},
                "result_content": json.dumps({
                    "query": "class FastAPI",
                    "match_count": 1,
                    "truncated": False,
                    "matches": [
                        {"file": "fastapi/applications.py", "line": 48, "content": "class FastAPI(Starlette):"},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "read_file",
                "arguments": {"path": "fastapi/applications.py", "line_start": 48, "line_end": 110},
                "result_content": (
                    "File: fastapi/applications.py (lines 48-110 of 1234 total)\n\n"
                    "  48| class FastAPI(Starlette):\n"
                    "  49|     def __init__(\n"
                    "  50|         self,\n"
                    "  51|         *,\n"
                    "  52|         debug: bool = False,\n"
                    "  53|         routes: Optional[List[BaseRoute]] = None,\n"
                    "  54|         title: str = 'FastAPI',\n"
                    "  55|         description: str = '',\n"
                    "  56|         version: str = '0.1.0',\n"
                    "  57|         openapi_url: Optional[str] = '/openapi.json',\n"
                ),
                "is_error": False,
            },
            {
                "tool_name": "save_finding",
                "arguments": {
                    "file_path": "fastapi/applications.py",
                    "note": "FastAPI class defined at line 48, inherits from Starlette.",
                    "line_start": 48,
                    "line_end": 110,
                },
                "result_content": json.dumps({"saved": True, "finding_id": "_PLACEHOLDER_", "message": "saved"}),
                "is_error": False,
            },
        ],
        "findings": [
            {
                "file_path": "fastapi/applications.py",
                "line_start": 48,
                "line_end": 110,
                "note": "FastAPI class defined at line 48, inherits from Starlette.",
            },
        ],
    },
    {
        "repo_url": "https://github.com/psf/requests",
        "question": "What HTTP methods does the Session class support?",
        "answer": (
            "The `Session` class (in `src/requests/sessions.py`) provides convenience methods "
            "for all standard HTTP verbs: `get()`, `options()`, `head()`, `post()`, `put()`, "
            "`patch()`, and `delete()`, each implemented as a thin wrapper around `request()` "
            "(the unified entry point at line ~520). Method-specific defaults: `head()` sets "
            "`allow_redirects=False`; `get()` and `options()` default to `allow_redirects=True`."
        ),
        "status": "completed",
        "termination_reason": "completed",
        "iteration_count": 5,
        "input_tokens": 7621,
        "output_tokens": 487,
        "minutes_ago": 10,
        "duration_seconds": 38,
        "tool_calls": [
            {
                "tool_name": "get_previous_findings",
                "arguments": {"repo_url": "https://github.com/psf/requests"},
                "result_content": json.dumps({
                    "repo_url": "https://github.com/psf/requests",
                    "finding_count": 5,
                    "findings": [
                        {
                            "file_path": "src/requests/sessions.py",
                            "line_start": 325,
                            "line_end": 374,
                            "note": "Session class constructor — initializes headers, auth, cookies, adapters",
                            "from_session": "Question: Where is the Session class defined...",
                        },
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "search_code",
                "arguments": {"query": "def (get|post|put|delete|head|patch|options)", "file_pattern": "src/requests/sessions.py"},
                "result_content": json.dumps({
                    "query": "def (get|post|put|delete|head|patch|options)",
                    "match_count": 7,
                    "truncated": False,
                    "matches": [
                        {"file": "src/requests/sessions.py", "line": 600, "content": "    def get(self, url, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 612, "content": "    def options(self, url, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 624, "content": "    def head(self, url, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 638, "content": "    def post(self, url, data=None, json=None, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 653, "content": "    def put(self, url, data=None, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 666, "content": "    def patch(self, url, data=None, **kwargs):"},
                        {"file": "src/requests/sessions.py", "line": 679, "content": "    def delete(self, url, **kwargs):"},
                    ],
                }),
                "is_error": False,
            },
            {
                "tool_name": "save_finding",
                "arguments": {
                    "file_path": "src/requests/sessions.py",
                    "note": "Session has 7 HTTP method shortcuts (get/options/head/post/put/patch/delete) at lines 600-690, all delegating to request().",
                    "line_start": 600,
                    "line_end": 690,
                },
                "result_content": json.dumps({"saved": True, "finding_id": "_PLACEHOLDER_", "message": "saved"}),
                "is_error": False,
            },
        ],
        "findings": [
            {
                "file_path": "src/requests/sessions.py",
                "line_start": 600,
                "line_end": 690,
                "note": "Session has 7 HTTP method shortcuts (get/options/head/post/put/patch/delete) at lines 600-690, all delegating to request().",
            },
        ],
    },
]


class Command(BaseCommand):
    help = (
        "Populate the database with hand-crafted sample data (no LLM calls). "
        "Use this when seed_research is impractical due to API quotas or slow local inference."
    )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        now = timezone.now()

        Finding.objects.all().delete()
        ToolCall.objects.all().delete()
        ResearchSession.objects.all().delete()
        Repository.objects.all().delete()
        self.stdout.write("Existing rows wiped.")

        url_to_repo: dict[str, Repository] = {}
        for repo_spec in REPOS:
            repo = Repository.objects.create(
                url=repo_spec["url"],
                name=repo_spec["name"],
                clone_path=repo_spec["clone_path"],
                last_synced_at=now - timedelta(minutes=180),
            )
            url_to_repo[repo.url] = repo

        for session_spec in SESSIONS:
            created = now - timedelta(minutes=session_spec["minutes_ago"])
            duration = timedelta(seconds=session_spec["duration_seconds"])
            session = ResearchSession.objects.create(
                repository=url_to_repo[session_spec["repo_url"]],
                question=session_spec["question"],
                answer=session_spec["answer"],
                status=session_spec["status"],
                termination_reason=session_spec["termination_reason"],
                llm_provider=_PROVIDER,
                llm_model=_MODEL,
                input_tokens=session_spec["input_tokens"],
                output_tokens=session_spec["output_tokens"],
                iteration_count=session_spec["iteration_count"],
                created_at=created,
                started_at=created + timedelta(seconds=1),
                completed_at=created + duration,
            )
            ResearchSession.objects.filter(pk=session.pk).update(
                created_at=created,
                started_at=created + timedelta(seconds=1),
                completed_at=created + duration,
            )

            for index, call_spec in enumerate(session_spec["tool_calls"], start=1):
                started_at = created + timedelta(seconds=2 + index * 3)
                completed_at = started_at + timedelta(milliseconds=500)
                ToolCall.objects.create(
                    session=session,
                    sequence=index,
                    tool_name=call_spec["tool_name"],
                    arguments=call_spec["arguments"],
                    result_content=call_spec["result_content"],
                    result_truncated=False,
                    is_error=call_spec["is_error"],
                    started_at=started_at,
                    completed_at=completed_at,
                )

            for finding_spec in session_spec["findings"]:
                finding = Finding.objects.create(
                    session=session,
                    file_path=finding_spec["file_path"],
                    line_start=finding_spec["line_start"],
                    line_end=finding_spec["line_end"],
                    note=finding_spec["note"],
                )
                Finding.objects.filter(pk=finding.pk).update(created_at=created + timedelta(seconds=20))

            session.repository.last_analyzed_at = session.completed_at
            session.repository.save(update_fields=["last_analyzed_at"])

            self.stdout.write(self.style.SUCCESS(
                f"  ✓ session {session.id}: {session.status} ({session.termination_reason}) "
                f"on {session.repository.name} | {session.iteration_count} iters"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone: {Repository.objects.count()} repos, "
            f"{ResearchSession.objects.count()} sessions, "
            f"{ToolCall.objects.count()} tool calls, "
            f"{Finding.objects.count()} findings."
        ))
