"""Real grading runs and round trips retain criterion identity and weighted scores."""
from copy import deepcopy
from unittest.mock import patch

import pytest
from pydantic import BaseModel, ConfigDict

from autograder.autograder import build_pipeline
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.template import Template
from autograder.models.contracts.outcome import (
    ComparisonOutcome, outcome_score_vector, validate_outcome,
)
from autograder.models.dataclass.test_result import TestResult
from autograder.models.result_tree import ResultTree
from autograder.services.result_comparator import ResultComparator
from tests.unit.pipeline.test_terminal_outcome import definition, submission


@pytest.mark.parametrize('before,after,delta', [('import os','print(1)',100), ('print(1)','import os',-100), ('print(1)','print(1)',0)])
def test_comparison_of_real_runs(before, after, delta):
    pipeline = build_pipeline(definition=definition())
    baseline, head = pipeline.run(submission(before)), pipeline.run(submission(after))
    comparison = ResultComparator.compare(baseline.result.result_tree, head.result.result_tree)
    assert comparison.score_delta == delta
    assert comparison.test_deltas[0].path == 'imports'
    enriched = head.outcome.model_copy(update={'comparison':ComparisonOutcome(status='completed', content=comparison.to_dict())})
    assert validate_outcome(enriched.model_dump(mode='json')).comparison.content.score_delta == delta
    assert outcome_score_vector(head.outcome) == head.result.result_tree.to_score_vector()


def test_tree_roundtrip_and_renamed_groups_preserve_join_identity():
    original = definition()
    renamed = definition()
    renamed['criteria']['base']['tests'][0]['name'] = 'Changed label'
    baseline = build_pipeline(definition=original).run(submission('import os'))
    head = build_pipeline(definition=renamed).run(submission('print(1)'))
    reconstructed = ResultTree.from_dict(baseline.outcome.tree.model_dump(mode='json'))
    comparison = ResultComparator.compare(reconstructed, head.result.result_tree)
    assert len(comparison.test_deltas) == 1
    assert comparison.test_deltas[0].path == 'imports'
    assert comparison.test_deltas[0].status == 'improved'


@pytest.mark.parametrize('split,expected', [(0,100),(25,75),(100,0)])
def test_mixed_subject_and_test_weights_match_canonical_tree(split, expected):
    value = definition()
    direct = value['criteria']['base']['tests'][0]
    direct['id'] = 'direct'
    direct['parameters'] = {'forbidden_imports':['sys']}
    grouped = deepcopy(direct)
    grouped['id'] = 'grouped'
    grouped['parameters'] = {'forbidden_imports':['os']}
    value['criteria']['base']['subjects_weight'] = split
    value['criteria']['base']['subjects'] = [{'subject_name':'Nested','weight':100,
        'subjects':[{'subject_name':'Inner','weight':100,'tests':[grouped]}]}]
    execution = build_pipeline(definition=value).run(submission('import os'))
    assert execution.outcome.status == 'completed'
    assert execution.outcome.score == expected
    assert outcome_score_vector(execution.outcome) == {'direct':100,'grouped':0}
    validate_outcome(execution.outcome.model_dump(mode='json'))


def test_bonus_and_penalty_caps_are_validated_against_leaf_scores():
    value = definition()
    value['criteria']['base']['tests'][0]['parameters']={'forbidden_imports':['sys']}
    test = deepcopy(value['criteria']['base']['tests'][0])
    test['id'] = 'bonus'
    value['criteria']['bonus']={'weight':25,'tests':[test]}
    test = deepcopy(test)
    test['id'] = 'penalty'
    test['parameters']={'forbidden_imports':['os']}
    value['criteria']['penalty']={'weight':50,'tests':[test]}
    execution = build_pipeline(definition=value).run(submission('import os'))
    assert execution.outcome.score == 75
    assert outcome_score_vector(execution.outcome) == {'imports':100,'bonus':100,'penalty':0}


class EmptyParameters(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Review(AiTestFunction):
    name = 'review'
    description = 'review'
    parameter_description = []
    config_schema = EmptyParameters
    def build_prompt(self, files, **kwargs):
        return 'Review this criterion'


class ReviewTemplate(Template):
    template_name = 'review'
    template_description = 'review'
    requires_sandbox = False
    def __init__(self):
        self.tests = {'review':Review()}
    def get_test(self, name):
        return self.tests[name]


def ai_definition():
    return {'schema_version':'1.0','templates':['review'],'languages':['python'],
            'criteria':{'base':{'weight':100,'tests':[
                {'id':identity,'type':'review','name':'Repeated display label','parameters':{}}
                for identity in ['first','second']]}}}


def test_repeated_ai_evaluator_outputs_are_bound_to_criterion_ids():
    pipeline = build_pipeline(definition=ai_definition(), templates={'review':ReviewTemplate()})
    with patch('autograder.steps.ai_batch_step.AiExecutor') as executor:
        executor.return_value.run.return_value={'first':TestResult('first',100,''),'second':TestResult('second',0,'')}
        execution = pipeline.run(submission('print(1)'))
    assert execution.outcome.status == 'completed' and execution.outcome.score == 50
    assert outcome_score_vector(execution.outcome) == {'first':100,'second':0}
    inputs = executor.return_value.run.call_args.args[0]
    assert [item.test_name for item in inputs] == ['first','second']
    executor.return_value.run.assert_called_once()


def test_missing_ai_assessment_fails_once_without_fallback_or_zero_grade():
    pipeline = build_pipeline(definition=ai_definition(), templates={'review':ReviewTemplate()})
    with patch('autograder.steps.ai_batch_step.AiExecutor') as executor, patch('autograder.models.abstract.ai_test_function.AiExecutor') as fallback:
        executor.return_value.run.return_value={'first':TestResult('first',100,'')}
        execution = pipeline.run(submission('print(1)'))
    assert execution.outcome.status == 'failed' and execution.outcome.score is None
    assert execution.outcome.error.code == 'MISSING_EVALUATOR_RESULT'
    executor.return_value.run.assert_called_once()
    fallback.assert_not_called()


@pytest.mark.parametrize('weights', [[0,0], [1e308,1e308], [1e-300,1e-300], [1,3]])
def test_sibling_weight_normalization_is_finite_even_at_extreme_scales(weights):
    value = definition()
    first = value['criteria']['base']['tests'][0]
    first['weight'] = weights[0]
    second = deepcopy(first)
    second['id'] = 'second'
    second['weight'] = weights[1]
    second['parameters'] = {'forbidden_imports':['sys']}
    value['criteria']['base']['tests'].append(second)
    execution = build_pipeline(definition=value).run(submission('import os'))
    assert execution.outcome.status == 'completed'
    assert execution.outcome.score == (75 if weights == [1,3] else 50)
