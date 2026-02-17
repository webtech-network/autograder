# Pipeline Execution Tracking

## Overview

As of February 2026, the autograder now provides comprehensive pipeline execution tracking in all submission responses. This gives complete transparency into the grading process, especially useful for debugging and understanding preflight failures.

## What Changed

### New API Response Fields

Every submission response now includes a `pipeline_execution` field that contains:

- Execution status and timing
- All executed pipeline steps
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
    "total_steps_planned": 7,
    "steps_completed": 7,
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
        "name": "PRE_FLIGHT",
        "status": "success",
        "message": "All preflight checks passed"
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

### Response When Preflight Fails

```json
{
  "id": 11,
  "status": "failed",
  "final_score": 0,
  
  "feedback": "## Preflight Check Failed\n\nYour submission failed during the setup phase before grading could begin.\n\n### Setup Command Failed: Compile Calculator.java\n\n**Command executed:**\n```bash\njavac Calculator.java\n```\n\n**Exit code:** 1\n\n**Error output:**\n```\nCalculator.java:4: error: ';' expected\n        Scanner sc = new Scanner(System.in)\n                                           ^\n1 error\n```\n\n**What to do:**\n- Fix the compilation errors shown above\n- Pay attention to the line numbers and error messages\n- Common issues: missing semicolons, undefined variables, syntax errors\n- Resubmit after fixing all compilation errors\n",
  
  "result_tree": null,
  
  "pipeline_execution": {
    "status": "failed",
    "failed_at_step": "PRE_FLIGHT",
    "total_steps_planned": 7,
    "steps_completed": 3,
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
        "name": "PRE_FLIGHT",
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

### Check for Preflight Failures

```python
def check_preflight_status(submission):
    """Check if submission failed during preflight."""
    pipeline = submission.get('pipeline_execution', {})
    
    if pipeline.get('failed_at_step') == 'PRE_FLIGHT':
        print("Preflight check failed!")
        
        # Get error details
        for step in pipeline.get('steps', []):
            if step['name'] == 'PRE_FLIGHT' and step['status'] == 'fail':
                error_details = step.get('error_details', {})
                
                if error_details.get('error_type') == 'setup_command_failed':
                    cmd = error_details.get('failed_command', {})
                    print(f"Command failed: {cmd.get('command')}")
                    print(f"Exit code: {cmd.get('exit_code')}")
                    print(f"Error: {cmd.get('stderr')}")
                
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

### Aggregate Statistics

```python
def get_failure_statistics(submissions):
    """Analyze where submissions are failing."""
    stats = {
        'total': len(submissions),
        'preflight_failures': 0,
        'grading_failures': 0,
        'compilation_errors': 0,
        'missing_files': 0,
    }
    
    for sub in submissions:
        pipeline = sub.get('pipeline_execution', {})
        
        if pipeline.get('status') == 'failed':
            failed_step = pipeline.get('failed_at_step')
            
            if failed_step == 'PRE_FLIGHT':
                stats['preflight_failures'] += 1
                
                # Get error type
                for step in pipeline.get('steps', []):
                    if step['name'] == 'PRE_FLIGHT':
                        error_type = step.get('error_details', {}).get('error_type')
                        if error_type == 'setup_command_failed':
                            stats['compilation_errors'] += 1
                        elif error_type == 'required_file_missing':
                            stats['missing_files'] += 1
            else:
                stats['grading_failures'] += 1
    
    return stats
```

## Error Types

### Preflight Errors

#### 1. Required File Missing

**Error Details Structure:**
```json
{
  "error_type": "required_file_missing",
  "phase": "required_files",
  "missing_file": "Calculator.java"
}
```

**Generated Feedback:**
- Lists the missing file name
- Reminds about case-sensitivity
- Provides actionable steps to fix

#### 2. Setup Command Failed

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

**Generated Feedback:**
- Shows the command that was executed
- Displays exit code
- Includes full compiler/error output
- Provides language-specific guidance (Java, C++, etc.)

## Migration Guide

### For API Consumers

If you're consuming the autograder API, you should update your code to handle the new `pipeline_execution` field:

**Before:**
```python
result = get_submission(submission_id)
if result['status'] == 'failed':
    print("Submission failed")  # No details available
```

**After:**
```python
result = get_submission(submission_id)
if result['status'] == 'failed':
    # Check what went wrong
    pipeline = result.get('pipeline_execution', {})
    failed_step = pipeline.get('failed_at_step')
    
    if failed_step == 'PRE_FLIGHT':
        # Show the detailed preflight error from feedback
        print(result.get('feedback', 'Preflight check failed'))
    else:
        print(f"Failed at step: {failed_step}")
```

### Database Changes

A new column `pipeline_execution` (JSON type) was added to the `submission_results` table.

**Migration:**
```bash
alembic upgrade head
```

This migration is backward compatible - existing submissions will have `pipeline_execution: null`.

## Best Practices

### For Students

1. **Read the Feedback**: The `feedback` field now contains detailed, human-readable error messages
2. **Check Compilation First**: If you see "Preflight Check Failed", fix compilation errors before resubmitting
3. **Verify File Names**: Case-sensitive file name checks happen in preflight

### For Instructors

1. **Monitor Preflight Failures**: High preflight failure rates may indicate unclear instructions
2. **Use Error Statistics**: Aggregate `pipeline_execution` data to identify common student issues
3. **Customize Feedback**: Consider the auto-generated feedback when designing rubrics

### For Developers

1. **Always Check `pipeline_execution`**: Even successful submissions include execution details
2. **Parse Error Details**: The `error_details` object provides machine-readable error information
3. **Display Execution Time**: Help users understand performance characteristics

## FAQ

### Q: Will `result_tree` ever be populated if preflight fails?
**A:** No. If preflight fails, `result_tree` will always be `null` because grading never occurred.

### Q: Is `pipeline_execution` always present?
**A:** Yes, for all new submissions. Old submissions (before this feature) will have `pipeline_execution: null`.

### Q: Can I disable pipeline execution tracking?
**A:** No, it's always included. It adds minimal overhead and provides valuable debugging information.

### Q: What if a step is skipped?
**A:** Skipped steps don't appear in the `steps` array. Only executed steps are included.

### Q: How do I know if compilation failed?
**A:** Check if `failed_at_step == "PRE_FLIGHT"` and look for `error_type: "setup_command_failed"` in the error details.

## See Also

- [API Documentation](API.md)
- [Core Structures](core_structures.md)
- [Setup Config Feature](setup_config_feature.md)
- [Named Setup Commands](NAMED_SETUP_COMMANDS.md)

