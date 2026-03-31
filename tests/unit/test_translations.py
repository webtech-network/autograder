"""
Translation verification tests.

Checks:
1. Structural parity: every key in en.json exists in pt_br.json (and vice-versa).
2. Format-string parity: {placeholders} match between locales.
3. Key coverage: every t("key") call in Python source resolves to a leaf in en.json.
4. JSON validity and encoding: both files parse cleanly as UTF-8.
"""

import json
import os
import re
import ast
from pathlib import Path
from typing import Any, Dict, Set

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TRANSLATIONS_DIR = Path(__file__).resolve().parents[2] / "autograder" / "translations"
SOURCE_ROOT = Path(__file__).resolve().parents[2] / "autograder"

LOCALE_FILES = {
    "en": TRANSLATIONS_DIR / "en.json",
    "pt_br": TRANSLATIONS_DIR / "pt_br.json",
}

PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")


def load_catalog(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def flatten_keys(d: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Flatten nested dict into dot-separated keys → leaf string values."""
    items: Dict[str, str] = {}
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.update(flatten_keys(v, full_key))
        elif isinstance(v, str):
            items[full_key] = v
    return items


def get_placeholders(template: str) -> Set[str]:
    return set(PLACEHOLDER_RE.findall(template))


def extract_translation_keys_from_source() -> Set[str]:
    """Walk Python source files and extract all string arguments to t(...)."""
    keys: Set[str] = set()
    t_call_re = re.compile(r"""\bt\(\s*(['"])(.*?)\1""")

    for py_file in SOURCE_ROOT.rglob("*.py"):
        # skip test files — they may use t() in mocks
        rel = py_file.relative_to(SOURCE_ROOT)
        if "test" in rel.parts:
            continue
        try:
            text = py_file.read_text(encoding="utf-8")
        except Exception:
            continue
        for m in t_call_re.finditer(text):
            keys.add(m.group(2))
    return keys


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def catalogs():
    return {name: load_catalog(path) for name, path in LOCALE_FILES.items()}


@pytest.fixture(scope="module")
def flat_catalogs(catalogs):
    return {name: flatten_keys(cat) for name, cat in catalogs.items()}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestJsonValidity:
    """Ensure translation files are valid JSON / UTF-8."""

    @pytest.mark.parametrize("locale,path", list(LOCALE_FILES.items()))
    def test_json_parses(self, locale, path):
        with open(path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)  # raises on invalid JSON
        assert isinstance(data, dict), f"{locale}.json root must be an object"


class TestStructuralParity:
    """Every key in one locale must exist in the other."""

    def test_en_keys_exist_in_pt_br(self, flat_catalogs):
        en_keys = set(flat_catalogs["en"].keys())
        pt_keys = set(flat_catalogs["pt_br"].keys())
        missing = en_keys - pt_keys
        assert not missing, (
            f"{len(missing)} key(s) in en.json missing from pt_br.json:\n"
            + "\n".join(f"  - {k}" for k in sorted(missing))
        )

    def test_pt_br_keys_exist_in_en(self, flat_catalogs):
        en_keys = set(flat_catalogs["en"].keys())
        pt_keys = set(flat_catalogs["pt_br"].keys())
        extra = pt_keys - en_keys
        assert not extra, (
            f"{len(extra)} key(s) in pt_br.json missing from en.json:\n"
            + "\n".join(f"  - {k}" for k in sorted(extra))
        )


class TestPlaceholderParity:
    """Format placeholders ({name}) must match across locales."""

    def test_placeholders_match(self, flat_catalogs):
        en_flat = flat_catalogs["en"]
        pt_flat = flat_catalogs["pt_br"]
        mismatches = []
        for key in en_flat:
            if key not in pt_flat:
                continue  # structural parity test covers this
            en_ph = get_placeholders(en_flat[key])
            pt_ph = get_placeholders(pt_flat[key])
            if en_ph != pt_ph:
                mismatches.append(
                    f"  - {key}: en={sorted(en_ph)} pt_br={sorted(pt_ph)}"
                )
        assert not mismatches, (
            f"{len(mismatches)} key(s) with mismatched placeholders:\n"
            + "\n".join(mismatches)
        )


class TestSourceKeyCoverage:
    """Every t('key') in source code must resolve to a leaf in en.json."""

    def test_all_source_keys_exist(self, flat_catalogs):
        en_flat = flat_catalogs["en"]
        source_keys = extract_translation_keys_from_source()
        assert source_keys, "No translation keys found in source — extraction may be broken"

        missing = source_keys - set(en_flat.keys())
        assert not missing, (
            f"{len(missing)} translation key(s) used in code but missing from en.json:\n"
            + "\n".join(f"  - {k}" for k in sorted(missing))
        )
