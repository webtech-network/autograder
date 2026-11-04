"""Locale is a closed core vocabulary; no value reaches a filesystem path."""
import builtins
import logging
from pathlib import Path

import pytest

from autograder.models.dataclass.submission import Submission
from autograder.translations.translator import t
from tests.locale_cases import ACCEPTED, REJECTED

TRANSLATIONS = Path(__file__).resolve().parents[2] / "autograder" / "translations"


def submission(locale):
    return Submission(username="u", user_id=1, assignment_id=1, submission_files={}, locale=locale)


def locale_module():
    from autograder.models import locale  # pylint: disable=import-outside-toplevel
    return locale


def test_traversal_locale_cannot_load_a_file_outside_the_catalog(monkeypatch):
    # At 3a8abcc this returned '1.0': docs/criteria_example.json was loaded and cached.
    opened = []
    real_open = builtins.open
    monkeypatch.setattr(builtins, "open", lambda file, *a, **k: opened.append(file) or real_open(file, *a, **k))
    with pytest.raises(ValueError, match="Unsupported locale"):
        t("schema_version", locale="../../docs/criteria_example")
    assert opened == []


@pytest.mark.parametrize("value", REJECTED + [None, 1, b"en", object()])
def test_unsupported_locales_are_rejected_everywhere_in_core(value, caplog):
    parse_locale = locale_module().parse_locale
    with caplog.at_level(logging.DEBUG):
        with pytest.raises((ValueError, TypeError)):
            parse_locale(value)
        with pytest.raises((ValueError, TypeError)):
            submission(value)
        if value is not None:
            # Never silently replaced by the default locale.
            with pytest.raises((ValueError, TypeError)):
                t("feedback.report_title", locale=value)
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]


@pytest.mark.parametrize(("value", "canonical"), ACCEPTED)
def test_supported_locales_normalize_once_to_the_canonical_identifier(value, canonical):
    Locale, parse_locale = locale_module().Locale, locale_module().parse_locale
    assert parse_locale(value) == canonical
    assert submission(value).locale == canonical
    assert submission(value).locale is Locale(canonical)
    assert t("feedback.report_title", locale=value) == t("feedback.report_title", locale=canonical)


def test_default_locale_and_localized_lookup():
    Locale = locale_module().Locale
    assert submission(Locale.EN).locale is Locale.EN
    assert Submission(username="u", user_id=1, assignment_id=1, submission_files={}).locale is Locale.EN
    assert t("feedback.report_title") == t("feedback.report_title", locale="en")
    assert t("feedback.report_title", locale="pt-br") != t("feedback.report_title", locale="en")


def test_the_published_set_is_exactly_the_shipped_catalogs():
    LOCALE_IDS = locale_module().LOCALE_IDS
    shipped = {path.stem.replace("_", "-") for path in TRANSLATIONS.glob("*.json")}
    assert set(LOCALE_IDS) == shipped
    assert {canonical for _, canonical in ACCEPTED} == set(LOCALE_IDS)
