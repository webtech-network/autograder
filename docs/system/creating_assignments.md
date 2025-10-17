# Creating Assignments with the Autograder

This guide walks you through setting up automated grading for your assignments using the autograder in GitHub Classroom.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start](#quick-start)
3. [Step-by-Step Setup](#step-by-step-setup)
4. [Configuration Options](#configuration-options)
5. [Example Assignments](#example-assignments)
6. [Troubleshooting](#troubleshooting)
7. [Best Practices](#best-practices)

---

## Prerequisites

Before you begin, ensure you have:

- A GitHub account with access to GitHub Classroom
- Basic understanding of Git and GitHub
- (Optional) OpenAI API key for AI-powered feedback
- (Optional) Redis instance for caching (improves performance)

---

## Quick Start

### 1. Create Your Assignment Repository

If using GitHub Classroom:
1. Create a new assignment in your GitHub Classroom
2. Set it as an individual or group assignment
3. Add your starter code (if any)

If using a regular GitHub repository:
1. Create a new repository for your assignment template
2. Add any starter files students will need

### 2. Add the Workflow File

Create `.github/workflows/autograder.yml` in your repository:

```yaml
name: Autograderr
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
  workflow_dispatch:

jobs:
  grading:
    permissions: write-all
    runs-on: ubuntu-latest
    if: github.actor != 'github-classroom[bot]'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
           path: submission

      - name: Check repository criteria
        uses: webtech-network/autograder@v5
        with:
          template_preset : "web dev"
          feedback-type: "ai"
          openai_key: ${{ secrets.ENGINE }}
          redis_url: ${{ secrets.REDIS_URL }}
          redis_token: ${{ secrets.REDIS_NAME }}
```

**Important Notes:**
- The `path: submission` parameter in the checkout step is **required**
- The `if: github.actor != 'github-classroom[bot]'` condition prevents the autograder from running when GitHub Classroom creates the repository

### 3. Configure Secrets

In your repository or organization settings, add the following secrets:

- `ENGINE`: Your OpenAI API key (for AI feedback)
- `REDIS_URL`: Your Redis instance URL (optional, for caching)
- `REDIS_NAME`: Your Redis authentication token (optional)

**To add secrets:**
1. Go to your repository Settings
2. Navigate to Secrets and variables → Actions
3. Click "New repository secret"
4. Add each secret with its corresponding value

---

## Step-by-Step Setup

### Step 1: Choose Your Template Preset

The autograder comes with several built-in templates:

- `"web dev"` - Evaluates HTML, CSS, and JavaScript projects
- `"html-css-basic"` - Basic HTML and CSS validation
- `"javascript-advanced"` - Advanced JavaScript testing

You can also use a custom template by setting `custom_template: true` - this will make the autograder look for a `template.py` file in your repository.

For this example, we're using `"web dev"`.

### Step 2: Select Feedback Type

Choose how detailed you want the feedback to be:

- `"default"` - Standard technical feedback with test results
- `"ai"` - AI-generated detailed feedback (requires OpenAI API key)

### Step 3: Create Configuration Files (Optional)

For more control over grading, you can add configuration files to your repository:

#### Custom Template (Advanced)

If you need complete control over grading logic, you can create a `template.py` file in your repository root and set `custom_template: true` in your workflow.

**`template.py` example:**

```python
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult

# ===============================================================
# region: TestFunction Implementations
# ===============================================================

class HasRequiredFile(TestFunction):
    @property
    def name(self):
        return "has_required_file"

    @property
    def description(self):
        return "Checks if a required file exists in the submission"

    @property
    def parameter_description(self):
        return {
            "file_path": "Path to the required file",
            "file_name": "Name of the required file"
        }

    def execute(self, file_path: str, file_name: str) -> TestResult:
        import os
        exists = os.path.exists(file_path)
        score = 100 if exists else 0
        report = f"File '{file_name}' found!" if exists else f"File '{file_name}' is missing."
        return TestResult(self.name, score, report, parameters={"file_name": file_name})


class CheckMinimumLines(TestFunction):
    @property
    def name(self):
        return "check_minimum_lines"

    @property
    def description(self):
        return "Checks if a file has at least a minimum number of lines"

    @property
    def parameter_description(self):
        return {
            "file_content": "Content of the file to check",
            "min_lines": "Minimum number of lines required"
        }

    def execute(self, file_content: str, min_lines: int) -> TestResult:
        lines = file_content.strip().split('\n')
        actual_lines = len([line for line in lines if line.strip()])
        score = min(100, int((actual_lines / min_lines) * 100)) if min_lines > 0 else 100
        report = f"File has {actual_lines} lines (minimum: {min_lines})"
        return TestResult(self.name, score, report, parameters={"min_lines": min_lines})


# ===============================================================
# endregion
# ===============================================================

class CustomAssignmentTemplate(Template):
    """
    A custom template for a specific assignment.
    """

    @property
    def template_name(self):
        return "Custom Assignment Template"

    @property
    def template_description(self):
        return "Custom grading template for specific assignment requirements"

    @property
    def requires_execution_helper(self) -> bool:
        return False

    @property
    def execution_helper(self):
        return None

    @property
    def requires_pre_executed_tree(self) -> bool:
        return False

    def __init__(self):
        self.tests = {
            "has_required_file": HasRequiredFile(),
            "check_minimum_lines": CheckMinimumLines(),
            # Add more custom tests here
        }

    def stop(self):
        pass

    def get_test(self, name: str) -> TestFunction:
        """
        Retrieves a specific test function instance from the template.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
```

Then in your workflow:
```yaml
- name: Check repository criteria
  uses: webtech-network/autograder@v5
  with:
    template_preset: "web dev"
    custom_template: true  # This tells the autograder to look for template.py
    feedback-type: "default"
```

#### `.autograder/criteria.json`

Define custom grading criteria:

```json
{
  "criteria": [
    {
      "id": "html-structure",
      "name": "HTML Structure",
      "description": "Valid HTML5 structure with proper semantic elements",
      "points": 30,
      "children": [
        {
          "id": "html-doctype",
          "name": "DOCTYPE Declaration",
          "description": "Page includes proper HTML5 DOCTYPE",
          "points": 5
        },
        {
          "id": "html-semantic",
          "name": "Semantic HTML",
          "description": "Uses semantic elements (header, nav, main, footer)",
          "points": 15
        }
      ]
    },
    {
      "id": "css-styling",
      "name": "CSS Styling",
      "description": "Proper CSS implementation",
      "points": 40
    }
  ]
}
```

#### `.autograder/feedback.json`

Customize feedback preferences:

```json
{
  "verbosity": "detailed",
  "include_suggestions": true,
  "include_positive_feedback": true,
  "tone": "encouraging",
  "language": "en",
  "format": "markdown"
}
```

#### `.autograder/setup.json`

Configure execution environment:

```json
{
  "timeout": 300,
  "working_directory": "submission",
  "environment": {
    "NODE_VERSION": "18"
  },
  "dependencies": {
    "npm_packages": ["eslint", "prettier"]
  }
}
```

### Step 4: Test Your Setup

1. Create a test branch in your repository
2. Make a commit that should trigger the autograder
3. Check the Actions tab to see the workflow run
4. Review the output to ensure everything works correctly

### Step 5: Deploy to GitHub Classroom

Once you've tested the workflow:

1. In GitHub Classroom, create or edit your assignment
2. Select your template repository (the one with the workflow)
3. Ensure "Enable feedback pull request" is checked (optional but recommended)
4. Students will now have the autograder run on their submissions

---

## Configuration Options

### Workflow Triggers

The workflow is triggered by:

- **`push` to `main` branch**: Every commit students push to main
- **`pull_request` to `main` branch**: When students create PRs
- **`workflow_dispatch`**: Manual trigger (useful for re-running grading)

### Autograder Inputs

| Input | Description | Required | Default |
|-------|-------------|----------|---------|
| `template_preset` | Grading template to use | Yes | - |
| `feedback-type` | Type of feedback to generate | Yes | - |
| `openai_key` | OpenAI API key for AI feedback | No (Yes for AI feedback) | - |
| `redis_url` | Redis URL for caching | No | - |
| `redis_token` | Redis authentication token | No | - |
| `custom_template` | Boolean flag to use custom template.py file | No | `false` |

---

## Example Assignments

### Example 1: Simple HTML/CSS Portfolio

**Assignment:** Create a personal portfolio website

**Workflow:**
```yaml
name: Autograderr
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
  workflow_dispatch:

jobs:
  grading:
    permissions: write-all
    runs-on: ubuntu-latest
    if: github.actor != 'github-classroom[bot]'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
           path: submission

      - name: Check repository criteria
        uses: webtech-network/autograder@v5
        with:
          template_preset : "web dev"
          feedback-type: "ai"
          openai_key: ${{ secrets.ENGINE }}
          redis_url: ${{ secrets.REDIS_URL }}
          redis_token: ${{ secrets.REDIS_NAME }}
```

**Expected structure:**
```
submission/
├── index.html
├── style.css
├── about.html
└── images/
    └── profile.jpg
```

### Example 2: JavaScript Interactive App

**Assignment:** Create an interactive to-do list application

**Workflow:** (same as above with `"web dev"` preset)

**Expected structure:**
```
submission/
├── index.html
├── styles.css
├── script.js
└── README.md
```

### Example 3: Custom Grading with Specific Criteria

**Assignment:** Build a responsive landing page with custom grading logic

**Step 1:** Create a `template.py` file in your repository root:

```python
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.core.models.test_result import TestResult
from bs4 import BeautifulSoup
import re

# ===============================================================
# region: TestFunction Implementations
# ===============================================================

class CheckResponsiveImages(TestFunction):
    @property
    def name(self):
        return "check_responsive_images"

    @property
    def description(self):
        return "Checks if images use responsive attributes"

    @property
    def parameter_description(self):
        return {
            "html_content": "The HTML content to analyze",
            "min_count": "Minimum number of responsive images required"
        }

    def execute(self, html_content: str, min_count: int) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        images = soup.find_all('img')
        responsive_count = 0

        for img in images:
            # Check for responsive attributes
            if img.get('srcset') or 'responsive' in img.get('class', []):
                responsive_count += 1

        score = min(100, int((responsive_count / min_count) * 100)) if min_count > 0 else 100
        report = f"Found {responsive_count} of {min_count} required responsive images."
        return TestResult(self.name, score, report, parameters={"min_count": min_count})


class CheckMediaQueries(TestFunction):
    @property
    def name(self):
        return "check_media_queries"

    @property
    def description(self):
        return "Checks if CSS contains media queries for responsive design"

    @property
    def parameter_description(self):
        return {
            "css_content": "The CSS content to analyze",
            "min_breakpoints": "Minimum number of breakpoints required"
        }

    def execute(self, css_content: str, min_breakpoints: int) -> TestResult:
        pattern = r'@media\s*\([^)]+\)'
        matches = re.findall(pattern, css_content)
        breakpoint_count = len(matches)

        score = min(100, int((breakpoint_count / min_breakpoints) * 100)) if min_breakpoints > 0 else 100
        report = f"Found {breakpoint_count} of {min_breakpoints} required media queries."
        return TestResult(self.name, score, report, parameters={"min_breakpoints": min_breakpoints})


# ===============================================================
# endregion
# ===============================================================

class ResponsiveLandingPageTemplate(Template):
    """
    Custom template for responsive landing page assignment.
    """

    @property
    def template_name(self):
        return "Responsive Landing Page Template"

    @property
    def template_description(self):
        return "Evaluates responsive design implementation in landing pages"

    @property
    def requires_execution_helper(self) -> bool:
        return False

    @property
    def execution_helper(self):
        return None

    @property
    def requires_pre_executed_tree(self) -> bool:
        return False

    def __init__(self):
        self.tests = {
            "check_responsive_images": CheckResponsiveImages(),
            "check_media_queries": CheckMediaQueries(),
        }

    def stop(self):
        pass

    def get_test(self, name: str) -> TestFunction:
        """
        Retrieves a specific test function instance from the template.
        """
        test_function = self.tests.get(name)
        if not test_function:
            raise AttributeError(f"Test '{name}' not found in the '{self.template_name}' template.")
        return test_function
```

**Step 2:** Update your workflow to use the custom template:

```yaml
name: Autograderr
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
  workflow_dispatch:

jobs:
  grading:
    permissions: write-all
    runs-on: ubuntu-latest
    if: github.actor != 'github-classroom[bot]'
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
           path: submission

      - name: Check repository criteria
        uses: webtech-network/autograder@v5
        with:
          template_preset: "web dev"
          custom_template: true
          feedback-type: "default"
          openai_key: ${{ secrets.ENGINE }}
          redis_url: ${{ secrets.REDIS_URL }}
          redis_token: ${{ secrets.REDIS_NAME }}
```

**Note:** When `custom_template: true` is set, the autograder will look for and use the `template.py` file in your repository to define grading criteria.

---

## Troubleshooting

### Workflow Doesn't Run

**Problem:** The autograder workflow doesn't start after a push.

**Solutions:**
1. Check that the workflow file is in `.github/workflows/` directory
2. Ensure the file has a `.yml` or `.yaml` extension
3. Verify the branch name matches your trigger (e.g., `main` vs `master`)
4. Check the Actions tab for any errors

### Authentication Errors

**Problem:** `Error: Invalid OpenAI API key` or `Redis connection failed`

**Solutions:**
1. Verify secrets are correctly named (e.g., `ENGINE`, `REDIS_URL`, `REDIS_NAME`)
2. Check that secrets are set at the repository or organization level
3. Ensure API keys are valid and have not expired
4. For organization secrets, verify they're accessible to the repository

### Checkout Issues

**Problem:** `Error: Unable to locate submission files`

**Solutions:**
1. Ensure `path: submission` is set in the checkout step (this is **required**)
2. Verify the checkout step completes successfully
3. Check that students' files are in the correct location

### Timeout Errors

**Problem:** `Error: Workflow timeout after 6 hours`

**Solutions:**
1. Add a `timeout-minutes` setting to your job:
   ```yaml
   jobs:
     grading:
       runs-on: ubuntu-latest
       timeout-minutes: 10
   ```
2. Check if student code contains infinite loops or long-running processes
3. Adjust timeout in `.autograder/setup.json` if needed

### Grading Results Not Appearing

**Problem:** Workflow runs successfully but no feedback is visible

**Solutions:**
1. Check the workflow logs in the Actions tab
2. Verify the autograder is generating output (look for "result" in logs)
3. If using GitHub Classroom feedback PR, ensure it's enabled
4. Check that the student has permissions to view Actions

### Permission Errors

**Problem:** `Error: Resource not accessible by integration`

**Solutions:**
1. Ensure `permissions: write-all` is set in the job configuration
2. Check repository settings → Actions → General → Workflow permissions
3. Verify that Actions have read and write permissions

---

## Best Practices

### 1. Start Simple

Begin with a basic preset template and minimal configuration. Add complexity as needed.

```yaml
# Simple starter configuration
- name: Check repository criteria
  uses: webtech-network/autograder@v5
  with:
    template_preset: "web dev"
    feedback-type: "detailed"
```

### 2. Test Before Deployment

Always test your workflow in a separate repository before deploying to GitHub Classroom assignments.

### 3. Provide Clear Instructions

Include a README in your assignment template that tells students:
- What the assignment requires
- How to test their code locally
- When the autograder will run
- How to interpret the feedback

### 4. Use Meaningful Criteria

Structure your grading criteria to match your learning objectives:

```json
{
  "criteria": [
    {
      "id": "functionality",
      "name": "Functional Requirements",
      "description": "All required features work correctly",
      "points": 50
    },
    {
      "id": "code-quality",
      "name": "Code Quality",
      "description": "Code is clean, readable, and well-organized",
      "points": 30
    },
    {
      "id": "documentation",
      "name": "Documentation",
      "description": "Code includes comments and README",
      "points": 20
    }
  ]
}
```

### 5. Balance Automation and Manual Review

The autograder is a tool to assist, not replace, your evaluation:
- Use it for objective criteria (syntax, structure, tests passing)
- Reserve manual review for subjective elements (design decisions, creativity)
- Consider making the autograder worth 60-80% of the grade

### 6. Provide Timely Feedback

Configure the workflow to run on every push so students get immediate feedback:
```yaml
on:
  push:
    branches:
      - main
  pull_request:
    branches:
      - main
```

### 7. Monitor Usage

Keep an eye on your GitHub Actions usage:
- Actions have usage limits depending on your plan
- Monitor the Actions tab for failed or stuck workflows
- Optimize workflows to reduce runtime

### 8. Use Caching for Better Performance

If you have a Redis instance, enable caching to speed up repeat evaluations:
```yaml
redis_url: ${{ secrets.REDIS_URL }}
redis_token: ${{ secrets.REDIS_NAME }}
```

### 9. Version Control Your Workflows

Use specific version tags for the autograder action to ensure consistency:
```yaml
uses: webtech-network/autograder@v5  # Specific version
```

### 10. Document Your Grading Rubric

Make your grading criteria transparent to students by including them in your assignment:
- Share the criteria.json file
- Explain point distributions
- Show example submissions and their scores

---

## Getting Help

If you encounter issues not covered in this guide:

1. **Check the logs**: Review the workflow run logs in the Actions tab
2. **Consult the documentation**: See other docs in this folder for detailed configuration options
3. **GitHub Issues**: Report bugs or request features on the autograder repository
4. **Community**: Ask questions in GitHub Discussions

---

## Next Steps

- Learn about [Grading Templates](templates/grading_templates.md)
- Explore [Configuration Options](configuration/criteria_config.md)
- Understand the [System Architecture](system_architecture.md)
- Review [Core Concepts](core_concepts.md)
