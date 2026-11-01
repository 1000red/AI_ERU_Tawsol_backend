# ERU Tawasol Backend

FastAPI backend for a university community platform that connects students, teaching assistants, doctors, and admins. It provides authentication, user profile management, course materials, announcements, assignments, real-time chat, support contact, and AI-assisted quiz generation from uploaded course files.

## Features

- JWT-based login, password change, OTP verification, and password reset.
- User profile endpoints for the authenticated user.
- Course material lookup for students and teachers.
- Content management for announcements, files, and assignments.
- Real-time chat with WebSocket presence, delivery/seen status, pinned conversations, voice uploads, and file uploads.
- Announcement WebSocket notifications.
- Quiz generation and evaluation for supported course materials: PDF, PPTX, and DOCX.
- Static file serving from `/uploads`.

## Tech Stack

- Python 3.12+
- FastAPI and Uvicorn
- SQLAlchemy
- Alembic migrations
- Pydantic settings and schemas
- PostgreSQL
- SendGrid for support/password email flows
- Google Gemini API for quiz generation

## Project Structure

```text
app/
  core/          configuration, security, dependencies
  db/            SQLAlchemy engine/session and base metadata
  models/        database models
  routers/       HTTP and WebSocket route modules
  schemas/       Pydantic request/response models
  services/      business logic
  utils/         email and helper utilities
  websockets/    WebSocket managers
alembic/         database migration environment and versions
uploads/         runtime uploaded files, ignored by git
```

## Getting Started

Clone the repository and create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
APP_NAME="ERU Tawasol"
APP_VERSION="2.0.0"
DEBUG=false
DATABASE_URL="postgresql://postgres:password@localhost:5432/eru_tawasol"
SECRET_KEY="replace-with-a-long-random-secret"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=1440
RESET_TOKEN_EXPIRE_MINUTES=5
SENDGRID_API_KEY=""
FROM_EMAIL="noreply@eru-tawasol.com"
OTP_EXPIRE_MINUTES=10
GEMINI_API_KEY=""
```

Make sure PostgreSQL is running and the database in `DATABASE_URL` exists.

Apply migrations:

```bash
alembic upgrade head
```

Run the API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open the interactive API docs at:

```text
http://localhost:8000/docs
```

## API Areas

- `GET /` and `GET /health`: service status.
- `/auth`: login, logout, forgot password, OTP verification, reset password.
- `/users`: authenticated profile and password updates.
- `/materials`: student and teacher material listings.
- `/announcements`: announcements, recipients, unread counts, and notification WebSocket.
- `/files`: material file upload and management.
- `/assignments`: assignment listing and management.
- `/chat`: chat history, search, uploads, message edits/deletes, presence, and chat WebSocket.
- `/contact`: authenticated support/contact form.
- `/quiz`: quiz generation and answer evaluation.

## Development Notes

- Keep route handlers thin; put business workflows in `app/services`.
- Add database changes as Alembic revisions under `alembic/versions`.
- Do not commit `.env`, virtual environments, `__pycache__`, `*.pyc`, or uploaded files.
- The app creates upload directories on startup: `uploads/materials`, `uploads/content`, `uploads/voice`, and `uploads/files`.
