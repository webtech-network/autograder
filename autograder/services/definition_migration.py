"""Explicit offline conversion to definition format 2.0. Never called by the live parser.

Three inputs are accepted: a pre-1.0 envelope (``template_name``,
``grading_criteria``, ...), a 1.0 definition and a 2.0 definition, which is only
checked. Every mapping is deterministic. What cannot be mapped is rejected with
its path (``CONVERSION_REJECTED``); what is mapped but assessed differently is
reported as a note next to the converted definition.

Run it on a file::

    python -m autograder.services.definition_migration old.json definition.json
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from typing import Mapping, NamedTuple

from autograder.models.abstract.template import Template
from autograder.models.contracts.definition import (
    SCHEMA_VERSION, DefinitionValidationError, compile_definition, compile_snapshot,
)

REJECTED = 'CONVERSION_REJECTED'

#: 1.0 evaluator parameters renamed in 2.0, per evaluator.
RENAMED_PARAMETERS = {'has_style': {'count': 'required_count'}}
#: 1.0 evaluators renamed in 2.0 because the old name hid what scores 100.
RENAMED_EVALUATORS = {'check_bootstrap_usage': 'has_no_bootstrap'}
#: 1.0 file-name parameters that duplicated the criterion ``file`` target.
FILE_PARAMETERS = {'has_no_js_framework': ('html_file', 'js_file'),
                   'count_unused_css_classes': ('html_file', 'css_file')}
FILE_PARAMETER_NOTE = ('`{evaluator}` names no files in 2.0: it reads every {kinds} file of the submission, '
                       'where 1.0 read only {files} (the same result when the project has one of each)')


class Conversion(NamedTuple):
    """A converted 2.0 definition and what it assesses differently from its source."""
    definition: dict
    notes: list


def _reject(path, message):
    raise DefinitionValidationError([{'code': REJECTED, 'path': list(path), 'message': message}])


def _rename(owner: dict, old: str, new: str, path):
    if old not in owner:
        return
    if new in owner:
        _reject((*path, old), f'Both `{old}` and `{new}` are given; keep one')
    items = list(owner.items())
    owner.clear()
    owner.update((new if key == old else key, value) for key, value in items)


def upgrade_v1(definition: Mapping) -> Conversion:
    """Map a 1.0 definition onto the 2.0 shape without consulting any registry.

    Structural only: the result still has to be compiled. A field that 1.0
    rejected is left for compilation to report at the same path.
    """
    source = deepcopy(dict(definition))
    if source.get('schema_version') != '1.0':
        _reject(('schema_version',), 'Expected a 1.0 definition')
    notes = []
    source.pop('templates', None)  # type alone resolves the evaluator
    criteria = source.get('criteria')
    if isinstance(criteria, dict):
        base = criteria.get('base')
        if isinstance(base, dict) and 'weight' in base:
            if base['weight'] != 100 or isinstance(base['weight'], bool):
                _reject(('criteria', 'base', 'weight'), '1.0 required a base weight of 100; this definition was invalid')
            del base['weight']
        for category in ('bonus', 'penalty'):
            if isinstance(criteria.get(category), dict):
                _rename(criteria[category], 'weight', 'max_points', ('criteria', category))

        def group(node, path):
            if not isinstance(node, dict):
                return
            for index, test in enumerate(node.get('tests') or []):
                if isinstance(test, dict):
                    _upgrade_test(test, (*path, 'tests', index), notes)
            for index, subject in enumerate(node.get('subjects') or []):
                if isinstance(subject, dict):
                    _rename(subject, 'subject_name', 'name', (*path, 'subjects', index))
                group(subject, (*path, 'subjects', index))

        for category in ('base', 'bonus', 'penalty'):
            group(criteria.get(category), ('criteria', category))
    order = ('schema_version', 'languages', 'criteria', 'preparation', 'feedback', 'metadata')
    upgraded = {key: source[key] for key in order if key in source}
    upgraded.update({key: value for key, value in source.items() if key not in upgraded})
    upgraded['schema_version'] = SCHEMA_VERSION
    return Conversion(upgraded, notes)


def _upgrade_test(test: dict, path, notes):
    evaluator = test.get('type')
    parameters = test.get('parameters')
    if evaluator in RENAMED_EVALUATORS:
        test['type'] = evaluator = RENAMED_EVALUATORS[evaluator]
    if not isinstance(parameters, dict):
        return
    for old, new in RENAMED_PARAMETERS.get(evaluator, {}).items():
        _rename(parameters, old, new, (*path, 'parameters'))
    if evaluator == 'dont_fail' and 'user_input' in parameters:
        if 'inputs' in parameters:
            _reject((*path, 'parameters', 'user_input'), 'Both `user_input` and `inputs` are given; keep one')
        line = parameters['user_input']
        if not isinstance(line, str):
            _reject((*path, 'parameters', 'user_input'), '`user_input` must be a string')
        _rename(parameters, 'user_input', 'inputs', (*path, 'parameters'))
        # One stdin line, or empty stdin for an empty value: exactly the bytes 1.0 sent.
        parameters['inputs'] = [line] if line else []
    removed = [name for name in FILE_PARAMETERS.get(evaluator, ()) if name in parameters]
    if removed:
        named = [parameters.pop(name) for name in removed]
        kinds = 'HTML and CSS' if evaluator == 'count_unused_css_classes' else 'HTML and JavaScript'
        notes.append({'path': [*path, 'parameters'], 'message': FILE_PARAMETER_NOTE.format(
            evaluator=evaluator, kinds=kinds, files=', '.join(f'`{name}`' for name in named))})


def convert_definition(value: Mapping, *, templates: Mapping[str, Template] | None = None) -> Conversion:
    """Convert authoring input in any earlier format, then compile it as 2.0.

    Raises ``DefinitionValidationError`` with the exact paths of what cannot be
    converted or does not compile. ``templates`` are the trusted Python
    templates the definition's evaluators come from, if not built in.
    """
    if not isinstance(value, Mapping):
        _reject((), 'A definition must be an object')
    version = value.get('schema_version')
    if version is None:
        converted = upgrade_v1(_legacy_to_v1(deepcopy(dict(value))))
    elif version == '1.0':
        converted = upgrade_v1(value)
    else:
        converted = Conversion(deepcopy(dict(value)), [])
    compiled = compile_definition(converted.definition, templates=templates)
    return Conversion(compiled.definition.model_dump(mode='json'), converted.notes)


def convert_snapshot(snapshot: Mapping) -> Conversion:
    """Convert a stored canonical 1.0 snapshot without normalizing it again.

    The result is loaded with ``compile_snapshot``, as every stored snapshot
    is, so a parameter value is never changed: only renamed.
    """
    converted = upgrade_v1(snapshot) if snapshot.get('schema_version') == '1.0' else Conversion(deepcopy(dict(snapshot)), [])
    compiled = compile_snapshot(converted.definition)
    return Conversion(compiled.definition.model_dump(mode='json'), converted.notes)


def _legacy_to_v1(source: dict) -> dict:  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
    """Pre-1.0 envelope to a 1.0 definition.

    Historical runtime-injected language placeholders are removed. Duplicates,
    competing extra parameter encodings, and unknown authoring fields are errors.
    No undocumented last-value-wins behavior is retained.
    """
    fail = _reject
    allowed = {'template_name','grading_criteria','criteria','languages','setup_config','include_feedback','feedback_config','feedback_mode','test_library','assignment_id','id','is_active','created_at','updated_at'}
    unknown = set(source) - allowed
    if unknown:
        fail((sorted(unknown)[0],), 'Unknown legacy definition field')
    if 'grading_criteria' in source and 'criteria' in source:
        fail(('criteria',), 'Competing criteria encodings require explicit resolution')
    criteria = source.get('grading_criteria', source.get('criteria'))
    if not isinstance(criteria, dict):
        fail(('criteria',), 'Legacy criteria object required')
    criteria.pop('test_library', None)
    languages = source.get('languages')
    if isinstance(languages, str):
        languages = [item.strip().lower() for item in languages.split(',')]
    elif isinstance(languages, list):
        languages = [item.lower() if isinstance(item,str) else item for item in languages]
    names = {}
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
            identity='-'.join(map(str,testpath))  # identity derives solely from the path
            names.setdefault(label,[]).append(identity)
            converted={'id':identity,'type':evaluator,'name':label,'parameters':normalized}
            if 'file' in test:
                converted['file']=None if test['file']=='all' else test['file']
            if 'weight' in test:
                converted['weight']=test['weight']
            test.clear()
            test.update(converted)
        for i,subject in enumerate(group.get('subjects') or []):
            walk(subject,(*path,'subjects',i))
    for category in ('base','bonus','penalty'):
        if criteria.get(category) is not None:
            walk(criteria[category],(category,))
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
    # The unused AI preferences have no reporter equivalent; reject nonempty ones.
    if preferences.get('ai'):
        fail(('feedback_config','ai'),'AI reporter preferences are unsupported')
    preferences.pop('ai',None)
    # Learning links formerly named labels; only unambiguous labels can be migrated.
    for resource_index,resource in enumerate(preferences.get('general',{}).get('online_content',[])):
        references=[]
        for link in resource.get('linked_tests',[]):
            ids=names.get(link,[])
            if len(ids)!=1:
                fail(('feedback_config','general','online_content',resource_index,'linked_tests'),
                     'Legacy learning-resource labels require an unambiguous criterion match')
            references.append(ids[0])
        resource['linked_tests']=references
    return {'schema_version':'1.0','languages':languages,'criteria':criteria,
            'preparation':preparation,'feedback':{'enabled':source.get('include_feedback',False),
            'mode':source.get('feedback_mode') or 'default','preferences':preferences}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=(
        f'Convert one grading definition (pre-1.0 or 1.0) to format {SCHEMA_VERSION} offline; '
        'prints what it cannot convert, and what it converted but assesses differently'))
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args(argv)
    try:
        result = convert_definition(json.loads(args.source.read_text(encoding='utf-8')))
    except DefinitionValidationError as exc:
        print(json.dumps({'errors': exc.errors()}, indent=2))
        raise SystemExit(2) from exc
    args.destination.write_text(json.dumps(result.definition, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if result.notes:
        print(json.dumps({'notes': result.notes}, indent=2), file=sys.stderr)


if __name__ == '__main__':
    main()
