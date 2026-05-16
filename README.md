# Codebase Research Agent

An AI agent that answers technical questions about a GitHub repository by exploring its source code. Built using Django, Celery and LLM provider Google Gemini.

## Setup LLM

This project works with `Gemini` and `Ollama` LLM Provider but configuration is require.

### Gemini API Key

Create a Gemini API Key using following steps

1. Go to https://aistudio.google.com/
2. Sign in with a Google account
3. Click "Get API key" -> "Create API key"
4. Paste into .env file as GEMINI_API_KEY

### Ollama

**Note:** Without dedicated GPU Ollama performs fairly slow (tested on mac).

```shell
brew install ollama
brew services start ollama

ollama pull qwen2.5:7b   # 4.7 GB download
ollama serve

curl http://localhost:11434/api/tags
```

## Project Structure

```
codebase-research-agent/
├── config/           # Django project (settings, urls, celery)
├── llm/              # LLMProvider ABC and Gemini/Ollama implementations
├── tools/            # Agent tools for code exploration and DB interaction
├── agent/            # Agent loop and system prompts
├── repos/            # Repository model and git clone utility
├── research/         # Sessions, REST API, Celery tasks
├── fixtures/         # Sample data (`sample_data.json`)
└── workdir/          # Local git clone cache (gitignored)
```

See **DECISIONS.md** and **ERD.md** for database design and design rationale.

## Configuration

Copy `.env.example` to `.env` and adjust. All env vars in active use:

| Name                            | Description                                                                                                                                       |
| ------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- |
| `DATABASE_URL`                  | Postgres URL, e.g. `postgres://postgres:12345@localhost:5432/research_agent`                                                                      |
| `SECRET_KEY`                    | Django secret key                                                                                                                                 |
| `DEBUG`                         | Django debug mode                                                                                                                                 |
| `ALLOWED_HOSTS`                 | Comma-separated list of allowed Host headers                                                                                                      |
| `LLM_PROVIDER`                  | Which LLM backend — `gemini` (cloud API) or `ollama` (local)                                                                                      |
| `LLM_MODEL`                     | Provider-specific model name. Gemini examples: `gemini-2.5-flash-lite`, `gemini-2.5-flash`. Ollama examples: `qwen2.5:7b`, `qwen2.5:3b`, `llama3.1:8b` |
| `GEMINI_API_KEY`                | Get from https://aistudio.google.com/apikey (required when `LLM_PROVIDER=gemini`)                                                                 |
| `ENABLE_GEMINI_RETRY_BACKOFF`   | Sleep on 429 (Gemini's `retryDelay`) and retry up to 2 times per call                                                                             |
| `CELERY_BROKER_URL`             | Celery's broker (Redis)                                                                                                                           |
| `CELERY_TASK_ALWAYS_EAGER`      | Run tasks synchronously in-process (useful for one-off scripts; tests force this on automatically)                                                |
| `REPO_SYNC_TTL_HOURS`           | Hours before a cached repo clone is deleted and re-cloned                                                                                         |


## Run Project

This project provides `make` target for usability. Run following command to start the server. Refer to **INSTRUCTION.md** for instruction on installing `python` and `venv`


```shell
python --version # tested with python 3.12.13

python -m venv .venv
source .venv/bin/activate

pip install pip-tools
pip-sync requirements-dev.lock

cp .env.example .env  # edit default configurations
make infra
make migrate
make load-fixture     # instant sample data

make web              # terminal 1
make worker           # terminal 2

# terminal 3
curl -X POST http://localhost:8000/api/v1/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"repo_url": "https://github.com/tiangolo/fastapi", "question": "test"}'
```

## API Endpoints

All endpoints live under `/api/v1/`. Quick reference with one-line usage:

| Method | Path | Purpose | One-line `curl` |
|---|---|---|---|
| `POST` | `/sessions/` | Start a research session (returns `202 Accepted` + `polling_url`) | `curl -X POST localhost:8000/api/v1/sessions/ -H 'Content-Type: application/json' -d '{"repo_url":"https://github.com/psf/requests","question":"Where is Session defined?"}'` |
| `GET` | `/sessions/<id>/` | Full session detail incl. `findings[]` and `tool_calls[]` (poll target) | `curl localhost:8000/api/v1/sessions/1/` |
| `GET` | `/sessions/?repo_url=...` | Paginated list of sessions, filterable by repo | `curl 'localhost:8000/api/v1/sessions/?repo_url=https://github.com/psf/requests'` |
| `GET` | `/repos/` | Paginated list of all researched repos (with `session_count`) | `curl localhost:8000/api/v1/repos/` |
| `GET` | `/repos/<id>/` | Single repo detail | `curl localhost:8000/api/v1/repos/1/` |
