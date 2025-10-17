"""Context module."""

from connectors.models.autograder_request import AutograderRequest


class RequestContext:
    """
    A Singleton class to hold the active AutograderRequest object.
    This provides a global point of access to request data, avoiding the need
    to pass the request object through multiple layers of the application.
    """

    _instance = None

    @classmethod
    def get_instance(cls):
        """Gets the single instance of the class."""
        if cls._instance is None:
            cls._instance = cls.__new__(cls)
            cls._instance.request = None
        return cls._instance

    def set_request(self, autograder_request: AutograderRequest):
        """Sets the active autograder request for the current session."""
        self.request = autograder_request

    def get_request(self):
        """Gets the active autograder request."""
        if self.request is None:
            raise Exception(
                "RequestContext has not been initialized. Call set_request() first."
            )
        return self.request


# Create a globally accessible instance
request_context = RequestContext.get_instance()
