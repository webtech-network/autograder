"""
Port (Adapter Interface) Module.

This module defines the Port abstract base class, which serves as the
interface between external systems (API, GitHub Actions, CLI) and the core
autograding logic.

Architecture Pattern:
    This implements the Ports and Adapters (Hexagonal Architecture) pattern.
    The Port is the "inbound port" - the interface through which external
    systems communicate with the core autograder.

Design:
    - Port: Abstract interface defining required methods
    - Adapters: Concrete implementations (API, GitHub, CLI)
    - Core: Autograder facade (doesn't know about adapters)

This design allows the autograder core to remain environment-agnostic and
easily testable, while supporting multiple deployment contexts.
"""

from abc import ABC, abstractmethod

from autograder.autograder_facade import Autograder
from connectors.models.assignment_config import AssignmentConfig


class Port(ABC):
    """
    Abstract Port class defining the interface for autograder adapters.

    This class defines the contract that all adapters must implement to
    communicate with the core autograding system. It follows the Adapter
    pattern from the Hexagonal Architecture.

    Workflow:
        1. Adapter receives input from external system (HTTP request, GitHub event)
        2. Adapter calls create_request() to build AutograderRequest
        3. Adapter calls run_autograder() to execute grading
        4. Adapter calls export_results() to format output for external system

    Attributes:
        autograder_request (AutograderRequest): Input request object
        autograder_response (AutograderResponse): Output response object

    Concrete Implementations:
        - ApiAdapter: REST API interface
        - GithubAdapter: GitHub Actions integration
        - CliAdapter: Command-line interface (future)

    Example Implementation:
        >>> class MyAdapter(Port):
        ...     def create_request(self, ...):
        ...         # Convert external input to AutograderRequest
        ...         self.autograder_request = AutograderRequest(...)
        ...
        ...     def export_results(self):
        ...         # Convert AutograderResponse to external format
        ...         return {"score": self.autograder_response.final_score}
    """

    def __init__(self):
        """
        Initialize the port with empty request/response.

        These will be populated during the grading workflow:
        - autograder_request: Set by create_request()
        - autograder_response: Set by run_autograder()
        """
        self.autograder_request = None
        self.autograder_response = None

    def run_autograder(self):
        """
        Execute the autograding pipeline with the current request.

        This method:
        1. Validates that create_request() has been called
        2. Invokes the core Autograder.grade() method
        3. Stores the response for later export
        4. Returns self for method chaining

        Returns:
            Port: self (for method chaining)

        Raises:
            Exception: If grading fails or request is invalid

        Example:
            >>> adapter.create_request(...)
            >>> adapter.run_autograder()
            >>> results = adapter.export_results()
        """
        try:
            # Call the core autograder facade
            response = Autograder.grade(self.autograder_request)
            self.autograder_response = response
            return self
        except Exception as e:
            raise Exception(f"Error running autograder: {e}") from e

    @abstractmethod
    def export_results(self):
        """
        Export grading results in adapter-specific format.

        This method must be implemented by concrete adapters to convert the
        AutograderResponse into the format expected by the external system.

        Returns:
            Adapter-specific format:
                - ApiAdapter: JSON response for HTTP
                - GithubAdapter: Markdown comment for GitHub
                - CliAdapter: Pretty-printed console output

        Example Implementation:
            >>> def export_results(self):
            ...     return {
            ...         "score": self.autograder_response.final_score,
            ...         "feedback": self.autograder_response.feedback,
            ...         "status": self.autograder_response.status
            ...     }
        """
        pass

    @abstractmethod
    def create_request(
        self,
        submission_files,
        assignment_config: AssignmentConfig,
        student_name,
        student_credentials,
        feedback_mode="default",
        openai_key=None,
        redis_url=None,
        redis_token=None,
    ):
        """
        Create an AutograderRequest from adapter-specific inputs.

        This method must be implemented by concrete adapters to convert
        their input format into a standardized AutograderRequest object.

        Args:
            submission_files: Student's submitted files
                Format depends on adapter (file objects, dict, URLs, etc.)

            assignment_config (AssignmentConfig): Grading configuration

            student_name: Student identifier

            student_credentials (optional): Additional authentication

            feedback_mode (str): "default" or "AI"
                Default: "default"

            openai_key (str, optional): API key for AI feedback

            redis_url (str, optional): Redis caching URL

            redis_token (str, optional): Redis authentication

        Side Effects:
            Sets self.autograder_request with the created request object

        Example Implementation:
            >>> def create_request(self, submission_files, ...):
            ...     # Convert adapter-specific format to dict
            ...     files_dict = self._process_files(submission_files)
            ...
            ...     # Create request object
            ...     self.autograder_request = AutograderRequest(
            ...         submission_files=files_dict,
            ...         assignment_config=assignment_config,
            ...         student_name=student_name,
            ...         ...
            ...     )
        """
        pass
