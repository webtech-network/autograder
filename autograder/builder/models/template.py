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

    def get_tests(self):
        return self.tests




    