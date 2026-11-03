"""The one canonical declaration of supported submission languages.

A language is a domain identifier only. It carries no Docker image, command or
parser: hosts map it to a runtime profile (``sandbox_config.yml`` ``runtimes``),
execution evaluators choose their commands, and analysis implementations choose
grammars from the files they inspect. JSON contracts, submission binding and
outcome serialization all derive from this declaration.
"""
from enum import Enum
from typing import Literal


class Language(Enum):
    """Supported submission language; the value is the stable wire identifier."""
    PYTHON = "python"
    JAVA = "java"
    NODE = "node"
    CPP = "cpp"
    C = "c"


#: Wire identifiers in declaration order.
LANGUAGE_IDS: tuple[str, ...] = tuple(language.value for language in Language)

#: JSON/Pydantic type of a wire identifier, derived from :class:`Language`.
LanguageId = Literal[LANGUAGE_IDS]  # type: ignore[valid-type]
