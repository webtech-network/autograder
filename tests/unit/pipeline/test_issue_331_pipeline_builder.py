"""Pipeline selects resources from an already validated definition."""
from autograder.autograder import build_pipeline
from autograder.models.dataclass.step_result import StepName
from tests.unit.pipeline.test_terminal_outcome import definition, submission


def test_static_pipeline_has_no_sandbox_or_preparation():
    pipeline = build_pipeline(definition=definition())
    execution = pipeline.run(submission())
    assert StepName.GRADE in execution.planned_steps
    assert StepName.SANDBOX not in execution.planned_steps
    assert StepName.PRE_FLIGHT not in execution.planned_steps


def test_io_pipeline_requires_sandbox():
    value = {'schema_version':'1.0','templates':['input_output'],'languages':['python'],
             'criteria':{'base':{'weight':100,'tests':[{'id':'runs','type':'dont_fail','name':'Runs',
                'parameters':{'program_command':'python main.py'}}]}}}
    pipeline = build_pipeline(definition=value)
    execution = pipeline.run(submission())
    assert StepName.SANDBOX in execution.planned_steps
    assert StepName.PRE_FLIGHT not in execution.planned_steps


def test_language_specific_preparation_is_installed():
    value = definition(preparation={'languages':{'python':{'required_files':['main.py']}}})
    assert StepName.PRE_FLIGHT not in build_pipeline(definition=value).run(submission()).planned_steps


def test_public_builder_does_not_accept_exporter_configuration():
    import pytest
    with pytest.raises(TypeError):
        build_pipeline(definition=definition(), export_results=True)
