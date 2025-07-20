from abc import ABC, abstractmethod



class EnginePort(ABC):
    """
    Abstract class for the Engine, which is responsible for running the tests
    and generating the standard test report output.
    """

    @abstractmethod
    def run_tests(self):
        pass

    @abstractmethod
    def normalize_output(self):
        pass

    