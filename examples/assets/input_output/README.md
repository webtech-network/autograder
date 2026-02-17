# Autograder I/O Template Testing Assets

Interactive testing suite for the Autograder Input/Output template.

## Quick Start

1. **Start the Autograder API**:
   ```bash
   docker-compose up
   # OR
   uvicorn web.main:app --reload
   ```

2. **Launch the Testing Dashboard**:
   ```bash
   cd tests/assets/input_output
   python serve_dashboard.py
   ```

3. Open http://localhost:8080/index.html in your browser.

## Pages

| Page | Description |
|------|-------------|
| **index.html** | Main dashboard with navigation |
| **page_config.html** | Create grading configurations with visual tree builder |
| **page_submit.html** | Submit code for grading with result polling |
| **page_api.html** | Direct API operations (health check, CRUD, etc.) |

## Directory Structure

```
input_output/
├── index.html              # Main navigation page
├── page_config.html        # Configuration creator
├── page_submit.html        # Code submission & results
├── page_api.html           # API operations
├── styles.css              # Shared styles
├── shared.js               # Shared JavaScript (templates, code examples)
├── serve_dashboard.py      # HTTP server script
├── validate_criteria.py    # Criteria validation script
├── criteria_examples/      # JSON criteria examples
│   ├── 1_base_only_simple.json
│   ├── 2_base_and_bonus.json
│   ├── 3_base_bonus_penalty.json
│   ├── 4_with_subjects.json
│   └── 5_nested_subjects.json
└── code_examples/          # Sample code
    ├── python/
    ├── java/
    ├── javascript/
    └── cpp/
```

## Criteria Tree Templates

### 1. Base Only (Simple)
Simple test suite with only base tests. No subjects, no bonus/penalty.

### 2. Base + Bonus
Base tests with bonus points for extra credit (students can score >100%).

### 3. Base + Bonus + Penalty
Full category support with penalties for errors.

### 4. With Subjects
Tests organized into named subject groups with weights.

### 5. Nested Subjects (Complex)
Hierarchical structure with nested subjects for complex rubrics.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/v1/health | Health check |
| GET | /api/v1/ready | Readiness check |
| GET | /api/v1/templates | List templates |
| POST | /api/v1/configs | Create configuration |
| GET | /api/v1/configs | List configurations |
| GET | /api/v1/configs/{id} | Get configuration |
| PUT | /api/v1/configs/{id} | Update configuration |
| POST | /api/v1/submissions | Submit code |
| GET | /api/v1/submissions/{id} | Get submission result |
| GET | /api/v1/submissions/user/{id} | List user submissions |

## Code Examples

- **Simple Calculator**: Basic addition of two numbers
- **Advanced Calculator**: Full operations (add, subtract, multiply, divide, power, modulo, sqrt)
- **Broken Calculator**: Buggy implementation for testing failures
