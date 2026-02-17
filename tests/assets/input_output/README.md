# Autograder I/O Template Testing Assets

This directory contains testing assets for the Autograder Input/Output template, including a comprehensive interactive web dashboard.

## Quick Start

1. **Start the Autograder API**:
   ```bash
   # From the project root
   docker-compose up
   # OR
   uvicorn web.main:app --reload
   ```

2. **Launch the Testing Dashboard**:
   ```bash
   cd tests/assets/input_output
   python serve_dashboard.py
   ```

3. Open http://localhost:8080/testing_dashboard.html in your browser.

## Directory Structure

```
input_output/
├── testing_dashboard.html     # Interactive web UI for testing
├── serve_dashboard.py         # Simple HTTP server script
├── criteria_examples/         # Criteria tree configuration examples
│   ├── 1_base_only_simple.json
│   ├── 2_base_and_bonus.json
│   ├── 3_base_bonus_penalty.json
│   ├── 4_with_subjects.json
│   └── 5_nested_subjects.json
└── code_examples/             # Sample code in various languages
    ├── python/
    ├── java/
    ├── javascript/
    └── cpp/
```

## Criteria Tree Examples

### 1. Base Tests Only (Simple)
The simplest configuration with only base tests. No subjects, no bonus/penalty categories.

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "tests": [...]
  }
}
```

### 2. Base + Bonus Tests
Adds bonus points for extra features. Students can score above 100%.

```json
{
  "test_library": "input_output",
  "base": { "weight": 100, "tests": [...] },
  "bonus": { "weight": 15, "tests": [...] }
}
```

### 3. Base + Bonus + Penalty Tests
Full category support including penalties.

```json
{
  "test_library": "input_output",
  "base": { "weight": 100, "tests": [...] },
  "bonus": { "weight": 15, "tests": [...] },
  "penalty": { "weight": 20, "tests": [...] }
}
```

### 4. With Subjects (Organized)
Groups tests into subjects with individual weights.

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "subjects": [
      { "subject_name": "Addition", "weight": 50, "tests": [...] },
      { "subject_name": "Subtraction", "weight": 50, "tests": [...] }
    ]
  }
}
```

### 5. Nested Subjects (Complex)
Full hierarchical structure with nested subjects.

```json
{
  "test_library": "input_output",
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Basic Operations",
        "weight": 60,
        "subjects": [
          { "subject_name": "Addition", "weight": 50, "tests": [...] },
          { "subject_name": "Subtraction", "weight": 50, "tests": [...] }
        ]
      },
      {
        "subject_name": "Advanced Operations",
        "weight": 40,
        "subjects": [...]
      }
    ]
  }
}
```

## Testing Dashboard Features

### Create Configuration Tab
- Select from 5 pre-built criteria tree templates
- Choose programming language (Python, Java, JavaScript, C++)
- Visual tree structure preview
- Editable JSON with syntax highlighting
- One-click API submission

### Submit Code Tab
- Pre-built code examples for each language
- Simple, advanced, and broken calculator variants
- Custom code editor
- Automatic filename detection

### View Results Tab
- Fetch submission results by ID
- List all submissions for a user
- Visual score display
- Result tree visualization
- Feedback display

### CRUD Operations Tab
- List all configurations
- Get configuration by ID
- Update configurations
- Get submissions
- System health checks
- Template listing

## Code Examples

### Simple Calculator
Basic addition of two numbers from stdin.

### Advanced Calculator  
Full calculator with operations:
- add, subtract, multiply, divide
- power, modulo, sqrt
- Error handling for division by zero, invalid input, unknown operations

### Broken Calculator
A buggy implementation that subtracts instead of adds - useful for testing failure scenarios.

## API Endpoints Used

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/v1/configs | Create grading configuration |
| GET | /api/v1/configs/{id} | Get configuration |
| GET | /api/v1/configs | List configurations |
| PUT | /api/v1/configs/{id} | Update configuration |
| POST | /api/v1/submissions | Submit code for grading |
| GET | /api/v1/submissions/{id} | Get submission with results |
| GET | /api/v1/submissions/user/{id} | List user submissions |
| GET | /api/v1/health | Health check |
| GET | /api/v1/ready | Readiness check |
| GET | /api/v1/templates | List available templates |

## Test Configuration Structure

Each test in the I/O template uses the `expect_output` test function with these parameters:

```json
{
  "name": "expect_output",
  "parameters": [
    {
      "name": "inputs",
      "value": ["5", "3"]
    },
    {
      "name": "expected_output", 
      "value": "8"
    },
    {
      "name": "program_command",
      "value": "python3 calculator.py"
    }
  ]
}
```

## Score Calculation

Final score is calculated as:

```
final_score = base_score + bonus_score - penalty_score
```

Where each category score is the weighted sum of its tests/subjects.

## Troubleshooting

### API Connection Issues
- Ensure the Autograder API is running on port 8000
- Check the API URL in the dashboard navbar
- Use the Health Check button to verify connectivity

### Configuration Errors
- Ensure JSON is valid (use the Format button)
- Check that all weights are between 0-100
- Verify test names match template functions

### Submission Failures
- Verify the assignment ID exists
- Check that language is supported
- Review the API response for error details

