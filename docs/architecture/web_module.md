# Web Module — Architecture & Deployment

The `web/` module is the FastAPI-based REST API layer of the Autograder system. It handles HTTP requests, persists grading configurations and submissions to a database, and delegates actual grading to the core autograder pipeline via background tasks.

> **For endpoint reference**, see [API Documentation](../API.md).

---

## Architecture

The web module follows a clean layered architecture:

```
Client Request
    ↓
Endpoint (web/api/v1/)         → Route handlers, request validation
    ↓
Schema (web/schemas/)          → Pydantic models for request/response
    ↓
Repository (web/repositories/) → Data access layer (SQLAlchemy)
    ↓
Database (PostgreSQL/SQLite)   → Persistence
    ↓ (async)
Service (web/service/)         → Business logic, grading orchestration
    ↓
Autograder Pipeline            → Core grading engine
    ↓
Sandbox Manager                → Docker container execution
```

### Key Design Decisions

- **Async throughout**: All database operations and grading use `async/await` via SQLAlchemy's async engine and `asyncio`
- **Background grading**: Submissions are saved immediately, grading runs as an `asyncio.create_task` so the API responds without blocking
- **Repository pattern**: Database access is abstracted behind repository classes, keeping endpoint handlers thin
- **Stateless DCE**: The [Deliberate Code Execution](../features/deliberate_code_execution.md) feature bypasses the database entirely for fast, stateless code execution

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `postgresql+asyncpg://...localhost:5432/autograder` |
| `DATABASE_ECHO` | Log SQL queries | `False` |
| `DATABASE_POOL_SIZE` | Connection pool size (PostgreSQL only) | `10` |
| `DATABASE_MAX_OVERFLOW` | Max overflow connections | `20` |
| `DATABASE_POOL_TIMEOUT` | Connection timeout (seconds) | `30` |
| `DATABASE_POOL_RECYCLE` | Connection recycle time (seconds) | `3600` |
| `SANDBOX_POOL_SIZE` | Sandbox containers per language | `2` |
| `JSON_LOGS` | Use JSON logging format | `false` |
| `OPENAI_API_KEY` | OpenAI API key (for AI feedback mode) | — |

### Database Setup

#### PostgreSQL (Recommended for Production)

```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/autograder
```

**Connection pool sizing guidelines:**

| Environment | `POOL_SIZE` | `MAX_OVERFLOW` |
|-------------|-------------|----------------|
| Development | 5 | 10 |
| Production (low traffic) | 10 | 20 |
| Production (high traffic) | 20 | 40 |

#### SQLite (Development Only)

```bash
DATABASE_URL=sqlite+aiosqlite:///./autograder.db
```

> **Note:** SQLite lacks concurrent write support and connection pooling — not recommended for production.

### Database Migrations

```bash
# Apply all pending migrations
make db-upgrade

# Create a new migration
make db-migrate MSG="description of change"

# Show current version
make db-current

# Rollback last migration
make db-downgrade

# Reset database (destructive)
make db-reset
```

Or using Alembic directly:

```bash
alembic upgrade head          # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
alembic downgrade -1          # Rollback
alembic current               # Current version
```

---

## Deployment

### Docker Compose

```bash
docker-compose up -d
```

This starts PostgreSQL and the Autograder API with sandbox support.

### Manual

```bash
# Development
uvicorn web.main:app --reload

# Production
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

API docs available at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc` (ReDoc).

---

## Troubleshooting

### Database Connection Issues

- **PostgreSQL**: Verify `DATABASE_URL` includes the `postgresql+asyncpg://` prefix. Check the server is running (`docker ps` or `pg_isready`). Ensure migrations are up to date (`alembic current`).
- **SQLite**: Verify file path and directory permissions.
- **Pool exhaustion**: Reduce `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW`, or increase `DATABASE_POOL_TIMEOUT`. Enable `DATABASE_ECHO=True` temporarily to monitor pool activity.

### Sandbox Issues

- Verify Docker is running: `docker ps`
- Build sandbox images: `make sandbox-build-all`  
- Adjust pool size: `SANDBOX_POOL_SIZE` environment variable

### API Not Starting

- Check logs for startup errors
- Verify dependencies: `pip install -r requirements.txt`
- Ensure port 8000 is available

