# Autograder API Payload Structure Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AUTOGRADER API REQUEST PAYLOAD                       │
│                         (multipart/form-data)                            │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                 ┌───────────────────┴────────────────────┐
                 │                                        │
        ┌────────▼─────────┐                    ┌────────▼─────────┐
        │  FORM FIELDS     │                    │   FILE UPLOADS   │
        │  (text data)     │                    │   (binary data)  │
        └────────┬─────────┘                    └────────┬─────────┘
                 │                                        │
     ┌───────────┴───────────┐               ┌───────────┴────────────┐
     │                       │               │                        │
     ▼                       ▼               ▼                        ▼
┌──────────┐        ┌──────────────┐   ┌─────────────┐    ┌─────────────────┐
│ Required │        │  Optional    │   │ Submission  │    │  Configuration  │
│  Fields  │        │   Fields     │   │   Files     │    │     Files       │
└────┬─────┘        └──────┬───────┘   └──────┬──────┘    └────────┬────────┘
     │                     │                  │                    │
     │                     │                  │                    │
     │                     │                  │                    │
     ▼                     ▼                  ▼                    ▼


┌─────────────────────────────────────────────────────────────────────────┐
│                            REQUIRED FIELDS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  template_preset: "web dev" | "api" | "io" | "custom"                  │
│  ├─ Determines which grading template to use                           │
│  └─ Must match available templates in TemplateLibrary                  │
│                                                                          │
│  student_name: "John Doe"                                               │
│  ├─ Identifier for the student                                         │
│  └─ Used in feedback and reporting                                     │
│                                                                          │
│  student_credentials: "github-token-abc123"                             │
│  ├─ Authentication token (GitHub, etc.)                                │
│  └─ Used for future integrations                                       │
│                                                                          │
│  include_feedback: true | false                                         │
│  ├─ Whether to generate detailed feedback                              │
│  └─ Affects response content                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                            OPTIONAL FIELDS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  feedback_type: "default" | "ai"                                        │
│  ├─ Type of feedback generation                                        │
│  ├─ "default": Rule-based feedback                                     │
│  └─ "ai": OpenAI-powered feedback (requires openai_key)                │
│                                                                          │
│  openai_key: "sk-..."  [Required if feedback_type = "ai"]              │
│  ├─ OpenAI API key for AI-powered feedback                             │
│  └─ Not stored, used only for current request                          │
│                                                                          │
│  redis_url: "redis://..."  [Optional for AI feedback caching]          │
│  └─ Redis URL for caching AI responses                                 │
│                                                                          │
│  redis_token: "token..."  [Optional]                                    │
│  └─ Authentication for Redis connection                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         SUBMISSION FILES                                 │
│                  (submission_files - multiple files)                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  WEB DEV TEMPLATE:                                                      │
│  ├─ index.html          [HTML file]                                    │
│  ├─ style.css           [CSS file]                                     │
│  └─ script.js           [JavaScript file]                              │
│                                                                          │
│  API TESTING TEMPLATE:                                                  │
│  ├─ server.js           [Node.js server file]                          │
│  ├─ package.json        [NPM dependencies]                             │
│  └─ ...other JS/TS files                                               │
│                                                                          │
│  INPUT/OUTPUT TEMPLATE:                                                 │
│  ├─ program.py          [Python executable]                            │
│  ├─ requirements.txt    [Python dependencies]                          │
│  └─ ...other Python files                                              │
│                                                                          │
│  CUSTOM TEMPLATE:                                                       │
│  └─ Any files required by custom template                              │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                      CONFIGURATION FILES (JSON)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  criteria_json  [REQUIRED]                                              │
│  ├─ Defines grading criteria and test cases                            │
│  └─ Structure:                                                          │
│      {                                                                  │
│        "base": {                                                        │
│          "weight": 100,                                                 │
│          "subjects": {                                                  │
│            "subject_name": {                                            │
│              "weight": 50,                                              │
│              "tests": [                                                 │
│                {                                                        │
│                  "name": "test_function_name",                          │
│                  "file": "filename.ext",                                │
│                  "calls": [["param1", "param2"]]                        │
│                }                                                        │
│              ]                                                          │
│            }                                                            │
│          }                                                              │
│        }                                                                │
│      }                                                                  │
│                                                                          │
│  feedback_json  [OPTIONAL but recommended]                              │
│  ├─ Configures feedback generation                                     │
│  └─ Structure:                                                          │
│      {                                                                  │
│        "general": {                                                     │
│          "report_title": "Assignment Feedback",                         │
│          "show_passed_tests": true,                                     │
│          "show_test_details": true                                      │
│        },                                                               │
│        "default": {                                                     │
│          "category_headers": {                                          │
│            "base": "Core Requirements"                                  │
│          }                                                              │
│        }                                                                │
│      }                                                                  │
│                                                                          │
│  setup_json  [REQUIRED for "api" and "io" templates]                   │
│  ├─ Docker container configuration                                     │
│  └─ Structure:                                                          │
│      {                                                                  │
│        "runtime_image": "node:18-alpine",                               │
│        "container_port": 8000,                                          │
│        "start_command": "node server.js",                               │
│        "commands": {                                                    │
│          "install_dependencies": "npm install"                          │
│        }                                                                │
│      }                                                                  │
│                                                                          │
│  custom_template  [REQUIRED for "custom" template]                     │
│  ├─ Python file defining custom Template class                         │
│  ├─ Must inherit from autograder.builder.models.template.Template      │
│  └─ Implements custom test functions                                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                           PROCESSING FLOW                                │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │   REQUEST    │
    │   RECEIVED   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   VALIDATE   │────────► Missing fields? ──► 400 Error
    │    FIELDS    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │     LOAD     │────────► Invalid template? ──► 404 Error
    │   TEMPLATE   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │    CREATE    │
    │   REQUEST    │
    │   CONTEXT    │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   SETUP      │────────► Docker setup (if needed)
    │ ENVIRONMENT  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   EXECUTE    │────────► Run all test cases
    │    TESTS     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │  CALCULATE   │────────► Weighted scores
    │    SCORE     │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   GENERATE   │────────► Default or AI feedback
    │   FEEDBACK   │
    └──────┬───────┘
           │
           ▼
    ┌──────────────┐
    │   RETURN     │────────► JSON response
    │   RESULTS    │
    └──────────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                           RESPONSE STRUCTURE                             │
