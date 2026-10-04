"""Explicit offline legacy conversion. Never called by the live parser."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from pydantic import ValidationError
from autograder.models.contracts.definition import DefinitionValidationError, compile_definition


def convert_legacy_definition(legacy: dict) -> dict:
    """Convert unambiguous legacy rows/files, then compile the resulting v1.

    Historical runtime-injected language placeholders are removed. Duplicates,
    competing extra parameter encodings, and unknown authoring fields are errors.
    No undocumented last-value-wins behavior is retained.
    """
    if not isinstance(legacy, dict):
        raise DefinitionValidationError([{'code': 'LEGACY_CONVERSION_REJECTED', 'path': [],
                                          'message': 'Legacy definition must be an object'}])
    source = deepcopy(legacy)
    if source.get('schema_version') is not None:
        return compile_definition(source).definition.model_dump(mode='json')
    def fail(path, message):
        raise DefinitionValidationError([{'code':'LEGACY_CONVERSION_REJECTED','path':list(path),'message':message}])
    allowed = {'template_name','grading_criteria','criteria','languages','setup_config','include_feedback','feedback_config','feedback_mode','test_library','assignment_id','id','is_active','created_at','updated_at'}
    unknown = set(source) - allowed
    if unknown:
        fail((sorted(unknown)[0],), 'Unknown legacy definition field')
    if 'grading_criteria' in source and 'criteria' in source:
        fail(('criteria',), 'Competing criteria encodings require explicit resolution')
    criteria = source.get('grading_criteria', source.get('criteria'))
    if not isinstance(criteria, dict):
        fail(('criteria',), 'Legacy criteria object required')
    template = source.get('template_name', criteria.pop('test_library', source.get('test_library')))
    criteria.pop('test_library', None)
    templates = [item.strip() for item in template.split(',')] if isinstance(template, str) else template
    languages = source.get('languages')
    if isinstance(languages, str):
        languages = [item.strip().lower() for item in languages.split(',')]
    elif isinstance(languages, list):
        languages = [item.lower() if isinstance(item,str) else item for item in languages]
    def walk(group, path):
        if not isinstance(group,dict):
            fail(path, 'Expected criteria group')
        for i,test in enumerate(group.get('tests') or []):
            testpath=(*path,'tests',i)
            if not isinstance(test,dict):
                fail(testpath,'Expected test object')
            evaluator=test.get('type') or test.get('name')
            params=test.get('parameters',[])
            if not isinstance(params,list):
                fail((*testpath,'parameters'),'Legacy parameters must be named pairs')
            normalized={}
            for j,pair in enumerate(params):
                if not isinstance(pair,dict) or set(pair)!={'name','value'} or not isinstance(pair['name'],str):
                    fail((*testpath,'parameters',j),'Expected an exact name/value pair')
                key=pair['name']
                if key in normalized:
                    fail((*testpath,'parameters',j),'Duplicate parameter requires instructor resolution')
                normalized[key]=pair['value']
            # Language has always been injected by the runtime, never assignment-owned.
            normalized.pop('submission_language',None)
            parameter_label=normalized.pop('display_name',None)
            if parameter_label is not None and (not isinstance(parameter_label,str) or not parameter_label.strip()):
                fail((*testpath,'parameters','display_name'),'Legacy display name must be a nonempty string')
            if parameter_label is not None and test.get('display_name') not in (None,parameter_label):
                fail((*testpath,'display_name'),'Competing display names require explicit resolution')
            label=parameter_label or test.get('display_name') or test.get('name') or evaluator
            extras=set(test)-{'name','type','file','weight','parameters','display_name'}
            if extras:
                fail((*testpath,sorted(extras)[0]),'Extra-key parameter encoding requires explicit resolution')
            test.clear()
            test.update(id='-'.join(map(str,testpath)),type=evaluator,name=label,parameters=normalized)
            # Replaced below from preserved originals; identity derives solely from path.
        for i,subject in enumerate(group.get('subjects') or []):
            walk(subject,(*path,'subjects',i))
    # Preserve display/file/weights while converting each test in place.
    original=deepcopy(criteria)
    for category in ('base','bonus','penalty'):
        if criteria.get(category) is not None:
            walk(criteria[category],(category,))
    def restore(new,old):
        for test, prior in zip(new.get('tests') or [],old.get('tests') or []):
            for field in ('file','weight'):
                if field in prior:
                    test[field]=None if field == 'file' and prior[field] == 'all' else prior[field]
        for newsub,oldsub in zip(new.get('subjects') or [],old.get('subjects') or []):
            restore(newsub,oldsub)
    for category in ('base','bonus','penalty'):
        if criteria.get(category) is not None:
            restore(criteria[category],original[category])
    if criteria.get('base'):
        # Legacy base weight was ignored by the grader; canonicalize its semantics.
        criteria['base']['weight']=100
    setup=source.get('setup_config') or {}
    if not isinstance(setup,dict):
        fail(('setup_config',),'Expected setup object')
    preparation={'languages':{},'fixtures':[]}
    if 'global' in setup:
        if not isinstance(setup['global'], dict) or set(setup['global']) - {'assets'}:
            fail(('setup_config', 'global'), 'Only the legacy assets field is supported in global preparation')
        if 'assets' in setup and 'assets' in setup['global']:
            fail(('setup_config', 'assets'), 'Competing asset encodings require explicit resolution')
    global_assets=setup.get('global',{}).get('assets')
    assets=global_assets if global_assets is not None else setup.get('assets',[])
    if not isinstance(assets, list):
        fail(('setup_config', 'assets'), 'Expected an asset list')
    for i,asset in enumerate(assets):
        if not isinstance(asset,dict) or set(asset)-{'source','target','read_only'}:
            fail(('setup_config','assets',i),'Unexpected asset shape')
        target=asset.get('target','')
        if not isinstance(target, str):
            fail(('setup_config', 'assets', i, 'target'), 'Expected a target path string')
        if target.startswith('/tmp/app/'):
            target=target[len('/tmp/app/'):]
        elif target.startswith('/'):
            fail(('setup_config','assets',i,'target'),'Absolute targets outside submission root require explicit relocation')
        preparation['fixtures'].append({'reference':asset.get('source'), 'path':target,'read_only':asset.get('read_only',True)})
    for key,value in setup.items():
        if key in ('global','assets'):
            continue
        if key not in (languages or []):
            fail(('setup_config',key),'Preparation language must be allowed')
        if not isinstance(value,dict) or set(value)-{'required_files','setup_commands'}:
            fail(('setup_config',key),'Unexpected language preparation shape')
        commands=value.get('setup_commands',[])
        if not isinstance(commands, list):
            fail(('setup_config', key, 'setup_commands'), 'Expected a command list')
        value['setup_commands']=[{'name':f'Setup command {i+1}','command':command} if isinstance(command,str) else command for i,command in enumerate(commands)]
        preparation['languages'][key]=value
    preferences=source.get('feedback_config') or {}
    if not isinstance(preferences,dict):
        fail(('feedback_config',),'Expected feedback preferences')
    # The unused AI preferences have no v1 reporter equivalent; reject nonempty ones.
    if preferences.get('ai'):
        fail(('feedback_config','ai'),'AI reporter preferences are unsupported')
    preferences.pop('ai',None)
    # Learning links formerly named labels; only unambiguous labels can be migrated.
    from autograder.models.contracts.definition import GradingDefinition, walk_tests
    try:
        parsed = GradingDefinition.model_validate({
            'schema_version': '1.0', 'templates': templates, 'languages': languages, 'criteria': criteria})
    except ValidationError as exc:
        raise DefinitionValidationError([{'code': 'LEGACY_CONVERSION_REJECTED',
            'path': list(item['loc']), 'message': item['msg']}
            for item in exc.errors(include_input=False, include_url=False)]) from exc
    names={}
    for test,_ in walk_tests(parsed.criteria):
        names.setdefault(test.name,[]).append(test.id)
    for resource_index,resource in enumerate(preferences.get('general',{}).get('online_content',[])):
        references=[]
        for link in resource.get('linked_tests',[]):
            ids=names.get(link,[])
            if len(ids)!=1:
                fail(('feedback_config','general','online_content',resource_index,'linked_tests'),
                     'Legacy learning-resource labels require an unambiguous criterion match')
            references.append(ids[0])
        resource['linked_tests']=references
    result={'schema_version':'1.0','templates':templates,'languages':languages,'criteria':criteria,
            'preparation':preparation,'feedback':{'enabled':source.get('include_feedback',False),
            'mode':source.get('feedback_mode') or 'default','preferences':preferences}}
    return compile_definition(result).definition.model_dump(mode='json')


def main():
    parser=argparse.ArgumentParser(description='Convert one legacy grading definition offline; rejects ambiguity')
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    try:
        result=convert_legacy_definition(json.loads(args.source.read_text()))
    except DefinitionValidationError as exc:
        print(json.dumps({'errors':exc.errors()},indent=2))
        raise SystemExit(2) from exc
    args.destination.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')


if __name__=='__main__':
    main()
