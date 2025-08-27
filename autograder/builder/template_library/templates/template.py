from abc import ABC, abstractmethod

class Template(ABC):
    def __init__(self,template_name: str):
        self.template_name = template_name
