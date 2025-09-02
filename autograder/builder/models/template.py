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

    def get_tests(self):
        return self.tests




    