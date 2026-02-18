# Autograder Web API

RESTful API for code submission grading using the Autograder system.

## Features

- **Grading Configuration Management**: Create and manage grading criteria for assignments
- **Submission Processing**: Submit code for grading with background task processing
- **Template Library**: Access to various grading templates (webdev, API, I/O, etc.)
- **Database Persistence**: PostgreSQL or SQLite support with Alembic migrations
- **Sandbox Execution**: Secure code execution in Docker containers
- **Structured Logging**: JSON or human-readable logging formats
- **Health Monitoring**: Health check and readiness endpoints

## Quick Start

### Prerequisites

- Python 3.10+
- Docker (for sandbox execution)
- PostgreSQL (optional, SQLite works for development)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

3. Run database migrations:
```bash
# Using make command (recommended)
make db-upgrade

# Or using alembic directly
alembic upgrade head
```

4. Build sandbox images (required for code execution):
```bash
make sandbox-build-all
```

5. Start the API:
```bash
uvicorn web.main:app --reload
```

The API will be available at `http://localhost:8000`.

## API Documentation

Once the API is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Key Endpoints

#### Health & Monitoring
- `GET /api/v1/health` - Health check
- `GET /api/v1/ready` - Readiness check

#### Templates
- `GET /api/v1/templates` - List all available templates
- `GET /api/v1/templates/{name}` - Get template details

#### Grading Configurations
- `POST /api/v1/configs` - Create a grading configuration
- `GET /api/v1/configs/{external_assignment_id}` - Get configuration
- `GET /api/v1/configs` - List all configurations
- `PUT /api/v1/configs/{id}` - Update configuration

#### Submissions
- `POST /api/v1/submissions` - Submit code for grading
- `GET /api/v1/submissions/{id}` - Get submission with results
- `GET /api/v1/submissions/user/{user_id}` - Get user's submissions

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder` |
| `DATABASE_ECHO` | Log SQL queries | `False` |
| `DATABASE_POOL_SIZE` | PostgreSQL connection pool size | `10` |
| `DATABASE_MAX_OVERFLOW` | PostgreSQL max overflow connections | `20` |
| `DATABASE_POOL_TIMEOUT` | Connection timeout in seconds | `30` |
| `DATABASE_POOL_RECYCLE` | Connection recycle time in seconds | `3600` |
| `SANDBOX_POOL_SIZE` | Sandbox containers per language | `2` |
| `JSON_LOGS` | Use JSON logging format | `false` |
| `OPENAI_API_KEY` | OpenAI API key for AI feedback | - |

### Database Configuration

#### PostgreSQL (Recommended)
```bash
# Production
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/autograder
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40

# Development
DATABASE_URL=postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
```

**Connection Pool Best Practices:**
- Development: `POOL_SIZE=5`, `MAX_OVERFLOW=10`
- Production (low traffic): `POOL_SIZE=10`, `MAX_OVERFLOW=20`
- Production (high traffic): `POOL_SIZE=20`, `MAX_OVERFLOW=40`
- Enable `pool_pre_ping=True` for connection health checks (enabled by default)

#### SQLite (Development Only)
```bash
DATABASE_URL=sqlite+aiosqlite:///./autograder.db
# Note: Pool settings are ignored for SQLite
```

**Important:** SQLite is not recommended for production use due to:
- No concurrent write support
- Limited performance under load
- No connection pooling
- Missing PostgreSQL-specific optimizations

## Docker Deployment

### Using Docker Compose

```bash
docker-compose up -d
```

This will start:
- PostgreSQL database
- Autograder API with sandbox support

### Building the API Image

```bash
docker build -t autograder-api:latest -f Dockerfile.api .
```

## Database Migrations

### Using Make Commands (Recommended)

```bash
# Initialize/upgrade database to latest version
make db-init

# Apply all pending migrations
make db-upgrade

# Create a new migration
make db-migrate MSG="add user profile table"

# Show current migration version
make db-current

# Show migration history
make db-history

# Rollback last migration
make db-downgrade

# Reset database (WARNING: destructive)
make db-reset
```

### Using Alembic Directly

#### Create a new migration
```bash
alembic revision --autogenerate -m "Description"
```

#### Apply migrations
```bash
alembic upgrade head
```

#### Rollback migration
```bash
alembic downgrade -1
```

#### Check current version
```bash
alembic current
```

#### View migration history
```bash
alembic history --verbose
```

## Usage Example

### 1. Create a Grading Configuration

```python
import requests

