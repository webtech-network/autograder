"""Both configuration sources bind the same validated definition and language."""
import json
from unittest.mock import MagicMock, patch

import pytest

from autograder.models.contracts.definition import compile_definition
from github_action.github_action_service import GithubActionService


def definition(languages=None):
    return {"schema_version": "1.0", "templates": ["webdev"], "languages": languages or ["node"],
            "criteria": {"base": {"weight": 100, "tests": [{"id": "file", "type": "check_project_structure",
                "name": "HTML entry", "parameters": {"expected_structure": "index.html"}}]}}}


def configure(service, path, **kwargs):
    options = dict(definition_path=path, execution_mode="repo", grading_config_id=None,
                   cloud_url=None, cloud_token=None, upload_to_cloud=False, language=None, locale="pt-br")
    options.update(kwargs)
    return service.configure(**options)


def test_repo_mode_selects_single_language_and_locale_without_github_or_secrets(tmp_path):
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(definition()))
    service = GithubActionService()
    with patch("github_action.github_action_service.build_pipeline") as build:
        configure(service, path)
    assert service.language.value == "node"
    assert service.locale == "pt-br"
    assert build.call_args.kwargs["definition"].definition.templates == ["webdev"]
    assert build.call_args.kwargs["locale"] == "pt-br"
    pipeline = MagicMock()
    service.run_autograder(pipeline, "alice", {})
    submission = pipeline.run.call_args.args[0]
    assert submission.user_id == "alice"
    assert submission.assignment_id == "local"
    assert submission.locale == "pt-br"


def test_repo_mode_requires_explicit_multilanguage_selection(tmp_path):
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(definition(["python", "node"])))
    with pytest.raises(ValueError):
        configure(GithubActionService(), path)


def test_external_source_does_not_imply_publication(tmp_path):
    compiled = compile_definition(definition())
    config = {"id": 7, "definition": definition(), "definition_hash": compiled.definition_hash, "version": 4}
    service = GithubActionService()
    with patch("github_action.github_action_service.CloudClient") as client, patch("github_action.github_action_service.build_pipeline") as build:
        client.return_value.get_grading_config.return_value = config
        configure(service, tmp_path / "unused", execution_mode="external", grading_config_id=7,
                  cloud_url="https://cloud.invalid", cloud_token="secret")
    assert service.publisher is None
    provenance = build.call_args.kwargs["provenance"]
    assert provenance.reference == "7"
    assert provenance.revision == 4
    assert provenance.definition_hash == compiled.definition_hash


def test_local_cloud_publication_requires_matching_revision(tmp_path):
    path = tmp_path / "definition.json"
    path.write_text(json.dumps(definition()))
    with patch("github_action.github_action_service.CloudClient") as client:
        client.return_value.get_grading_config.return_value = {"id": 7, "definition_hash": "0" * 64, "version": 1}
        with pytest.raises(ValueError, match="does not match"):
            configure(GithubActionService(), path, upload_to_cloud=True, grading_config_id=7,
                      cloud_url="https://cloud.invalid", cloud_token="secret")
