"""One-submission Actions adapter; credentials never enter grading identity."""
import json
import logging
from pathlib import Path

from autograder.autograder import build_pipeline
from autograder.models.contracts.definition import compile_definition, compile_snapshot, select_language
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.dataclass.submission import Submission
from github_action.cloud_client import CloudClient
from github_action.cloud_exporter import CloudPublisher


logger = logging.getLogger(__name__)


class GithubActionService:
    def __init__(self):
        self.host = None
        self.publisher = None
        self.language = None
        self.locale = "en"
        self.assignment_id = "local"

    def configure(self, *, definition_path, execution_mode, grading_config_id,
                  cloud_url, cloud_token, upload_to_cloud, language, locale, grading_config_revision=None):
        client = None
        config = None
        if execution_mode == "external" or upload_to_cloud:
            client = CloudClient(cloud_url, cloud_token)
        if execution_mode == "external" or (upload_to_cloud and grading_config_revision is None):
            # Reading a configuration needs the integration scope.
            config = client.get_grading_config(grading_config_id)
        if execution_mode == "external":
            # A cloud configuration is a stored canonical snapshot.
            compiled = compile_snapshot(config["definition"])
        else:
            with Path(definition_path).open(encoding="utf-8") as handle:
                compiled = compile_definition(json.load(handle))
        self.language = select_language(compiled.definition, language)
        self.locale = locale
        provenance = DefinitionProvenance(definition_hash=compiled.definition_hash)
        if config is not None:
            if config["definition_hash"] != compiled.definition_hash:
                raise ValueError("Local definition does not match the selected cloud revision.")
            self.assignment_id = str(config["id"])
            provenance = DefinitionProvenance(
                definition_hash=compiled.definition_hash,
                reference=self.assignment_id, revision=config["version"],
            )
        elif upload_to_cloud:
            # A restricted attestation credential cannot read configurations: the
            # workflow names the revision and the server verifies hash and revision.
            self.assignment_id = str(grading_config_id)
            provenance = DefinitionProvenance(
                definition_hash=compiled.definition_hash,
                reference=self.assignment_id, revision=grading_config_revision,
            )
        if upload_to_cloud:
            self.publisher = CloudPublisher(client, int(self.assignment_id), compiled.definition)
        from execution_host.docker import DockerHost
        self.host = DockerHost.from_environment()
        return build_pipeline(definition=compiled, locale=locale, provenance=provenance,
                              capabilities=self.host.capabilities)

    def run_autograder(self, pipeline, identity, submission_files):
        submission = Submission(
            username=identity.submitter_name, user_id=identity.submitter_id, assignment_id=self.assignment_id,
            submission_files=submission_files, language=self.language, locale=self.locale,
        )
        try:
            return pipeline.run(submission).outcome
        finally:
            if self.host is not None:
                try:
                    self.host.close()
                except Exception:
                    logger.exception("Actions host cleanup failed after grading")

    def delivery_payload(self, outcome, identity, provenance):
        if self.publisher is None:
            return None
        return self.publisher.payload(outcome, identity, provenance)

    def publish(self, payload):
        return self.publisher.publish(payload)