response = requests.post("http://localhost:8000/api/v1/configs", json={
    "external_assignment_id": "assignment-1",
    "template_name": "webdev",
    "language": "python",
    "criteria_config": {
        "tests": ["test_homepage", "test_navigation"]
    }
})
config = response.json()
```

### 2. Submit Code for Grading

```python
response = requests.post("http://localhost:8000/api/v1/submissions", json={
    "external_assignment_id": "assignment-1",
    "external_user_id": "student-123",
    "username": "john.doe",
    "files": {
        "app.py": "from flask import Flask\napp = Flask(__name__)"
    }
})
submission = response.json()
```

### 3. Get Results

```python
submission_id = submission["id"]
response = requests.get(f"http://localhost:8000/api/v1/submissions/{submission_id}")
result = response.json()

print(f"Score: {result['final_score']}")
print(f"Feedback: {result['feedback']}")
print(f"Status: {result['status']}")

# New: Pipeline execution details
if result.get('pipeline_execution'):
    exec_info = result['pipeline_execution']
    print(f"\nPipeline Status: {exec_info['status']}")
    print(f"Execution Time: {exec_info['execution_time_ms']}ms")
    
    # Check if preflight failed
    if exec_info.get('failed_at_step') == 'PRE_FLIGHT':
        print("Preflight check failed - see feedback for details")
    
    # Show all executed steps
    for step in exec_info['steps']:
        print(f"  {step['name']}: {step['status']}")
        if step.get('error_details'):
            print(f"    Error: {step.get('message')}")
```

**Response Structure:**

```json
{
  "id": 1,
  "status": "completed",
  "final_score": 85.5,
  "feedback": "Grade: 85.5/100...",
  "result_tree": { /* Grading results */ },
  "pipeline_execution": {
    "status": "success",
    "failed_at_step": null,
    "total_steps_planned": 7,
    "steps_completed": 7,
    "execution_time_ms": 4521,
    "steps": [
      {"name": "PRE_FLIGHT", "status": "success"},
      {"name": "GRADE", "status": "success"}
    ]
  }
}
```

**Note:** The `pipeline_execution` field provides complete transparency into the grading process, including detailed error information if any step fails.

## Testing

### Run Unit Tests
```bash
pytest tests/web/test_database.py -v
```

### Run All Tests
```bash
pytest -v
```

## Architecture

The API follows a clean architecture pattern:

- **Models**: SQLAlchemy ORM models for database entities
- **Repositories**: Data access layer abstracting database operations
- **Schemas**: Pydantic models for request/response validation
- **Services**: Business logic (template library, sandbox manager)
- **Endpoints**: FastAPI route handlers

### Request Flow

```
Client → POST /submissions → Validation → Database → Background Task
                                                           ↓
                                                    Autograder Pipeline
                                                           ↓
                                                    Sandbox Execution
                                                           ↓
                                                    Store Results → Database
```

## Monitoring

### Health Check
```bash
curl http://localhost:8000/api/v1/health
```

### Check Logs
```bash
# Human-readable logs (development)
JSON_LOGS=false uvicorn web.main:app

# JSON logs (production)
JSON_LOGS=true uvicorn web.main:app
```

## Security Considerations

1. **Sandbox Isolation**: Code runs in isolated Docker containers
2. **Input Validation**: Pydantic schemas validate all inputs
3. **Database Security**: Parameterized queries prevent SQL injection
4. **Environment Variables**: Sensitive data in environment, not code

## Troubleshooting

### Database Connection Issues

#### PostgreSQL
- Verify `DATABASE_URL` is correct and includes `postgresql+asyncpg://` prefix
- Ensure PostgreSQL is running: `docker ps` or `pg_isready`
- Check PostgreSQL logs: `docker logs autograder-postgres`
- Test connection: `psql -U autograder -d autograder -h localhost`
- Verify user permissions: ensure the database user has CREATE, INSERT, UPDATE, DELETE privileges
- Check migrations are up to date: `alembic current`

#### SQLite
- Verify file path in `DATABASE_URL`
- Check file permissions for the database file
- Ensure directory exists for the .db file

### Connection Pool Issues
- **Too many connections**: Reduce `DATABASE_POOL_SIZE` and `DATABASE_MAX_OVERFLOW`
- **Connection timeouts**: Increase `DATABASE_POOL_TIMEOUT`
- **Stale connections**: Ensure `pool_pre_ping=True` and `pool_recycle=3600` are set
- Monitor pool usage: Enable `DATABASE_ECHO=True` temporarily to see connection activity

### Sandbox Issues
- Verify Docker is running: `docker ps`
- Build sandbox images: `make sandbox-build-all`
- Check sandbox pool size: `SANDBOX_POOL_SIZE` environment variable

### API Not Starting
- Check logs for startup errors
- Verify all dependencies are installed: `pip install -r requirements.txt`
- Ensure port 8000 is available

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `pytest`
5. Submit a pull request

## License

See LICENSE file for details.
