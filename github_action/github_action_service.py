"""One-submission Actions adapter; credentials never enter grading identity."""
import json
import logging
from pathlib import Path

from autograder.autograder import build_pipeline
from autograder.models.contracts.definition import compile_definition, select_language
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
                  cloud_url, cloud_token, upload_to_cloud, language, locale):
        client = None
        config = None
        if execution_mode == "external" or upload_to_cloud:
            client = CloudClient(cloud_url, cloud_token)
            config = client.get_grading_config(grading_config_id)
        if execution_mode == "external":
            value = config["definition"]
        else:
            with Path(definition_path).open(encoding="utf-8") as handle:
                value = json.load(handle)
        compiled = compile_definition(value)
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
        if upload_to_cloud:
            self.publisher = CloudPublisher(client, config["id"], compiled.definition)
        from execution_host.docker import DockerHost
        self.host = DockerHost.from_environment()
        return build_pipeline(definition=compiled, locale=locale, provenance=provenance,
                              capabilities=self.host.capabilities)

    def run_autograder(self, pipeline, user_name, submission_files):
        submission = Submission(
            username=user_name, user_id=user_name, assignment_id=self.assignment_id,
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

    def delivery_payload(self, outcome, user_name):
        if self.publisher is None:
            return None
        return self.publisher.payload(outcome, user_name)

    def publish(self, payload):
        return self.publisher.publish(payload)
