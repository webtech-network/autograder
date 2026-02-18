/* Configuration Page Logic */

document.addEventListener('DOMContentLoaded', () => {
    updatePreview();
});

function updatePreview() {
    const templateId = document.getElementById('criteriaTemplate').value;
    const language = document.getElementById('language').value;

    const template = criteriaTemplates[templateId];
    document.getElementById('templateDescription').textContent = template.description;

    // Update tree preview
    const criteria = replaceCmdPlaceholder(template.criteria, language);
    document.getElementById('treePreview').textContent = buildCriteriaTree(criteria);

    // Update JSON preview
    document.getElementById('jsonPreview').value = JSON.stringify(criteria, null, 2);
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
    const language = document.getElementById('language').value;

    if (!assignmentId) {
        showMessage('createResult', 'Please enter an assignment ID', 'error');
        return;
    }

    const template = criteriaTemplates[templateId];
    const criteria = replaceCmdPlaceholder(template.criteria, language);

    const payload = {
        assignment_id: assignmentId,
        criteria: criteria,
        feedback: {
            positive_feedback: [
                "Great job!",
                "Excellent work!",
                "Well done!"
            ],
            negative_feedback: [
                "Please review the requirements.",
                "Try again.",
                "Check your implementation."
            ],
            hints: {
                "Addition": "Make sure you're adding the two numbers correctly.",
                "Subtraction": "Double-check your subtraction logic."
            }
        }
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


