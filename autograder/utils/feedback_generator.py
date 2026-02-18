"""Utility for generating human-readable feedback from pipeline execution."""

from typing import Dict, Any


def generate_preflight_feedback(pipeline_execution_summary: Dict[str, Any]) -> str:
    """
    Generate human-readable feedback for preflight failures.

    Args:
        pipeline_execution_summary: Pipeline execution summary dict

    Returns:
        Markdown-formatted feedback string
    """
    # Find the failed preflight step
    preflight_step = None
    for step in pipeline_execution_summary.get("steps", []):
        if step["name"] == "PreFlightStep" and step["status"] == "fail":
            preflight_step = step
            break

    if not preflight_step:
        return "## Preflight Check Failed\n\nYour submission failed during the preflight phase."

    error_details = preflight_step.get("error_details", {})
    error_type = error_details.get("error_type", "unknown")

    feedback = "## Preflight Check Failed\n\n"
    feedback += "Your submission failed during the setup phase before grading could begin.\n\n"

    if error_type == "required_file_missing":
        missing_file = error_details.get("missing_file", "unknown file")
        feedback += f"### Required File Missing\n\n"
        feedback += f"**Missing:** {missing_file}\n\n"
        feedback += "**What to do:**\n"
        feedback += f"- Make sure you upload a file named exactly **`{missing_file}`**\n"
        feedback += "- Check for typos in the filename (case-sensitive)\n"
        feedback += "- Verify the file is included in your submission\n"
        feedback += "- Resubmit with all required files\n"

    elif error_type == "setup_command_failed":
        failed_cmd = error_details.get("failed_command", {})
        cmd_name = error_details.get("command_name", "Setup command")
        command = failed_cmd.get("command", "")
        exit_code = failed_cmd.get("exit_code", "unknown")
        stderr = failed_cmd.get("stderr", "")
        stdout = failed_cmd.get("stdout", "")

        feedback += f"### Setup Command Failed: {cmd_name}\n\n"

        if command:
            feedback += f"**Command executed:**\n```bash\n{command}\n```\n\n"

        feedback += f"**Exit code:** {exit_code}\n\n"

        if stderr:
            feedback += "**Error output:**\n```\n"
            feedback += stderr
            feedback += "\n```\n\n"

        if stdout:
            feedback += "**Output:**\n```\n"
            feedback += stdout
            feedback += "\n```\n\n"

        # Add specific guidance for compilation errors
        if "javac" in command and "error:" in stderr:
            feedback += "**What to do:**\n"
            feedback += "- Fix the compilation errors shown above\n"
            feedback += "- Pay attention to the line numbers and error messages\n"
            feedback += "- Common issues: missing semicolons, undefined variables, syntax errors\n"
            feedback += "- Resubmit after fixing all compilation errors\n"
        elif "g++" in command or "gcc" in command:
            feedback += "**What to do:**\n"
            feedback += "- Fix the compilation/linking errors shown above\n"
            feedback += "- Check for syntax errors and missing includes\n"
            feedback += "- Verify all required files are present\n"
            feedback += "- Resubmit after fixing the errors\n"
        else:
            feedback += "**What to do:**\n"
            feedback += "- Review the error output above\n"
            feedback += "- Fix any issues in your code or configuration\n"
            feedback += "- Resubmit after resolving the error\n"
    else:
        feedback += "**What to do:**\n"
        feedback += "- Review the error message\n"
        feedback += "- Contact your instructor if you need help\n"
        feedback += "- Resubmit after fixing the issue\n"

    return feedback

