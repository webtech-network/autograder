"""Offline migration of historical integration fixtures, never production aliases."""
from autograder.autograder import build_pipeline
from autograder.services.definition_migration import convert_legacy_definition


def build_migrated_fixture_pipeline(*, template_name, include_feedback, grading_criteria,
                                    feedback_config, setup_config=None, languages=None):
    definition = convert_legacy_definition({
        "template_name": template_name, "languages": languages or ["python", "java"],
        "grading_criteria": grading_criteria, "include_feedback": include_feedback,
        "feedback_config": feedback_config or {}, "setup_config": setup_config or {},
    })
    from sandbox_manager.manager import get_sandbox_manager
    from execution_host.docker import docker_capabilities
    return build_pipeline(definition=definition, capabilities=docker_capabilities(get_sandbox_manager()))
