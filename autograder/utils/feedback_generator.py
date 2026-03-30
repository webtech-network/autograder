"""Utility for generating human-readable feedback from pipeline execution."""

from typing import Dict, Any, Optional
from autograder.translations import t


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

    # Extract locale from summary if available, fallback to 'en'
    # The summary structure usually contains submission details
    submission = pipeline_execution_summary.get("submission", {})
    locale = submission.get("locale", "en")

    if not preflight_step:
        return t("feedback.preflight.failed_title", locale=locale) + "\n\n" + t("feedback.preflight.failed_subtitle", locale=locale)

    error_details = preflight_step.get("error_details", {})
    error_type = error_details.get("error_type", "unknown")

    feedback = t("feedback.preflight.failed_title", locale=locale) + "\n\n"
    feedback += t("feedback.preflight.failed_subtitle", locale=locale)

    if error_type == "required_file_missing":
        missing_file = error_details.get("missing_file", "unknown file")
        feedback += f"{t('feedback.preflight.required_file_missing_header', locale=locale)}\n\n"
        feedback += f"{t('feedback.preflight.missing_label', locale=locale, missing_file=missing_file)}\n\n"
        feedback += f"{t('feedback.preflight.what_to_do', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.upload_instruction', locale=locale, missing_file=missing_file)}\n"
        feedback += f"{t('feedback.preflight.typo_instruction', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.verify_instruction', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.resubmit_instruction', locale=locale)}\n"

    elif error_type == "setup_command_failed":
        failed_cmd = error_details.get("failed_command", {})
        cmd_name = error_details.get("command_name", "Setup command")
        command = failed_cmd.get("command", "")
        exit_code = failed_cmd.get("exit_code", "unknown")
        stderr = failed_cmd.get("stderr", "")
        stdout = failed_cmd.get("stdout", "")

        feedback += f"{t('feedback.preflight.setup_command_failed_header', locale=locale, command_name=cmd_name)}\n\n"

        if command:
            feedback += f"{t('feedback.preflight.command_executed_label', locale=locale)}\n```bash\n{command}\n```\n\n"

        feedback += f"{t('feedback.preflight.exit_code_label', locale=locale, exit_code=exit_code)}\n\n"

        if stderr:
            feedback += f"{t('feedback.preflight.error_output_label', locale=locale)}\n```\n"
            feedback += stderr
            feedback += "\n```\n\n"

        if stdout:
            feedback += f"{t('feedback.preflight.output_label', locale=locale)}\n```\n"
            feedback += stdout
            feedback += "\n```\n\n"

        # Add specific guidance for compilation errors
        if "javac" in command and "error:" in stderr:
            feedback += f"{t('feedback.preflight.what_to_do', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.compilation_fix_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.line_number_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.common_issues_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.compilation_resubmit_instruction', locale=locale)}\n"
        elif "g++" in command or "gcc" in command:
            feedback += f"{t('feedback.preflight.what_to_do', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.gpp_fix_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.gpp_syntax_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.gpp_verify_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.gpp_resubmit_instruction', locale=locale)}\n"
        else:
            feedback += f"{t('feedback.preflight.what_to_do', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.review_error_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.generic_fix_instruction', locale=locale)}\n"
            feedback += f"{t('feedback.preflight.generic_resubmit_instruction', locale=locale)}\n"
    else:
        feedback += f"{t('feedback.preflight.what_to_do', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.generic_error_instruction', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.contact_instructor_instruction', locale=locale)}\n"
        feedback += f"{t('feedback.preflight.generic_resubmit_instruction', locale=locale)}\n"

    return feedback

