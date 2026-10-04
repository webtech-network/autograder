"""Executable shared outcome/failure matrix, using the real engine boundary."""
from copy import deepcopy
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from pydantic import ValidationError

from autograder.autograder import build_pipeline
from autograder.models.contracts.outcome import (
    CompletedOutcome, ComparisonOutcome, FeedbackOutcome, OutcomeError,
    outcome_json_schema, outcome_score_vector, validate_outcome,
)
from autograder.models.dataclass.step_result import StepName, StepResult, StepStatus
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError
from autograder.serializers.pipeline_execution_serializer import PipelineExecutionSerializer
from autograder.template_library.input_output import ExpectOutputTest
from sandbox_manager.models.sandbox_models import CommandResponse, Language, ResponseCategory


def definition(*, feedback=False, preparation=None):
    value = {
        'schema_version': '1.0', 'templates': ['static_analysis'], 'languages': ['python'],
        'criteria': {'base': {'weight': 100, 'tests': [
            {'id': 'imports', 'type': 'forbidden_import', 'name': 'Imports',
             'parameters': {'forbidden_imports': ['os']}}]}},
        'feedback': {'enabled': feedback},
    }
    if preparation:
        value['preparation'] = preparation
    return value


def submission(code='import os', language=None):
    return Submission(username='student', user_id=1, assignment_id=1, language=language,
                      submission_files={'main.py': SubmissionFile('main.py', code)})


def outcome(code='import os'):
    return build_pipeline(definition=definition()).run(submission(code)).outcome


def test_zero_is_completed_and_normalized_language_and_provenance_are_retained():
    value = outcome()
    assert isinstance(value, CompletedOutcome)
    assert value.score == 0
    assert value.language == 'python'
    assert len(value.provenance.definition_hash) == 64
    assert value.error is None
    assert value.tree.base.tests[0].parameters == {'forbidden_imports': ['os']}
    assert outcome_score_vector(value) == {'imports': 0}
    wire = value.model_dump(mode='json')
    assert wire['started_at'].endswith('Z')
    assert wire['finished_at'].endswith('Z')
    assert 'score_vector' not in wire and 'root' not in wire
    assert validate_outcome(wire) == value


@pytest.mark.parametrize('category', [ResponseCategory.COMPILATION_ERROR, ResponseCategory.RUNTIME_ERROR, ResponseCategory.TIMEOUT])
def test_student_execution_failure_is_assessed_zero(category):
    response = CommandResponse(stdout='', stderr='student error', exit_code=1, execution_time=1, category=category)
    evaluator = ExpectOutputTest()
    sandbox = Mock()
    sandbox.run_commands.return_value = response
    result = evaluator.execute([], sandbox, program_command='python main.py', expected_output='hello')
    assert result.score == 0


@pytest.mark.parametrize('failure', [ResponseCategory.SYSTEM_ERROR, RuntimeError('token=secret')])
def test_sandbox_infrastructure_failure_is_not_an_assessment(failure):
    evaluator = ExpectOutputTest()
    sandbox = Mock()
    if isinstance(failure, Exception):
        sandbox.run_commands.side_effect = failure
    else:
        sandbox.run_commands.return_value = CommandResponse(stdout='', stderr='secret', exit_code=-1, execution_time=0, category=failure)
    with pytest.raises(EvaluationError) as error:
        evaluator.execute([], sandbox, program_command='python main.py', expected_output='hello')
    assert error.value.category == 'capability'
    assert 'secret' not in error.value.message


def test_required_file_missing_has_no_grade():
    pipeline = build_pipeline(definition=definition(preparation={'languages': {'python': {'required_files': ['other.py']}}}))
    execution = pipeline.run(submission())
    assert execution.result is None
    assert execution.outcome.status == 'failed'
    assert execution.outcome.score is None and execution.outcome.tree is None
    assert execution.outcome.error.code == 'REQUIRED_FILE_MISSING'
    assert execution.outcome.error.category == 'submission'


@pytest.mark.parametrize('language,languages,code', [(Language.JAVA,['python'],'LANGUAGE_NOT_ALLOWED'), (None,['python','java'],'LANGUAGE_REQUIRED')])
def test_invalid_language_becomes_explicit_failed_outcome(language,languages,code):
    value = definition()
    value['languages'] = languages
    execution = build_pipeline(definition=value).run(submission(language=language))
    assert execution.outcome.error.code == code
    assert execution.outcome.score is None


def test_feedback_failure_preserves_completed_grade_and_sanitizes_message():
    pipeline = build_pipeline(definition=definition(feedback=True))
    with patch('autograder.services.report.reporter_service.ReporterService.generate_feedback', side_effect=RuntimeError('secret')):
        execution = pipeline.run(submission('print(1)'))
    assert execution.result.final_score == 100
    assert execution.outcome.status == 'completed'
    assert execution.outcome.score == 100
    assert execution.outcome.feedback.status == 'failed'
    assert execution.outcome.feedback.error.code == 'FEEDBACK_ERROR'
    assert 'secret' not in str(execution.outcome.model_dump(mode='json'))


