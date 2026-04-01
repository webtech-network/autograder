import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

class Translator:
    """
    A simple translator class that manages language-specific string catalogs.
    It supports both flat string keys and nested dictionaries using dot-notation.
    Example: 'web_dev.html.check_head.description'
    """
    _instance = None
    _catalogs: Dict[str, Dict[str, Any]] = {}
    _default_locale = "en"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Translator, cls).__new__(cls)
        return cls._instance

    def _load_catalog(self, locale: str) -> Dict[str, Any]:
        """Lazy load a language catalog from the translations directory."""
        # Normalize locale (e.g., pt-br -> pt_br)
        normalized_locale = locale.replace('-', '_').lower()
        if normalized_locale in self._catalogs:
            return self._catalogs[normalized_locale]

        # Resolve absolute path to the JSON file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, f"{normalized_locale}.json")

        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                data = json.load(f)
                self._catalogs[normalized_locale] = data
                return data
        except FileNotFoundError:
            logger.error(f"Translation file not found: {json_path}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing JSON in {json_path}: {str(e)}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading translation for '{locale}': {str(e)}")
            return {}

    def _get_nested_value(self, catalog: Dict[str, Any], key: str) -> Optional[str]:
        """
        Traverse a nested catalog dictionary using a dot-separated key.
        Supports both flat keys (for backward compatibility) and nested structures.
        """
        # First, try to get the whole key as-is (flat support)
        if key in catalog and isinstance(catalog[key], str):
            return catalog[key]

        # Then, split by dot and traverse
        parts = key.split('.')
        current = catalog
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        
        # We only return it if it's a string, otherwise it's still a sub-dict path
        return current if isinstance(current, str) else None

    def translate(self, key: str, locale: Optional[str] = None, **kwargs) -> str:
        """
        Translates a key into the target locale.
        Falls back to the default locale if the key is missing.
        """
        target_locale = locale or self._default_locale
        catalog = self._load_catalog(target_locale)

        # Try to find the key in the target locale
        message = self._get_nested_value(catalog, key)

        # Fallback to default locale if not found and we're not already in default
        if message is None and target_locale != self._default_locale:
            logger.debug(f"Key '{key}' not found in '{target_locale}', falling back to '{self._default_locale}'")
            default_catalog = self._load_catalog(self._default_locale)
            message = self._get_nested_value(default_catalog, key)

        # If still not found, return the key itself as a fallback
        if message is None:
            logger.warning(f"Translation key not found: '{key}' (locale: {target_locale})")
            return key

        # Perform string formatting if kwargs are provided
        try:
            return message.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing formatting key '{e}' for message: {message}")
            return message
        except Exception as e:
            logger.error(f"Error formatting message '{key}': {str(e)}")
            return message

# Global translator instance
_translator = Translator()

def t(key: str, locale: Optional[str] = None, **kwargs) -> str:
    """Convenience function for translation."""
    return _translator.translate(key, locale=locale, **kwargs)
