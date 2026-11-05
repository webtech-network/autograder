"""The one closed declaration of supported feedback locales.

Every boundary (``Submission``, HTTP and the GitHub Action) accepts a locale
through :func:`parse_locale` and nothing else. Each locale has one shipped
catalog in ``autograder/translations``; no value ever becomes a file path.
"""
from enum import StrEnum
from typing import Literal


class Locale(StrEnum):
    """Supported locale; the value is the stable wire identifier."""
    EN = "en"
    PT_BR = "pt-br"


#: Wire identifiers in declaration order.
LOCALE_IDS: tuple[str, ...] = tuple(locale.value for locale in Locale)

#: JSON/Pydantic type of a wire identifier, derived from :class:`Locale`.
LocaleId = Literal[LOCALE_IDS]  # type: ignore[valid-type]

DEFAULT_LOCALE = Locale.EN


def parse_locale(value: object) -> Locale:
    """Return the supported locale for ``value``; case and ``_``/``-`` are not significant."""
    normalized = value.lower().replace("_", "-") if isinstance(value, str) else None
    if normalized in LOCALE_IDS:
        return Locale(normalized)
    raise ValueError(f"Unsupported locale. Supported locales are: {', '.join(LOCALE_IDS)}")