@pytest.mark.parametrize('score', [float('nan'), float('inf'), -1, 101, True])
def test_invalid_required_evaluator_score_invalidates_grade(score):
    pipeline = build_pipeline(definition=definition())
    with patch('autograder.template_library.static_analysis.ForbiddenImportTest.execute', return_value=TestResult('forbidden_import', score, '')):
        execution = pipeline.run(submission())
    assert execution.outcome.status == 'failed'
    assert execution.outcome.score is None
    assert execution.outcome.error.code == 'INVALID_EVALUATOR_RESULT'


def test_custom_step_exception_has_diagnostics_and_cleanup_is_always_called():
    pipeline = build_pipeline(definition=definition())
    pipeline._steps[StepName.GRADE] = Mock()
    pipeline._steps[StepName.GRADE].execute.side_effect = RuntimeError('secret')
    with patch.object(pipeline, '_cleanup_sandbox') as cleanup:
        execution = pipeline.run(submission())
    cleanup.assert_called_once_with(execution)
    assert execution.outcome.status == 'failed'
    diagnostics = PipelineExecutionSerializer.serialize(execution)
    assert diagnostics['failed_at_step'] == 'GradeStep'
    assert diagnostics['steps_completed'] < diagnostics['total_steps_planned']
    assert diagnostics['steps'][-1]['status'] == 'interrupted'
    assert PipelineExecutionSerializer.serialize(execution)['execution_time_ms'] == diagnostics['execution_time_ms']


@pytest.mark.parametrize('mutation', [
    lambda v: v.update(score=101),
    lambda v: v.update(score=float('nan')),
    lambda v: v.update(status='failed'),
    lambda v: v.update(error={'code':'NO','message':'Failed','category':'internal','retryable':False,'correlation_id':v['execution_id']}),
    lambda v: v.update(started_at='2026-10-04T00:00:00'),
    lambda v: v.update(finished_at='2000-01-01T00:00:00Z'),
    lambda v: v['tree']['base']['tests'][0].update(score=25),
    lambda v: v['tree']['base']['tests'].append(deepcopy(v['tree']['base']['tests'][0])),
    lambda v: v['feedback'].update(status='failed'),
])
def test_impossible_completed_payloads_are_rejected(mutation):
    wire = outcome().model_dump(mode='json')
    mutation(wire)
    with pytest.raises(ValidationError):
        validate_outcome(wire)


def test_contract_schema_is_discriminated_and_outcome_is_frozen():
    schema = outcome_json_schema()
    assert schema['discriminator']['propertyName'] == 'status'
    value = outcome()
    with pytest.raises(ValidationError):
        value.score = 50


def test_nested_parameters_are_immutable_without_changing_json_arrays():
    value = outcome()
    with pytest.raises(TypeError):
        value.tree.base.tests[0].parameters['new'] = 'value'
    with pytest.raises(TypeError):
        value.tree.base.tests[0].parameters['forbidden_imports'].append('sys')
    assert value.model_dump(mode='json')['tree']['base']['tests'][0]['parameters']['forbidden_imports'] == ['os']


@pytest.mark.parametrize('grade', [True, '100'])
def test_external_grade_must_be_numeric_without_coercion(grade):
    value = outcome().model_dump(mode='json')
    value['score'] = grade
    with pytest.raises(ValidationError):
        validate_outcome(value)


def test_finalization_is_idempotent_and_does_not_change_duration():
    execution = build_pipeline(definition=definition()).run(submission())
    artifact = execution.outcome
    duration = execution.duration_ms
    execution.finish_execution()
    assert execution.outcome is artifact
    assert execution.duration_ms == duration


@pytest.mark.parametrize('evaluator', ['health_check', 'check_response_json'])
def test_api_request_failure_is_not_an_assessed_zero(evaluator):
    import requests
    from autograder.template_library.api_testing import ApiTestingTemplate
    sandbox = Mock()
    sandbox.make_request.side_effect = requests.RequestException('secret')
    with pytest.raises(EvaluationError) as error:
        ApiTestingTemplate().get_test(evaluator).execute([], sandbox, endpoint='/')
    assert error.value.category == 'capability'
    assert 'secret' not in error.value.message


@pytest.mark.parametrize('evaluator', ['health_check', 'check_response_json'])
def test_assessed_api_failure_is_zero(evaluator):
    from autograder.template_library.api_testing import ApiTestingTemplate
    sandbox = Mock()
    sandbox.make_request.return_value.status_code = 500
    assert ApiTestingTemplate().get_test(evaluator).execute([], sandbox, endpoint='/').score == 0
