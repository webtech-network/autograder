"""Look up localized strings in the catalogs shipped for the supported locales.

Catalogs are named by the closed :class:`~autograder.models.locale.Locale` set
and loaded once at import; a caller's locale only selects one of them. Keys use
dot-notation for nested catalogs, e.g. ``web_dev.html.check_head.description``.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from autograder.models.locale import DEFAULT_LOCALE, Locale, parse_locale

logger = logging.getLogger(__name__)

_CATALOG_DIR = Path(__file__).resolve().parent
_CATALOGS: Dict[Locale, Dict[str, Any]] = {
    locale: json.loads((_CATALOG_DIR / f"{locale.value.replace('-', '_')}.json").read_text(encoding="utf-8-sig"))
    for locale in Locale
}


def _get_nested_value(catalog: Dict[str, Any], key: str) -> Optional[str]:
    """Return a flat key, or the string reached by following a dot-separated key."""
    if isinstance(catalog.get(key), str):
        return catalog[key]
    current: Any = catalog
    for part in key.split('.'):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current if isinstance(current, str) else None


def t(key: str, locale: Optional[str] = None, **kwargs) -> str:
    """Translate ``key`` into a supported locale (default English).

    An unsupported locale raises ``ValueError``; it is never replaced by the
    default. A key missing from a non-default catalog uses the default catalog,
    and a key missing everywhere returns the key itself.
    """
    target = DEFAULT_LOCALE if locale is None else parse_locale(locale)
    message = _get_nested_value(_CATALOGS[target], key)
    if message is None and target is not DEFAULT_LOCALE:
        message = _get_nested_value(_CATALOGS[DEFAULT_LOCALE], key)
    if message is None:
        logger.warning("Translation key not found: '%s' (locale: %s)", key, target.value)
        return key
    try:
        return message.format(**kwargs)
    except (AttributeError, IndexError, KeyError, ValueError) as exc:
        logger.error("Could not format message '%s': %s", key, exc)
        return message
