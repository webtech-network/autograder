/* Configuration Page Logic */

document.addEventListener('DOMContentLoaded', () => {
    updatePreview();
});

function updatePreview() {
    const templateId = document.getElementById('criteriaTemplate').value;
    const selectedLanguages = getSelectedLanguages();

    const template = criteriaTemplates[templateId];
    document.getElementById('templateDescription').textContent = template.description;

    // Use first selected language for preview, or default to python
    const previewLanguage = selectedLanguages.length > 0 ? selectedLanguages[0] : 'python';

    // Update tree preview
    const criteria = replaceCmdPlaceholder(template.criteria, previewLanguage);
    document.getElementById('treePreview').textContent = buildCriteriaTree(criteria);

    // Update JSON preview with all languages
    const fullCriteria = buildMultiLanguageCriteria(template.criteria, selectedLanguages);
    document.getElementById('jsonPreview').value = JSON.stringify(fullCriteria, null, 2);
}

function getSelectedLanguages() {
    const checkboxes = document.querySelectorAll('input[name="language"]:checked');
    return Array.from(checkboxes).map(cb => cb.value);
}

function buildMultiLanguageCriteria(baseCriteria, languages) {
    if (languages.length === 0) {
        languages = ['python']; // Default
    }

    // Deep clone the criteria to avoid modifying the original
    const criteria = JSON.parse(JSON.stringify(baseCriteria));

    // Build command map for all selected languages
    const commandMap = buildLanguageCommandMap(languages);

    // Replace all program_command parameters with multi-language format
    replaceCommandsWithMultiLanguage(criteria, commandMap);

    return criteria;
}

function buildLanguageCommandMap(languages) {
    const commandMap = {};
    languages.forEach(lang => {
        commandMap[lang] = languageCommands[lang];
    });
    return commandMap;
}

function replaceCommandsWithMultiLanguage(obj, commandMap) {
    if (typeof obj !== 'object' || obj === null) {
        return;
    }

    if (Array.isArray(obj)) {
        obj.forEach(item => replaceCommandsWithMultiLanguage(item, commandMap));
        return;
    }

    // Check if this is a parameters array with program_command
    if (obj.name === 'program_command' && obj.value === 'CMD') {
        obj.value = commandMap;
        return;
    }

    // Recursively process all properties
    Object.keys(obj).forEach(key => {
        replaceCommandsWithMultiLanguage(obj[key], commandMap);
    });
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

            if (subject.subjects) {
                result += buildSubjectSubjects(subject.subjects, prefix + extension);
            }

            if (subject.tests) {
                result += buildTests(subject.tests, prefix + extension);
            }
        });
    }

    if (section.tests) {
        result += buildTests(section.tests, prefix);
    }

    return result;
}

function buildSubjectSubjects(subjects, prefix) {
    let result = '';
    subjects.forEach((subject, i) => {
        const isLast = i === subjects.length - 1;
        const connector = isLast ? '└── ' : '├── ';
        const extension = isLast ? '    ' : '│   ';

        result += prefix + connector + subject.subject_name + ' (weight: ' + subject.weight + ')\n';

        if (subject.tests) {
            result += buildTests(subject.tests, prefix + extension);
        }
    });
    return result;
}

function buildTests(tests, prefix) {
    let result = '';
    tests.forEach((test, i) => {
        const isLast = i === tests.length - 1;
        const connector = isLast ? '└── ' : '├── ';
        result += prefix + connector + 'Test: ' + test.name + '\n';
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

    const template = criteriaTemplates[templateId];

    // Build proper multi-language criteria with commands for ALL selected languages
    const criteria = buildMultiLanguageCriteria(template.criteria, selectedLanguages);

    // Build setup_config for all selected languages
    const setupConfig = buildMultiLanguageSetupConfig(selectedLanguages);

    const payload = {
        external_assignment_id: assignmentId,
        template_name: "input_output",
        languages: selectedLanguages,
        criteria_config: criteria,
        setup_config: setupConfig
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
            setup_commands: ["javac Calculator.java"]
        },
        node: {
            required_files: ["calculator.js"],
            setup_commands: []
        },
        cpp: {
            required_files: ["calculator.cpp"],
            setup_commands: ["g++ calculator.cpp -o calculator"]
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

function copyJson() {
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


