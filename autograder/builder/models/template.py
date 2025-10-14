from abc import ABC, abstractmethod

class Template(ABC):

    def __init__(self):
        self.tests = None
    @property
    @abstractmethod
    def template_name(self) -> str:
        pass
    @property
    @abstractmethod
    def template_description(self) -> str:
        pass

    @property
    @abstractmethod
    def requires_pre_executed_tree(self) -> bool:
        pass

    @property
    @abstractmethod
    def requires_execution_helper(self) -> bool:
        pass

    @property
    @abstractmethod
    def execution_helper(self):
        pass

    @abstractmethod
    def stop(self):
        pass
    def get_tests(self):
        return self.tests





    