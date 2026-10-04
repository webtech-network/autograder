"""Teacher/browser examples must author the same definition the engine executes."""
import json
from pathlib import Path
import shutil
import subprocess
import pytest
from pydantic import ValidationError
from autograder import compile_definition
from autograder.models.contracts.outcome import ComparisonContent, CriterionDelta


@pytest.mark.parametrize('path', sorted(Path('examples/assets').glob('**/definition.json')) +
    sorted(Path('examples/assets/input_output/criteria_examples').glob('*.json')))
def test_shipped_definition_compiles(path):
    compile_definition(json.loads(path.read_text()))


@pytest.mark.skipif(shutil.which('node') is None, reason='Browser authoring test requires Node')
def test_browser_all_presets_generate_valid_single_and_multiple_language_definitions():
    javascript = r'''
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const context = {
  document: {addEventListener() {}},
  fetch: async name => ({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.resolve('examples/demo',name),'utf8'))}),
};
vm.createContext(context);
vm.runInContext(fs.readFileSync('examples/demo/shared.js','utf8'),context);
vm.runInContext(fs.readFileSync('examples/demo/config.js','utf8'),context);
vm.runInContext(`(async()=>{
  await loadCriteriaTemplates();
  const languages=[['python'],['java'],['node'],['cpp'],['python','java','node','cpp']];
  const definitions=Object.values(criteriaTemplates).flatMap(preset=>
    languages.map(selection=>buildMultiLanguageDefinition(preset.definition,selection)));
  return definitions;
})()`,context).then(definitions=>process.stdout.write(JSON.stringify(definitions))).catch(error=>{
  process.stderr.write(String(error));process.exit(1);
});
'''
    result=subprocess.run(['node','-e',javascript],check=True,capture_output=True,text=True)
    definitions=json.loads(result.stdout)
    assert len(definitions)==25
    for definition in definitions:
        compiled=compile_definition(definition)
        assert set(compiled.definition.preparation.languages)==set(compiled.definition.languages)


@pytest.mark.parametrize('number',[True,False,'1'])
def test_comparison_values_do_not_coerce_wire_booleans_or_strings(number):
    with pytest.raises(ValidationError):
        ComparisonContent(score_delta=number,improved=True)
    with pytest.raises(ValidationError):
        CriterionDelta(path='criterion',status='improved',baseline_score=0,head_score=1,delta=number)
