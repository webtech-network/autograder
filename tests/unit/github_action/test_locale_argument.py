"""The Action accepts exactly the core locale set, with the same normalization as HTTP."""
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

from autograder.models.locale import LOCALE_IDS
from github_action import main
from tests.locale_cases import ACCEPTED, REJECTED

REPO = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(("locale", "canonical"), ACCEPTED)
def test_supported_locale_is_normalized_by_the_cli(locale, canonical):
    assert main.parser.parse_args(["--locale", locale]).locale == canonical


def test_omitted_locale_defaults_to_english():
    assert main.parser.parse_args([]).locale == "en"


@pytest.mark.parametrize("locale", REJECTED)
def test_unsupported_locale_is_an_argument_error(locale, capsys):
    with pytest.raises(SystemExit) as exit_:
        main.parser.parse_args(["--locale", locale])
    assert exit_.value.code == 2
    assert "argument --locale" in capsys.readouterr().err


def test_real_cli_rejects_traversal_before_grading(tmp_path):
    env = dict(os.environ, GITHUB_WORKSPACE=str(tmp_path), PYTHONPATH=str(REPO))
    result = subprocess.run([sys.executable, "-m", "github_action.main", "--locale", "../../docs/criteria_example"],
                            cwd=REPO, env=env, capture_output=True, text=True, timeout=60, check=False)
    assert result.returncode == 2
    assert "argument --locale" in result.stderr
    assert not (tmp_path / ".autograder").exists()


def test_action_metadata_documents_the_core_locale_set():
    description = yaml.safe_load((REPO / "action.yml").read_text())["inputs"]["locale"]["description"]
    for locale in LOCALE_IDS:
        assert locale in description
