# Decisions

## Code Architecture

* **Interface-first** via abc.ABC. Three swappable backends sit behind ABCs: LLMProvider (Gemini + Ollama implementations), GitClient (system git primary, pure-Python dulwich fallback auto-selected via shutil.which), and Tool. Each is chosen at runtime through a factory reading settings, so the agent code is backend-agnostic and the actual choice is configuration.

* **Git** TTL-based re-clone, not pull. Each repo is shallow-cloned (--depth 1) once, cached by URL hash under workdir/repos/, and atomically re-cloned after `REPO_SYNC_TTL_HOURS=3` of staleness. Simpler and more robust than incremental pulls on shallow clones.

* **ToolCall, Finding** are two intentionally distinct tables. One is the audit log and the other is the agent's curated knowledge layer. The split enables cross-session reuse. `get_previous_findings(repo_url)` feeds past curated notes back as input to new sessions, making the DB part of the agent's reasoning, not a log dump.

* **Pydantic model** are used for each tool's args. Because auto-generated JSON Schema sent to the LLM which eliminating Python-vs-schema drift.

* **Six layers of guardrails** using max iterations, token budget, wall-clock, duplicate-call detection, per-tool truncation, graceful fallback — defence in depth, with termination_reason persisted for telemetry.

* **Async via Celery and Redis** becuase 5-minute sessions don't fit in a sync HTTP request. POST returns 202, a worker runs the agent, clients poll. `CELERY_TASK_ALWAYS_EAGER` provides a synchronous fallback for tests and seed.


## Agent Design Decision

* **Tool set structure:** Every tool inherits from a single Tool(ABC) base class with name, description, args_model and execute method.
    * **Code exploration:** `list_files(path)`, `read_file(path, line_start?, line_end?)`, `search_code(query, file_pattern?)`, `search_code(query, file_pattern?)`
    * **Cross-session memory:** `save_finding(file_path, note, line_start?, line_end?)`, `get_previous_findings(repo_url), list_past_sessions(repo_url)`
    * A ToolRegistry registers tools, exposes get_definitions() for the LLM tool catalog, and dispatch(name, args, ctx) which:
* **Agent stop condition:** There are three termination paths, all observable in the response via the termination_reason field on ResearchSession:
    * **Normal completion:** LLM returns a response with no tool_use blocks (text only). Outcome status=completed, termination_reason=completed, answer saved
    * **Guardrail hit:** Triggers when any limits exceeds. Resolved by one final LLM call with tools=[] (graceful fallback) -> status=completed, termination_reason=max_iterations / max_tokens / timeout / duplicate_calls, best-effort answer saved.
    * **Unhandled exception:** Handles LLM API error, DB error, etc. Outcome status=failed, termination_reason=error, error_message populated, exception re-raised for Celery logging
* **Infinite loop prevention:** The agent uses six independent limit configured in `agent/config.py`, each catching a different failure mode:
    * The most common failure: model never returns text. Default `MAX_AGENT_ITERATIONS = 20`.
    * Many cheap calls that bypass the iteration cap; cost runaway. Default `MAX_TOKENS_PER_SESSION = 100_000`.
    * Network/API hangs that don't increment counters. Default `MAX_SESSION_WALL_CLOCK_SECONDS = 300`.
    * Same (tool_name, sorted_args) called repeatedly — pathological loops. Default `MAX_CONSECUTIVE_DUPLICATE_CALLS = 3`.
    * Ensures agent always returns an answer, never crashes. Graceful fallback using behavior.
    * A single huge tool result blowing the context budget. Default `MAX_TOOL_RESULT_CHARS = 50_000`.

## Database Design

Refer to [ERD.md](./ERD.md) for complete Entity Relationship Diagram.

### Schema Normalization Decision

* `Repository` is a separate table and not denormalized onto every session. Becauses repos are researched many times. Storing URL, name, clone_path once avoids duplication and gives us a single row to update `last_synced_at` after a re-clone.
* `Finding` and `ToolCall` are distinct tables because `ToolCall` is audit log of every invocation and `Finding` is the agent's curated knowledge layer written via save_finding. The separation enables cross-session reuse using get_previous_findings(repo_url). Mixing them in single table would mix two genuinely different concerns.
* No nested data in models. Putting them inside a JSON blob would have killed the telemetry which is essential for this project.
* Coded `Status` and `TerminationReason` as Django `TextChoices`. Because Enum-style validation uses VARCHAR storage in the DB which causes separate lookup overhead.

### Schema Denormalization Decision

* `Token` counts (input_tokens, output_tokens) aggregated on ResearchSession rather than per-LLM-round. Initially considered a separate AgentTurn table holding one row per LLM call but rejected for complexity.
* `ToolCall.arguments` is JSONField because each tool has different argument shapes.
* `ToolCall.result_content` is a plain TextField because `Tool` outputs vary from a 100-char JSON success-marker to 50 KB of file contents.

### Schema NOT Denormalization Decision

* Computed at query time via annotate(Count("findings")) in RepositoryViewSet.get_queryset and ListPastSessionsTool. Caching would require post-save signals or risk staleness. The COUNT is cheap with the indexed foreign key, not worth the complexity.
* repo_url cached on ResearchSession would've saved JOIN.

### Indexes

* `Repository.url (unique → auto-indexed)`: Usage in get_or_create(url=...) in CreateSessionSerializer and _verify_repo_url in the database tools.
* `Repository.last_synced_at (db_index=True)`: Added for batch stale repos to refresh.
* `ResearchSession.status (db_index=True)`: Filter sessions by status in admin/ops; agent reads completed sessions.
* `ResearchSession.status (db_index=True)`: Runs sessions multiple time for a repo.
* `ResearchSession.status (db_index=True)`: List endpoint uses it because shows newest first.
* `ToolCall.tool_name (db_index=True)`: For finding usage count of Tool-usage statistics.
* `ToolCall UNIQUE(session, sequence)`: Preserves order integrity within a session.
* `Finding.file_path (db_index=True)`: For findings files used across sessions.


## Agent-DB interaction

The database is part of the agent's reasoning loop, not a side-effect of it. Three of the seven tools the agent can call are database tools, and one of them (`get_previous_findings`) is specifically designed to feed prior research back into the current session as input. Agent can build based on its own past work.

## Context Management
The codebase being researched is filesystem-mounted, not loaded into context — the agent reads slices of it through tools, and every slice has hard caps:

* `read_file` size is capped at 1 MB without a line range. `read_file` output is Line-numbered text only file.
* `search_code` results returns 50 records with 200 chars/line.
* `list_files` scans one directory at a time. Can't accidentally enumerate too many files.
* `get_file_summary` returns first 30 lines with size, language.
* Agent truncates with `MAX_TOOL_RESULT_CHARS = 50_000`.
* Agent loop is bounded by `MAX_AGENT_ITERATIONS = 20`.
* Token budget is considered with `MAX_TOKENS_PER_SESSION = 100_000`.
