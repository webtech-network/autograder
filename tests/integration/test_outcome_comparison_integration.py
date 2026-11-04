"""Real grading runs and round trips retain criterion identity and weighted scores."""
from copy import deepcopy
from autograder.models.capabilities import HostCapabilities

import pytest
from pydantic import BaseModel, ConfigDict

from autograder.autograder import build_pipeline
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.template import Template
from autograder.models.contracts.comparison import compare_outcomes
from autograder.models.contracts.definition import compile_definition
from autograder.models.contracts.outcome import outcome_score_vector, validate_outcome
from autograder.models.execution import ProviderAssessment
from autograder.models.contracts.outcome import ResultOutcomeTree, score_vector
from tests.grading import FakeProvider
from tests.unit.pipeline.test_terminal_outcome import definition, submission


@pytest.mark.parametrize('before,after,delta', [('import os','print(1)',100), ('print(1)','import os',-100), ('print(1)','print(1)',0)])
def test_comparison_of_real_runs(before, after, delta):
    compiled = compile_definition(definition())
    pipeline = build_pipeline(definition=compiled)
    baseline, head = pipeline.run(submission(before)), pipeline.run(submission(after))
    comparison = compare_outcomes(baseline.outcome, head.outcome, compiled.definition, compiled.definition)
    assert comparison.compatibility == 'same_definition'
    assert comparison.score_delta == delta
    assert comparison.criteria[0].criterion_id == 'imports'
    assert {row.criterion_id: row.head_score for row in comparison.criteria} == outcome_score_vector(head.outcome)
    # Comparison is a separate use of completed grades; the frozen grade is unchanged.
    assert head.outcome.comparison.status == 'disabled'
    head_tree = ResultOutcomeTree.model_validate(head.outcome.tree.model_dump(mode='json'))
    assert head_tree == head.outcome.tree
    assert outcome_score_vector(head.outcome) == score_vector(head_tree)


def test_renamed_label_across_revisions_preserves_join_identity():
    original = compile_definition(definition())
    changed = definition()
    changed['criteria']['base']['tests'][0]['name'] = 'Changed label'
    renamed = compile_definition(changed)
    baseline = build_pipeline(definition=original).run(submission('import os'))
    head = build_pipeline(definition=renamed).run(submission('print(1)'))
    comparison = compare_outcomes(baseline.outcome, head.outcome, original.definition, renamed.definition)
    assert comparison.compatibility == 'cross_revision' and comparison.score_delta is None
    assert len(comparison.criteria) == 1
    row = comparison.criteria[0]
    assert (row.criterion_id, row.status, row.baseline_label, row.head_label) == (
        'imports', 'improved', 'Imports', 'Changed label')


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
    config_schema = EmptyParameters
    def build_prompt(self, evaluation):
        return 'Review this criterion'


class ReviewTemplate(Template):
    template_name = 'review'
    template_description = 'review'
    requires_sandbox = False
    def __init__(self):
        self.tests = {'review':Review()}


def ai_definition():
    return {'schema_version':'1.0','templates':['review'],'languages':['python'],
            'criteria':{'base':{'weight':100,'tests':[
                {'id':identity,'type':'review','name':'Repeated display label','parameters':{}}
                for identity in ['first','second']]}}}


def test_repeated_ai_evaluator_outputs_are_bound_to_criterion_ids():
    provider = FakeProvider(lambda requests: [ProviderAssessment('first', 100), ProviderAssessment('second', 0)])
    pipeline = build_pipeline(definition=ai_definition(), templates={'review':ReviewTemplate()}, capabilities=HostCapabilities(ai=provider))
    execution = pipeline.run(submission('print(1)'))
    assert execution.outcome.status == 'completed' and execution.outcome.score == 50
    assert outcome_score_vector(execution.outcome) == {'first':100,'second':0}
    [(inputs, _, _)] = provider.calls
    assert [item.criterion_id for item in inputs] == ['first','second']


def test_missing_ai_assessment_fails_once_without_fallback_or_zero_grade():
    provider = FakeProvider(lambda requests: [ProviderAssessment('first', 100)])
    pipeline = build_pipeline(definition=ai_definition(), templates={'review':ReviewTemplate()}, capabilities=HostCapabilities(ai=provider))
    execution = pipeline.run(submission('print(1)'))
    assert execution.outcome.status == 'failed' and execution.outcome.score is None
    assert execution.outcome.error.code == 'MISSING_EVALUATOR_RESULT'
    assert len(provider.calls) == 1


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
