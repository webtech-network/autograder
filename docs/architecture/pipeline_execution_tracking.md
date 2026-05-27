# Pipeline Execution Tracking

## Overview

As of February 2026, the autograder now provides comprehensive pipeline execution tracking in all submission responses. This gives complete transparency into the grading process, especially useful for debugging and understanding preflight failures.

## What Changed

### New API Response Fields

Every submission response now includes a `pipeline_execution` field that contains:

- Execution status and timing
- All executed pipeline steps (including granular setup steps)
- Detailed error information for failures
- Human-readable error messages in the `feedback` field

### Key Benefits

1. **Transparency**: Students can see exactly what happened during grading
2. **Better Errors**: Clear, actionable feedback for compilation and setup failures
3. **Debugging**: Instructors can trace exactly where submissions fail
4. **Audit Trail**: Complete record of pipeline execution for each submission

## API Response Structure

### Field Separation

The response now has three distinct fields for different purposes:

| Field | Purpose | When Populated |
|-------|---------|----------------|
| `result_tree` | Grading results ONLY | After successful GRADE step |
| `pipeline_execution` | All pipeline steps | Always (success or failure) |
| `feedback` | Human-readable messages | Always (auto-generated for failures) |

### Response When Grading Succeeds

```json
{
  "id": 12,
  "status": "completed",
  "final_score": 85.5,
  
  "feedback": "## Grade: 85.5/100\n\n### ✅ Base Tests (85.5/100)...",
  
  "result_tree": {
    "final_score": 85.5,
    "children": {
      "base": { /* grading details */ }
    }
  },
  
  "pipeline_execution": {
    "status": "success",
    "failed_at_step": null,
    "total_steps_planned": 10,
    "steps_completed": 10,
    "execution_time_ms": 4521,
    "steps": [
      {
        "name": "LOAD_TEMPLATE",
        "status": "success",
        "message": "Template loaded successfully"
      },
      {
        "name": "BUILD_TREE",
        "status": "success",
        "message": "Criteria tree built successfully"
      },
      {
        "name": "FILE_CHECK",
        "status": "success",
        "message": "All required files are present"
      },
      {
        "name": "SANDBOX",
        "status": "success",
        "message": "Sandbox environment allocated"
      },
      {
        "name": "ASSET_INJECTION",
        "status": "success",
        "message": "Assets injected successfully"
      },
      {
        "name": "SETUP_COMMANDS",
        "status": "success",
        "message": "Setup commands executed successfully"
      },
      {
        "name": "GRADE",
        "status": "success",
        "message": "Grading completed: 85.5/100"
      },
      {
        "name": "FEEDBACK",
        "status": "success",
        "message": "Feedback generated"
      }
    ]
  }
}
```

### Response When Setup Fails (e.g. Compilation)

```json
{
  "id": 11,
  "status": "failed",
  "final_score": 0,
  
  "feedback": "## Preflight Check Failed\n\nYour submission failed during the setup phase before grading could begin.\n\n### Setup Command Failed: Compile Calculator.java\n\n**Command executed:**\n```bash\njavac Calculator.java\n```\n\n**Exit code:** 1\n\n**Error output:**\n```\nCalculator.java:4: error: ';' expected\n        Scanner sc = new Scanner(System.in)\n                                           ^\n1 error\n```\n\n**What to do:**\n- Fix the compilation errors shown above\n- Pay attention to the line numbers and error messages\n- Common issues: missing semicolons, undefined variables, syntax errors\n- Resubmit after fixing all compilation errors\n",
  
  "result_tree": null,
  
  "pipeline_execution": {
    "status": "failed",
    "failed_at_step": "SetupCommandsStep",
    "total_steps_planned": 10,
    "steps_completed": 6,
    "execution_time_ms": 1523,
    "steps": [
      {
        "name": "LOAD_TEMPLATE",
        "status": "success",
        "message": "Template loaded successfully"
      },
      {
        "name": "BUILD_TREE",
        "status": "success",
        "message": "Criteria tree built successfully"
      },
      {
        "name": "FILE_CHECK",
        "status": "success",
        "message": "All required files are present"
      },
      {
        "name": "SANDBOX",
        "status": "success",
        "message": "Sandbox environment allocated"
      },
      {
        "name": "ASSET_INJECTION",
        "status": "success",
        "message": "Assets injected successfully"
      },
      {
        "name": "SETUP_COMMANDS",
        "status": "fail",
        "message": "Setup command 'Compile Calculator.java' failed with exit code 1",
        "error_details": {
          "error_type": "setup_command_failed",
          "phase": "setup_commands",
          "command_name": "Compile Calculator.java",
          "failed_command": {
            "command": "javac Calculator.java",
            "exit_code": 1,
            "stderr": "Calculator.java:4: error: ';' expected\n        Scanner sc = new Scanner(System.in)\n                                           ^\n1 error\n"
          }
        }
      }
    ]
  }
}
```

