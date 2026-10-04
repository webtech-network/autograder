"""Pure acceptance boundary: wire files and HTTP storage share this compiler."""
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
import pytest
from autograder.models.contracts.definition import (
    DefinitionValidationError, compile_definition, grading_definition_json_schema,
    select_language,
)
from autograder.services.definition_migration import convert_legacy_definition


def definition(evaluator='forbidden_import', parameters=None, templates=None):
    return {'schema_version':'1.0','templates':templates or ['static_analysis'],'languages':['python'],
            'criteria':{'base':{'weight':100,'tests':[{'id':'first','type':evaluator,'name':'First',
                'parameters':parameters if parameters is not None else {'forbidden_imports':['os']}}]}}}


def test_compile_is_pure_and_normalized_parameters_are_executed():
    value=definition('expect_output',{'program_command':'python3 main.py','expected_output':'ok'},['input_output'])
    with patch('boto3.client', side_effect=AssertionError('provider')), patch('sandbox_manager.manager.get_sandbox_manager',side_effect=AssertionError('sandbox')):
        compiled=compile_definition(value)
    params=compiled.criteria_tree.base.tests[0].parameters
    assert params=={'program_command':'python3 main.py','expected_output':'ok','inputs':[],'normalization':True}
    assert params==compiled.definition.criteria.base.tests[0].parameters
    assert compiled.criteria_tree.base.tests[0].criterion_id=='first'
    assert 'preparation' not in value  # caller data untouched


def test_defaults_and_json_key_order_have_stable_hash():
    compiled=compile_definition(definition())
    normalized=compiled.definition.model_dump(mode='json')
    assert compile_definition(normalized).definition_hash==compiled.definition_hash
    assert compile_definition(json.loads(json.dumps(normalized,sort_keys=True))).definition_hash==compiled.definition_hash
    normalized['criteria']['base']['tests'][0]['parameters']['forbidden_imports']=['math']
    assert compile_definition(normalized).definition_hash!=compiled.definition_hash


@pytest.mark.parametrize('mutate,path',[
    (lambda v:v.update(schema_version='2.0'),['schema_version']),
    (lambda v:v.update(languages=['Python']),['languages',0]),
    (lambda v:v.update(languages=[]),['languages']),
    (lambda v:v.update(unknown='ignored?'),['unknown']),
    (lambda v:v['criteria'].update(test_library='static_analysis'),['criteria','test_library']),
    (lambda v:v['criteria']['base']['tests'][0].pop('type'),['criteria','base','tests',0,'type']),
    (lambda v:v['criteria']['base']['tests'][0].update(parameters=[{'name':'x','value':1}]),['criteria','base','tests',0,'parameters']),
    (lambda v:v['criteria']['base']['tests'][0].update(extra_parameter='ignored?'),['criteria','base','tests',0,'extra_parameter']),
    (lambda v:v['criteria']['base']['tests'][0].update(weight=float('nan')),['criteria','base','tests',0,'weight']),
    (lambda v:v['criteria']['base']['tests'][0].update(weight=True),['criteria','base','tests',0,'weight']),
    (lambda v:v['criteria']['base']['tests'][0]['parameters'].update(forbidden_imports=42),['criteria','base','tests',0,'parameters','forbidden_imports']),
    (lambda v:v['criteria']['base']['tests'][0]['parameters'].update(locale='pt'),['criteria','base','tests',0,'parameters','locale']),
    (lambda v:v['criteria']['base']['tests'][0].update(file='../private.py'),['criteria','base','tests',0,'file']),
    (lambda v:v['criteria']['base']['tests'][0].update(type='unknown'),['criteria','base','tests',0,'type']),
    (lambda v:v.update(templates=['unknown']),['templates',0]),
])
def test_rejections_have_precise_paths(mutate,path):
    value=definition();mutate(value)
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert any(error['path']==path for error in failure.value.errors()),failure.value.errors()


def test_duplicate_ids_are_rejected_across_categories_and_nested_subjects():
    value=definition()
    value['criteria']['bonus']={'weight':10,'subjects':[{'subject_name':'a/b','weight':1,'tests':[deepcopy(value['criteria']['base']['tests'][0])]}]}
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]['code']=='DUPLICATE_CRITERION_ID'


def test_command_map_must_cover_every_allowed_language():
    value=definition('expect_output',{'expected_output':'','program_command':{'python':'python3 main.py'}},['input_output'])
    value['languages']=['python','java']
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]['code']=='MISSING_LANGUAGE_COMMAND'
    value['criteria']['base']['tests'][0]['parameters']['program_command']['java']='java Main'
    compiled=compile_definition(value)
    with pytest.raises(DefinitionValidationError):
        select_language(compiled,None)
    assert select_language(compiled,'java').value=='java'
    with pytest.raises(DefinitionValidationError):
        select_language(compiled,'node')


