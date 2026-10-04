/* Submit Page Logic */

const sourceLanguages = {python:'python', java:'java', node:'javascript', cpp:'cpp'};
const sourceExtensions = {python:'py', java:'java', node:'js', cpp:'cpp'};
let sourceLoadSequence = 0;
const filenameMap = {
    python: 'calculator.py',
    java: 'Calculator.java',
    node: 'calculator.js',
    cpp: 'calculator.cpp'
};

let pollingInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    updateCode();
    updateRequestPreview();
});

async function updateCode() {
    const sequence = ++sourceLoadSequence;
    const language = document.getElementById('language').value;
    const example = document.getElementById('codeExample').value;
    const chosen = example === 'broken' ? 'simple' : example;
    const className = chosen === 'advanced' ? 'AdvancedCalculator' : 'SimpleCalculator';
    const basename = language === 'java' ? className : `${chosen}_calculator`;
    try {
        const response = await fetch(`../assets/input_output/code_examples/${sourceLanguages[language]}/${basename}.${sourceExtensions[language]}`);
        if (!response.ok) throw new Error('Could not load sample source');
        let source = await response.text();
        if (sequence !== sourceLoadSequence) return;
        if (language === 'java') source = source.replaceAll(className, 'Calculator');
        if (example === 'broken') source = source.replace(/a \+ b/g, 'a - b');
        document.getElementById('sourceCode').value = source;
        document.getElementById('filename').value = filenameMap[language];
        updateRequestPreview();
    } catch (error) { showMessage('submitResult', error.message, 'error'); }
}

function updateRequestPreview() {
    const payload = {
        external_assignment_id: document.getElementById('assignmentId').value,
        external_user_id: document.getElementById('userId').value,
        username: document.getElementById('username').value,
        language: document.getElementById('language').value,
        files: [
            {
                filename: document.getElementById('filename').value,
                content: document.getElementById('sourceCode').value
            }
        ]
    };

    document.getElementById('requestPreview').textContent = JSON.stringify(payload, null, 2);
}

async function submitCode() {
    const payload = {
        external_assignment_id: document.getElementById('assignmentId').value,
        external_user_id: document.getElementById('userId').value,
        username: document.getElementById('username').value,
        language: document.getElementById('language').value,
        files: [
            {
                filename: document.getElementById('filename').value,
                content: document.getElementById('sourceCode').value
            }
        ]
    };

    if (!payload.external_assignment_id || !payload.external_user_id || !payload.username) {
        showMessage('submitResult', 'Please fill in all required fields', 'error');
        return;
    }

    showMessage('submitResult', 'Submitting code...', 'success');

    const result = await apiCall('/api/v1/submissions', 'POST', payload);

    displayResponse(result);

    if (result.ok) {
        const submissionId = result.data.id;
        document.getElementById('submissionId').value = submissionId;
        showMessage('submitResult', `Submission created! ID: ${submissionId}`, 'success');

        // Auto-fetch result after a short delay
        setTimeout(() => getResult(), 2000);
    } else {
        showMessage('submitResult', `Error: ${result.data.error || 'Failed to submit code'}`, 'error');
    }
}

async function getResult() {
    const submissionId = document.getElementById('submissionId').value;

    if (!submissionId) {
        showMessage('submitResult', 'Please enter a submission ID', 'error');
        return;
    }

    const result = await apiCall(`/api/v1/submissions/${submissionId}`);

    displayResponse(result);

    if (result.ok) {
        updateResultDisplay(result.data);
        if (['completed', 'failed'].includes(result.data.status)) {
            stopPolling();
            const details = await apiCall(`/api/v1/submissions/${submissionId}/details`);
            if (details.ok) updateResultDisplay(details.data);
            else showMessage('submitResult', 'Status received; result details could not be loaded.', 'error');
        }
    } else {
        showMessage('submitResult', 'Failed to retrieve submission status', 'error');
    }
}

function updateResultDisplay(data) {
    const outcome = data.outcome;
    const tree = outcome?.tree;
    document.getElementById('scoreValue').textContent = data.final_score ?? '--';
    document.getElementById('statusValue').textContent = data.status || '--';
    ['base', 'bonus', 'penalty'].forEach(category => {
        document.getElementById(category + 'Value').textContent = tree?.[category]?.score ?? '--';
    });
    document.getElementById('resultTree').textContent = tree ? renderTree(tree)
        : (outcome?.error?.message || data.error?.message || 'Result details are not available yet');
}

function togglePolling() {
    if (pollingInterval) {
        stopPolling();
    } else {
        startPolling();
    }
}

function startPolling() {
    document.getElementById('pollBtn').textContent = 'Stop Polling';
    document.getElementById('pollingStatus').style.display = 'flex';
    pollingInterval = setTimeout(pollNext, 0);
}

async function pollNext() {
    await getResult();
    if (pollingInterval !== null) pollingInterval = setTimeout(pollNext, 2000);
}

function stopPolling() {
    if (pollingInterval !== null) clearTimeout(pollingInterval);
    pollingInterval = null;
    document.getElementById('pollBtn').textContent = 'Start Polling';
    document.getElementById('pollingStatus').style.display = 'none';
}
