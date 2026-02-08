from enum import Enum


class Language(Enum):
    PYTHON = ("python", "sandbox-py:latest")
    JAVA = ("java", "sandbox-java:latest")
    NODE = ("node", "sandbox-node:latest")
    CPP = ("cpp", "sandbox-cpp:latest")

    def __new__(cls, value, image):
        obj = object.__new__(cls)
        obj._value_ = value
        obj.image = image
        return obj

class SandboxState(Enum):
    IDLE = "idle"
    BUSY = "busy"
    STOPPED = "stopped"

