from abc import ABC, abstractmethod

class ExecutionHelper(ABC):
    """
    Abstract contract for any environment that runs tests.
    """
    @abstractmethod
    def start(self):
        """Initialize resources (e.g., spin up Docker, connect to API)."""
        pass

    @abstractmethod
    def stop(self):
        """Cleanup resources (e.g., kill container)."""
        pass
    
