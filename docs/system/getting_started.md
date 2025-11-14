# Getting Started with the Autograder

## Overview

The autograder provides an automated grading system that allows teachers to evaluate student submissions programmatically. This guide explains how the autograder works and how to set up assignments.

## How It Works

The autograder follows a simple workflow:

1. **Teacher sends an `AutograderRequest`** containing grading preferences and assignment configuration
2. **Autograder processes** the submission files according to the configuration
3. **Autograder returns an `AutograderResponse`** with scores, feedback, and detailed test reports

---

## The AutograderRequest

The `AutograderRequest` is the entry point for the grading system. It contains all the information needed to grade a student's submission.

### Core Components

#### 1. Student Information
- **Student Name**: Identifies the student being graded
- **Student Credentials** (optional): Additional authentication or identification data

#### 2. Grading Preferences
- **Include Feedback**: Boolean flag to determine if feedback should be generated
- **Feedback Mode**: Specifies the type of feedback generation
  - `"default"`: Standard rule-based feedback
  - `"AI"`: AI-powered contextual feedback using OpenAI

#### 3. External Service Configuration
- **OpenAI Key**: Required when using AI-powered feedback mode
- **Redis URL & Token**: For caching and distributed grading operations

#### 4. Submission Files
A dictionary containing all the student's submitted files to be graded.

#### 5. Assignment Config
The core configuration package that defines how the assignment should be graded. See below for details.

---

## The AssignmentConfig

The `AssignmentConfig` is the heart of the grading setup. It contains all configurations for the **pre-grading**, **grading**, and **post-grading** processes.

### Components

#### 1. **Template**
Specifies the grading template to use. Templates provide pre-built grading logic for common assignment types.

- **Template Options**: `"custom"`, `"web dev"`, and others
- **Purpose**: Simplifies setup for standard assignment types
- 📚 **[Learn more about templates →](/docs/system/templates/grading_templates.md)** _(grading_templates.md)_

#### 2. **Criteria Configuration** (JSON)
Defines the grading criteria as a tree structure:
- Test cases and their point values
- Nested criteria with dependencies
- Pass/fail conditions
- Grading rubric hierarchy

📄 **Detailed documentation**: See [criteria_config.md](/docs/system//configuration/criteria_config.md)

#### 3. **Setup Configuration** (JSON)
Controls the pre-grading environment setup:
- **Mandatory Files**: List of files that must be present before grading
- **Template-Specific Settings**: Container startup commands, environment variables, etc.
- **Pre-execution Checks**: Validation steps before running tests

📄 **Detailed documentation**: See [setup_config.md](docs/system/configuration/setup_config.md)

#### 4. **Feedback Configuration** (JSON)
Defines how feedback should be presented to students:
- Feedback verbosity level
- Which test details to include/exclude
- Formatting preferences
- AI feedback customization options

📄 **Detailed documentation**: See [feedback_config.md](docs/system/configuration/feedback_config.md)

#### 5. **Custom Template Code** (optional)
When using `template="custom"`, you can provide:
- Custom Python code defining the grading logic
- Allows complete control over the grading process
- Bypasses pre-built templates for specialized assignments

---

## The Grading Process

Once the autograder receives an `AutograderRequest`:

1. **Pre-Flight Checks**: Validates mandatory files and setup requirements
2. **Environment Setup**: Prepares the grading environment (containers, dependencies, etc.)
3. **Test Execution**: Runs all tests defined in the criteria configuration
4. **Result Processing**: Calculates scores based on the criteria tree
5. **Feedback Generation**: Creates student feedback based on configuration and mode
6. **Response Assembly**: Packages everything into an `AutograderResponse`

---

## The AutograderResponse

The autograder returns an `AutograderResponse` object containing:

### Response Fields

- **Status**: Indicates success or failure of the grading process
- **Final Score**: The calculated grade (typically 0.0 to 100.0)
- **Feedback**: Human-readable feedback text for the student
- **Test Report**: Detailed list of `TestResult` objects showing:
  - Individual test outcomes
  - Points earned/lost
  - Error messages and diagnostics
  - Execution details

---

## Quick Start Example

Here's a minimal example of setting up an autograder request:

```python
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig

# Define your configuration
assignment_config = AssignmentConfig(
    template="custom",
    criteria=criteria_json,      # Your criteria tree
    setup=setup_json,             # Your setup requirements
    feedback=feedback_json        # Your feedback preferences
)

# Create the request
request = AutograderRequest(
    submission_files={"main.py": "student code here..."},
    assignment_config=assignment_config,
    student_name="Jane Doe",
    include_feedback=True,
    feedback_mode="AI",
    openai_key="your-key-here"
)

# Send to autograder and receive response
response = autograder.grade(request)

print(f"Score: {response.final_score}")
print(f"Feedback: {response.feedback}")
```

---

## Next Steps

Now that you understand the overall structure, dive deeper into each configuration file:

- 📋 **[Criteria Configuration](docs/system/configuration/criteria_config.md)** - Define your grading rubric
- ⚙️ **[Setup Configuration](docs/system/configuration/setup_config.md)** - Configure the grading environment
- 💬 **[Feedback Configuration](docs/system/configuration/feedback_config.md)** - Customize student feedback
- 🎨 **[Templates Guide](docs/templates/)** - Use pre-built grading templates

---

## Need Help?

- Review the [Core Concepts](docs/system/core_concepts.md) documentation
- Check the [System Architecture](docs/system/system_architecture.md) for technical details
- Examine example configurations in the repository
