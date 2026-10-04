/* Shared JavaScript for Autograder Demo */

// API URL Management
function getApiUrl() {
    return localStorage.getItem('autograder_api_url') || 'http://localhost:8000';
}

function saveApiUrl(url) {
    localStorage.setItem('autograder_api_url', url.replace(/\/$/, ''));
}

function loadApiUrl() {
    const stored = getApiUrl();
    const input = document.getElementById('apiUrl');
    if (input) {
        input.value = stored;
        input.addEventListener('change', (e) => {
            saveApiUrl(e.target.value);
        });
    }
}

// Tokens stay in this browser session, separate from the saved API URL.
function loadApiToken() {
    const input = document.getElementById('apiToken');
    if (!input) return;
    input.value = sessionStorage.getItem('autograder_integration_token') || '';
    input.addEventListener('change', event => {
        sessionStorage.setItem('autograder_integration_token', event.target.value);
    });
}

// API Call Helper
async function apiCall(endpoint, method = 'GET', body = null, headers = {}) {
    const url = getApiUrl() + endpoint;
    const startTime = Date.now();

    const opts = {
        method,
        headers: { 'Content-Type': 'application/json', ...headers }
    };

    const token = sessionStorage.getItem('autograder_integration_token');
    if (token) opts.headers.Authorization = `Bearer ${token}`;

    if (body) {
        opts.body = JSON.stringify(body);
    }

    try {
        const res = await fetch(url, opts);
        const duration = Date.now() - startTime;
        const data = await res.json();

        return {
            ok: res.ok,
            status: res.status,
            data,
            duration
        };
    } catch (e) {
        return {
            ok: false,
            status: 0,
            data: { error: e.message },
            duration: Date.now() - startTime
        };
    }
}

// Display API Response
function displayResponse(result, elementId = 'apiResponse', statusCodeId = 'statusCode', responseTimeId = 'responseTime') {
    const responseEl = document.getElementById(elementId);
    const statusEl = document.getElementById(statusCodeId);
    const timeEl = document.getElementById(responseTimeId);

    if (responseEl) {
        responseEl.textContent = JSON.stringify(result.data, null, 2);
    }

    if (statusEl) {
        statusEl.textContent = result.status;
        statusEl.className = 'status-code ' + (result.ok ? 'success' : 'error');
    }

    if (timeEl) {
        timeEl.textContent = `${result.duration}ms`;
    }
}

// Show Message
function showMessage(elementId, message, type = 'success') {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.textContent = message;
    el.className = `result-message ${type}`;
    el.style.display = 'block';

    setTimeout(() => {
        el.style.display = 'none';
    }, 5000);
}

// Full v1 definitions are shared with the checked-in teacher examples.
const criteriaTemplates = {
    "1": {name: "Base Only", description: "Two-number addition", file: "1_base_only_simple.json"},
    "2": {name: "Base + Bonus", description: "Addition with extra credit", file: "2_base_and_bonus.json"},
    "3": {name: "Base + Bonus + Penalty", description: "Addition and error handling", file: "3_base_bonus_penalty.json"},
    "4": {name: "With Subjects", description: "Operation-based calculator", file: "4_with_subjects.json"},
    "5": {name: "Nested Subjects", description: "Operation-based advanced calculator", file: "5_nested_subjects.json"}
};
let templatesPromise = null;
function loadCriteriaTemplates() {
    if (!templatesPromise) {
        templatesPromise = Promise.all(Object.values(criteriaTemplates).map(async template => {
            const response = await fetch(`../assets/input_output/criteria_examples/${template.file}`);
            if (!response.ok) throw new Error(`Could not load ${template.file}`);
            template.definition = await response.json();
        })).catch(error => { templatesPromise = null; throw error; });
    }
    return templatesPromise;
}

const languageCommands = {
    python: "python3 calculator.py", java: "java Calculator",
    node: "node calculator.js", cpp: "./calculator"
};

function renderTree(node, prefix = '', isLast = true) {
    const connector = isLast ? '└── ' : '├── ';
    const extension = isLast ? '    ' : '│   ';
    let result = prefix + connector + node.name;
    if (node.score !== undefined) result += ` [${node.score}/100]`;
    if (node.id) result += ` (${node.id})`;
    result += '\n';
    const children = [node.base, node.bonus, node.penalty,
        ...(node.subjects || []), ...(node.tests || [])].filter(Boolean);
    children.forEach((child, index) => {
        result += renderTree(child, prefix + extension, index === children.length - 1);
    });
    return result;
}