def test_preparation_and_feedback_are_typed_and_have_single_shapes():
    value=definition()
    value['preparation']={'languages':{'python':{'required_files':['main.py'],'setup_commands':[{'name':'compile','command':'python3 -m py_compile main.py'}]}},'fixtures':[{'reference':'course/fixture.json','path':'data/input.json'}]}
    value['feedback']={'enabled':True,'mode':'default','preferences':{'general':{'show_score':False,'online_content':[{'url':'https://example.org','description':'Docs','linked_tests':['first']}]}}}
    assert compile_definition(value).definition.preparation.fixtures[0].read_only is True
    value['feedback']['mode']='ai'
    with pytest.raises(DefinitionValidationError):compile_definition(value)
    value['feedback']['mode']='default';value['preparation']['fixtures'][0]['path']='/tmp/absolute'
    with pytest.raises(DefinitionValidationError):compile_definition(value)


def test_offline_converter_preserves_names_weights_and_rejects_ambiguity():
    old={'template_name':'static_analysis','languages':['python'],'grading_criteria':{'base':{'weight':50,'tests':[{'name':'Imports','type':'forbidden_import','weight':7,'file':'main.py','parameters':[{'name':'forbidden_imports','value':['os']},{'name':'submission_language','value':'java'}]}]}}}
    result=convert_legacy_definition(old)
    test=result['criteria']['base']['tests'][0]
    assert test['id']=='base-tests-0' and test['name']=='Imports' and test['weight']==7
    assert result['criteria']['base']['weight']==100
    assert test['parameters']=={'forbidden_imports':['os']}
    old['grading_criteria']['base']['tests'][0]['parameters'].append({'name':'forbidden_imports','value':['math']})
    with pytest.raises(DefinitionValidationError) as failure:
        convert_legacy_definition(old)
    assert failure.value.errors()[0]['code']=='LEGACY_CONVERSION_REJECTED'


def test_checked_in_examples_and_schema_are_current():
    directory=Path('docs/contracts/v1')
    schema=json.loads((directory/'grading-definition.schema.json').read_text())
    assert schema==grading_definition_json_schema()
    for path in (directory/'examples').glob('*.json'):
        compile_definition(json.loads(path.read_text()))


@pytest.mark.parametrize('rule',[{'regex':'['},{'all':[{'unknown':'value'}]},{'kind':42}])
def test_custom_ast_rule_must_compile_before_acceptance(rule):
    value=definition('forbidden_keyword',{'custom_ast_grep_rules':[rule]})
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    assert failure.value.errors()[0]['path']==['criteria','base','tests',0,'parameters','custom_ast_grep_rules',0]


def test_invalid_examples_have_documented_error_paths():
    directory=Path('docs/contracts/v1/examples/invalid')
    for expected in json.loads((directory/'manifest.json').read_text()):
        with pytest.raises(DefinitionValidationError) as failure:
            compile_definition(json.loads((directory/expected['file']).read_text()))
        assert failure.value.errors()==expected['errors']


def test_known_legacy_display_parameter_moves_to_display_name():
    result=convert_legacy_definition({'template_name':'static_analysis','languages':['python'],
        'grading_criteria':{'base':{'weight':100,'tests':[{'name':'forbidden_import',
        'parameters':[{'name':'forbidden_imports','value':['os']},{'name':'display_name','value':'No OS imports'}]}]}}})
    test=result['criteria']['base']['tests'][0]
    assert test['name']=='No OS imports' and test['parameters']=={'forbidden_imports':['os']}


def test_tiny_subject_weights_normalize_without_infinity():
    value=definition()
    test=value['criteria']['base'].pop('tests')[0]
    value['criteria']['base']['subjects']=[
        {'subject_name':'First','weight':1e-320,'tests':[test]},
        {'subject_name':'Second','weight':1e-320,'tests':[{**test,'id':'second'}]},
    ]
    compiled=compile_definition(value)
    assert [subject.weight for subject in compiled.criteria_tree.base.subjects]==[50,50]
    from autograder.models.dataclass.submission import Submission,SubmissionFile
    from autograder import build_pipeline
    result=build_pipeline(definition=compiled).run(Submission(username='test',user_id=1,assignment_id=1,
        submission_files={'main.py':SubmissionFile('main.py','print(1)')}))
    assert result.outcome.status=='completed' and result.outcome.score==100
