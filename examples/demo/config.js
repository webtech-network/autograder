/* Configuration Page Logic */

document.addEventListener('DOMContentLoaded', () => {
    updatePreview().catch(error => showMessage('createResult', error.message, 'error'));
});

async function updatePreview() {
    await loadCriteriaTemplates();
    const template = criteriaTemplates[document.getElementById('criteriaTemplate').value];
    const languages = getSelectedLanguages();
    const definition = buildMultiLanguageDefinition(template.definition, languages.length ? languages : ['python']);
    document.getElementById('templateDescription').textContent = template.description;
    document.getElementById('treePreview').textContent = buildCriteriaTree(definition.criteria);
    document.getElementById('jsonPreview').value = JSON.stringify(definition, null, 2);
}

function getSelectedLanguages() {
    return Array.from(document.querySelectorAll('input[name="language"]:checked')).map(box => box.value);
}

function buildMultiLanguageDefinition(source, languages) {
    const definition = JSON.parse(JSON.stringify(source));
    definition.languages = [...languages];
    const commands = Object.fromEntries(languages.map(language => [language, languageCommands[language]]));
    const visit = group => {
        (group.tests || []).forEach(test => { test.parameters.program_command = {...commands}; });
        (group.subjects || []).forEach(visit);
    };
    ['base','bonus','penalty'].forEach(name => { if (definition.criteria[name]) visit(definition.criteria[name]); });
    definition.preparation.languages = buildMultiLanguageSetupConfig(languages);
    return definition;
}

function buildCriteriaTree(criteria) {
    let tree = 'Criteria Tree:\n';

    if (criteria.base) {
        tree += '├── Base (weight: ' + criteria.base.weight + ')\n';
        tree += buildSection(criteria.base, '│   ');
    }

    if (criteria.bonus) {
        tree += '├── Bonus (weight: ' + criteria.bonus.weight + ')\n';
        tree += buildSection(criteria.bonus, '│   ');
    }

    if (criteria.penalty) {
        tree += '└── Penalty (weight: ' + criteria.penalty.weight + ')\n';
        tree += buildSection(criteria.penalty, '    ');
    }

    return tree;
}

function buildSection(section, prefix) {
    let result = '';

    if (section.subjects) {
        section.subjects.forEach((subject, i) => {
            const isLast = i === section.subjects.length - 1 && !section.tests;
            const connector = isLast ? '└── ' : '├── ';
            const extension = isLast ? '    ' : '│   ';

            result += prefix + connector + subject.subject_name + ' (weight: ' + subject.weight + ')\n';

            result += buildSection(subject, prefix + extension);
        });
    }

    if (section.tests) {
        result += buildTests(section.tests, prefix);
    }

    return result;
}

function buildTests(tests, prefix) {
    let result = '';
    tests.forEach((test, i) => {
        const isLast = i === tests.length - 1;
        const connector = isLast ? '└── ' : '├── ';
        result += prefix + connector + 'Test: ' + test.name + ' (' + test.id + ')\n';
    });
    return result;
}

async function createConfig() {
    const assignmentId = document.getElementById('assignmentId').value;
    const templateId = document.getElementById('criteriaTemplate').value;
    const selectedLanguages = getSelectedLanguages();

    if (!assignmentId) {
        showMessage('createResult', 'Please enter an assignment ID', 'error');
        return;
    }

    if (selectedLanguages.length === 0) {
        showMessage('createResult', 'Please select at least one language', 'error');
        return;
    }

    await loadCriteriaTemplates();
    const payload = {
        external_assignment_id: assignmentId,
        definition: buildMultiLanguageDefinition(criteriaTemplates[templateId].definition, selectedLanguages)
    };

    showMessage('createResult', 'Creating configuration...', 'success');

    const result = await apiCall('/api/v1/configs', 'POST', payload);

    displayResponse(result);

    if (result.ok) {
        showMessage('createResult', `Configuration created successfully! ID: ${result.data.id}`, 'success');
    } else {
        showMessage('createResult', `Error: ${result.data.error || 'Failed to create configuration'}`, 'error');
    }
}

function buildMultiLanguageSetupConfig(languages) {
    const setupConfigs = {
        python: {
            required_files: ["calculator.py"],
            setup_commands: []
        },
        java: {
            required_files: ["Calculator.java"],
            setup_commands: [{name: "Compile Java", command: "javac Calculator.java"}]
        },
        node: {
            required_files: ["calculator.js"],
            setup_commands: []
        },
        cpp: {
            required_files: ["calculator.cpp"],
            setup_commands: [{name: "Compile C++", command: "g++ calculator.cpp -o calculator"}]
        }
    };

    const result = {};
    languages.forEach(lang => {
        if (setupConfigs[lang]) {
            result[lang] = setupConfigs[lang];
        }
    });

    return result;
}

function copyJson(event) {
    const json = document.getElementById('jsonPreview');
    json.select();
    document.execCommand('copy');

    const btn = event.target;
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => {
        btn.textContent = originalText;
    }, 2000);
}


