# Project Context: LegalBackend API

## Core Goal
Building a minimal, "production-adjacent" REST API. This is a first-time implementation of a database-driven API, so keep the code clean, readable, and standard. Avoid "clever" abstractions in favor of explicit, maintainable patterns.

## Tech Stack
- **Framework:** FastAPI (Python)
- **ORM:** SQLAlchemy 2.0 (Sync/Blocking)
- **Migrations:** Alembic
- **Database:** PostgreSQL (Supabase)
- **Deployment:** Heroku
- **Validation/Config:** Pydantic v2 & Pydantic-Settings

## Architectural Principles
1. **Lightweight over Complex:** Use a flat structure where possible. Don't over-engineer the service layer unless logic becomes heavy.
2. **Production Readiness:** - Use Pydantic for all Request/Response schemas.
   - Every DB change must go through an Alembic migration.
   - Connection pooling must be resilient (use `pool_pre_ping=True`).
3. **Heroku Compatibility:** - Environment variables are the source of truth.
   - Database URLs must be sanitized (handle `postgres://` vs `postgresql+psycopg://`).

## Database Workflow (Crucial)
- **Models:** Defined in `app/models/`.
- **Registration:** All models must be imported in `app/models/__init__.py` so Alembic's `autogenerate` can see them.
- **Migrations:** 1. Modify models. 
  2. Run `alembic revision --autogenerate -m "description"`.
  3. Review the generated file in `alembic/versions/`.
  4. Run `alembic upgrade head`.

## Reminders & Constraints
- **Sync Driver:** We are using `psycopg` (v3). Do not suggest `async` database calls or `asyncio.gather` for DB operations.
- **Documentation:** Always remind the user to update the `README.md` and the `alembic/versions` directory when adding new features or changing the schema.
- **Security:** Ensure no secrets or `.env` files are suggested for git commits.