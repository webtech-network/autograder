"""
Autograder Request Model.

This module defines the AutograderRequest class, which encapsulates all
information needed to grade a student submission. This is the primary input
to the autograding system and follows the Command pattern.

The request object is created by adapters (API, GitHub Actions) and passed
to the core autograding system through the Port interface.
"""

from connectors.models.assignment_config import AssignmentConfig


class AutograderRequest:
    """
    Complete request object for autograding a student submission.

    This class encapsulates all the data needed to grade a student's work,
    including their submitted files, grading configuration, student information,
    and optional services (AI feedback, caching).

    Attributes:
        submission_files (dict): Mapping of filename -> file content
            Example: {"index.html": "<html>...</html>", "style.css": "body {...}"}

        assignment_config (AssignmentConfig): Complete grading configuration including:
            - template: Which test template to use (web_dev, python, api, etc.)
            - criteria: Hierarchical grading rubric
            - feedback: Feedback customization settings
            - setup: Pre-flight commands to run

        student_name (str): Student identifier (name, email, GitHub username, etc.)

        student_credentials (str, optional): Additional authentication/identification
            Not currently used but available for future extensions

        include_feedback (bool): Whether to generate detailed feedback
            Default: False (only return score)

        feedback_mode (str): Type of feedback generation
            Options: "default" (rule-based) or "AI" (OpenAI-powered)
            Default: "default"

        openai_key (str, optional): OpenAI API key for AI-powered feedback
            Required if feedback_mode is "AI"

        redis_url (str, optional): Redis instance URL for caching
            Example: "redis://localhost:6379"
            Improves performance for repeated grading

        redis_token (str, optional): Authentication token for Redis
            Required if Redis instance requires authentication

    Usage:
        >>> config = AssignmentConfig(template="web_dev", criteria={...})
        >>> request = AutograderRequest(
        ...     submission_files={"index.html": "..."},
        ...     assignment_config=config,
        ...     student_name="alice@example.com",
        ...     include_feedback=True,
        ...     feedback_mode="AI",
        ...     openai_key="sk-..."
        ... )
        >>> response = Autograder.grade(request)
    """

    def __init__(
        self,
        submission_files: dict,
        assignment_config: AssignmentConfig,
        student_name,
        student_credentials=None,
        include_feedback=False,
        feedback_mode="default",
        openai_key=None,
        redis_url=None,
        redis_token=None,
    ):
        """
        Initialize an AutograderRequest.

        Args:
            submission_files: Mapping of filename to file content.
            assignment_config: Complete grading configuration.
            student_name: Student identifier.
            student_credentials: Optional authentication/identification.
            include_feedback: Whether to generate detailed feedback.
            feedback_mode: Type of feedback ("default" or "AI").
            openai_key: OpenAI API key for AI-powered feedback.
            redis_url: Redis instance URL for caching.
            redis_token: Authentication token for Redis.
        """
        self.submission_files = submission_files
        self.assignment_config = assignment_config
        self.student_name = student_name
        self.student_credentials = student_credentials
        self.include_feedback = include_feedback
        self.feedback_mode = feedback_mode
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token

    def __str__(self):
        """Return string representation of the autograder request."""
        stri = f"{len(self.submission_files)} submission files.\n"
        stri += f"Assignment config: {self.assignment_config}\n"
        stri += f"Student name: {self.student_name}\n"
        stri += f"Feedback mode: {self.feedback_mode}\n"
        return stri