└─────────────────────────────────────────────────────────────────────────┘

{
  "server_status": "Server connection happened successfully",
  "autograding_status": "completed" | "failed" | "partial",
  "final_score": 92.5,  // 0-100
  "feedback": "Detailed feedback text...",
  "test_report": [
    {
      "name": "test_function_name",
      "score": 100,  // 0-100
      "report": "Test execution report",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
    // ... more tests
  ]
}


┌─────────────────────────────────────────────────────────────────────────┐
│                        TEMPLATE REQUIREMENTS                             │
└─────────────────────────────────────────────────────────────────────────┘

┌────────────────┬─────────────────┬──────────────┬────────────────────┐
│   Template     │  Files Needed   │ Setup JSON?  │  Docker Required?  │
├────────────────┼─────────────────┼──────────────┼────────────────────┤
│ web dev        │ HTML/CSS/JS     │      ❌      │         ❌         │
│ api            │ server.js, etc  │      ✅      │         ✅         │
│ io             │ Python/other    │      ✅      │         ✅         │
│ custom         │ Any + template  │      ⚠️      │         ⚠️         │
└────────────────┴─────────────────┴──────────────┴────────────────────┘

Legend: ✅ Required  ❌ Not needed  ⚠️ Optional/Depends


┌─────────────────────────────────────────────────────────────────────────┐
│                          EXAMPLE PAYLOADS                                │
└─────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════
EXAMPLE 1: Web Development
═══════════════════════════════════════════════════════════════════════════

Form Data:
  template_preset: "web dev"
  student_name: "John Doe"
  student_credentials: "token-123"
  include_feedback: true
  feedback_type: "default"

Files:
  submission_files: index.html, style.css, script.js
  criteria_json: criteria.json
  feedback_json: feedback.json


═══════════════════════════════════════════════════════════════════════════
EXAMPLE 2: API Testing
═══════════════════════════════════════════════════════════════════════════

Form Data:
  template_preset: "api"
  student_name: "Jane Smith"
  student_credentials: "token-456"
  include_feedback: true

Files:
  submission_files: server.js, package.json
  criteria_json: criteria.json
  feedback_json: feedback.json
  setup_json: setup.json  ← REQUIRED for API template


═══════════════════════════════════════════════════════════════════════════
EXAMPLE 3: Custom Template
═══════════════════════════════════════════════════════════════════════════

Form Data:
  template_preset: "custom"
  student_name: "Alice Williams"
  student_credentials: "token-789"
  include_feedback: true

Files:
  submission_files: main.py
  criteria_json: criteria.json
  feedback_json: feedback.json
  custom_template: template.py  ← REQUIRED for custom template


┌─────────────────────────────────────────────────────────────────────────┐
│                    KEY VALIDATION RULES                                  │
└─────────────────────────────────────────────────────────────────────────┘

1. template_preset must be one of: "web dev", "api", "io", "custom"
2. At least one submission_file must be provided
3. criteria_json is always required
4. setup_json is required for "api" and "io" templates
5. custom_template is required for "custom" template
6. feedback_type "ai" requires openai_key
7. File names in criteria.json must match submission files
8. All JSON files must be valid JSON format
9. Docker images in setup.json must be accessible
10. Test function names in criteria must exist in template
