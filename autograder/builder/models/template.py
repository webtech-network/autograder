from abc import ABC, abstractmethod

class Template(ABC):

    @property
    @abstractmethod
    def name(self) -> str:
        pass
    #@property
    #@abstractmethod
    #def description(self) -> str:
        pass

    