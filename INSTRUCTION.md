# Instruction

# Setup Python

## Using brew

```shell
brew install python@3.12
python3.12 -m venv .venv
```

## Using pyenv

```shell
brew install pyenv

# Update shell profile (e.g. ~/.zshrc):
#   export PYENV_ROOT="$HOME/.pyenv"
#   eval "$(pyenv init -)"

pyenv install 3.12.0
pyenv local 3.12.0 # pyenv uses .python-version file
```

# Install/Update Dependencies

After each change in `pyprotject.toml` update dependencies.

```shell
pip-compile pyproject.toml -o requirements.lock
pip-compile pyproject.toml --extra dev -o requirements-dev.lock

# 3. Install dev deps (includes everything for testing)
pip-sync requirements-dev.lock
```

# Django Sanity-check and Migration

```shell
python manage.py check       # System check for issues identification
python manage.py migrate     # Applies Django's built-in auth/contenttypes migrations
```

# Django Generate Migration

After writing model use following code to generate migration.

```shell
# Create repos/migrations/0001_initial.py and repos/migrations/__init__.py
python manage.py makemigrations repos

# Inspect the generated SQL (Optional)
python manage.py sqlmigrate repos 0001

# Apply the migration
python manage.py migrate
```

# Test

```shell
pytest research/        # test only research module
pytest                  # test all modules configured in conftest.py
```


# Remove all Data

```shell

# Check records count
python manage.py shell -c "
from research.models import ResearchSession
from repos.models import Repository
print('Repos:', Repository.objects.count())
print('Sessions:', ResearchSession.objects.count())
"

python manage.py shell -c "
from research.models import Finding, ToolCall, ResearchSession
from repos.models import Repository
Finding.objects.all().delete()
ToolCall.objects.all().delete()
ResearchSession.objects.all().delete()
Repository.objects.all().delete()
print('Removed!')
"
```
