from abc import ABC, abstractmethod

class Template(ABC):

    @property
    @abstractmethod
    def template_name(self) -> str:
        pass
    @property
    @abstractmethod
    def template_description(self) -> str:
        pass

    