## Using Pipeline Execution Data

### Check for Setup Failures

```python
def check_setup_status(submission):
    """Check if submission failed during setup (file check, asset injection, setup commands)."""
    pipeline = submission.get('pipeline_execution', {})
    setup_steps = ['FileCheckStep', 'AssetInjectionStep', 'SetupCommandsStep']
    
    failed_at = pipeline.get('failed_at_step')
    if failed_at in setup_steps:
        print(f"Setup failed at {failed_at}!")
        
        # Get error details
        for step in pipeline.get('steps', []):
            if step['name'] == failed_at and step['status'] == 'fail':
                error_details = step.get('error_details', {})
                
                if error_details.get('error_type') == 'setup_command_failed':
                    cmd = error_details.get('failed_command', {})
                    print(f"Command failed: {cmd.get('command')}")
                
                elif error_details.get('error_type') == 'required_file_missing':
                    print(f"Missing file: {error_details.get('missing_file')}")
        
        return False
    
    return True
```

### Display Execution Timeline

```python
def show_execution_timeline(submission):
    """Display execution timeline for debugging."""
    pipeline = submission.get('pipeline_execution', {})
    
    print(f"Pipeline Status: {pipeline.get('status')}")
    print(f"Total Time: {pipeline.get('execution_time_ms')}ms")
    print(f"Steps: {pipeline.get('steps_completed')}/{pipeline.get('total_steps_planned')}")
    print("\nExecution Steps:")
    
    for step in pipeline.get('steps', []):
        status_icon = "✅" if step['status'] == 'success' else "❌"
        print(f"  {status_icon} {step['name']}: {step.get('message', 'No message')}")
        
        if step.get('error_details'):
            print(f"     Error Type: {step['error_details'].get('error_type')}")
```

## Error Types

### Granular Setup Errors

#### 1. Required File Missing (`FileCheckStep`)

**Error Details Structure:**
```json
{
  "error_type": "required_file_missing",
  "phase": "required_files",
  "missing_file": "Calculator.java"
}
```

#### 2. Asset Injection Failed (`AssetInjectionStep`)

**Error Details Structure:**
```json
{
  "error_type": "asset_injection_failed",
  "phase": "asset_injection",
  "message": "Failed to download asset from S3"
}
```

#### 3. Setup Command Failed (`SetupCommandsStep`)

**Error Details Structure:**
```json
{
  "error_type": "setup_command_failed",
  "phase": "setup_commands",
  "command_name": "Compile Calculator.java",
  "failed_command": {
    "command": "javac Calculator.java",
    "exit_code": 1,
    "stdout": "",
    "stderr": "Calculator.java:4: error: ';' expected..."
  }
}
```

## Migration Guide

### For API Consumers

The legacy `PRE_FLIGHT` step has been replaced by `FileCheckStep`, `AssetInjectionStep`, and `SetupCommandsStep`. API consumers should update their logic to check for any of these steps when identifying setup failures.

**Before:**
```python
if failed_step == 'PRE_FLIGHT':
    # handle error
```

**After:**
```python
setup_steps = ['FileCheckStep', 'AssetInjectionStep', 'SetupCommandsStep']
if failed_step in setup_steps:
    # handle error
```

## See Also

- [API Documentation](../API.md)
- [Core Structures](core_structures.md)
- [Pipeline README](../pipeline/README.md)
