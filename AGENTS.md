# Repository Guidelines

## Project Structure & Module Organization

This repository is a FastAPI backend. Application code lives in `app/`: `main.py` creates the API, mounts `/uploads`, and registers routers. Keep route definitions in `app/routers/`, business logic in `app/services/`, request/response models in `app/schemas/`, SQLAlchemy models in `app/models/`, database setup in `app/db/`, shared settings/security in `app/core/`, and websocket handlers in `app/websockets/`. Alembic migrations live in `alembic/versions/`. Runtime files are stored under `uploads/` and should not be committed.

## Build, Test, and Development Commands

- `python -m venv venv && source venv/bin/activate`: create and enter a local virtual environment.
- `pip install -r requirements.txt`: install FastAPI, SQLAlchemy, validation, email, and document-processing dependencies.
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`: run the API locally with reload enabled.
- `python app/main.py`: alternate local startup path using the module's `__main__` block.
- `alembic upgrade head`: apply database migrations when Alembic is available in your environment.
- `alembic revision --autogenerate -m "describe_change"`: create a migration after model changes.

## Coding Style & Naming Conventions

Use Python 3 style with 4-space indentation, clear type hints where practical, and small functions that keep routing thin. Name files and modules with `snake_case.py`; use `PascalCase` for Pydantic and SQLAlchemy classes; use `snake_case` for variables, functions, and service helpers. Follow the current layering: routers validate HTTP concerns, services own workflows, schemas define API contracts, and models define persistence. Avoid committing generated files such as `__pycache__/`, `*.pyc`, local virtual environments, `.env`, or uploaded content.

## Testing Guidelines

No test suite is currently present. Add tests under `tests/` when introducing behavior, using names like `test_auth_login.py` or `test_quiz_generation.py`. Prefer FastAPI `TestClient` for endpoint coverage and focused unit tests for service functions. Run tests with `pytest` once added, and cover success paths plus authorization, validation, and database edge cases for changed endpoints.

## Commit & Pull Request Guidelines

Recent commit messages are short and informal, for example `the finall edit_02`. Going forward, use concise imperative messages such as `Add chat file metadata migration` or `Fix quiz session validation`. Pull requests should include a brief summary, changed endpoints or migrations, test results, required environment variables, and screenshots only when API docs or uploaded-file behavior changes visibly.

## Security & Configuration Tips

Configuration is loaded from `.env` through `app/core/config.py`. Set `DATABASE_URL`, `SECRET_KEY`, `SENDGRID_API_KEY`, `FROM_EMAIL`, and `GEMINI_API_KEY` locally as needed. Never commit real secrets, database dumps, virtual environments, or `uploads/` contents.
