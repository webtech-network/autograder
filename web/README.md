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
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./autograder.db` |
| `DATABASE_ECHO` | Log SQL queries | `False` |
| `SANDBOX_POOL_SIZE` | Sandbox containers per language | `2` |
| `JSON_LOGS` | Use JSON logging format | `false` |
| `OPENAI_API_KEY` | OpenAI API key for AI feedback | - |

### Database Configuration

#### SQLite (Development)
```bash
DATABASE_URL=sqlite+aiosqlite:///./autograder.db
```

#### PostgreSQL (Production)
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/autograder
```

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

### Create a new migration
```bash
alembic revision --autogenerate -m "Description"
```

### Apply migrations
```bash
alembic upgrade head
```

### Rollback migration
```bash
alembic downgrade -1
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
```

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
- Verify `DATABASE_URL` is correct
- Ensure PostgreSQL is running (if using PostgreSQL)
- Check migrations are up to date: `alembic current`

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
