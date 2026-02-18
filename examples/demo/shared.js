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

// API Call Helper
async function apiCall(endpoint, method = 'GET', body = null) {
    const url = getApiUrl() + endpoint;
    const startTime = Date.now();

    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' }
    };

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

// Criteria Templates
const criteriaTemplates = {
    "1": {
        name: "Base Only (Simple)",
        description: "Simple test suite with only base tests",
        criteria: {
            "test_library": "input_output",
            "base": {
                "weight": 100,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["5", "3"]},
                        {"name": "expected_output", "value": "8"},
                        {"name": "program_command", "value": "CMD"}
                    ]},
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["10", "4"]},
                        {"name": "expected_output", "value": "14"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    },
    "2": {
        name: "Base + Bonus",
        description: "Base tests with bonus points",
        criteria: {
            "test_library": "input_output",
            "base": {
                "weight": 100,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["5", "3"]},
                        {"name": "expected_output", "value": "8"},
                        {"name": "program_command", "value": "CMD"}
                    ]},
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["10", "4"]},
                        {"name": "expected_output", "value": "14"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            },
            "bonus": {
                "weight": 15,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["-5", "10"]},
                        {"name": "expected_output", "value": "5"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    },
    "3": {
        name: "Base + Bonus + Penalty",
        description: "Full category support",
        criteria: {
            "test_library": "input_output",
            "base": {
                "weight": 100,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["5", "3"]},
                        {"name": "expected_output", "value": "8"},
                        {"name": "program_command", "value": "CMD"}
                    ]},
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["10", "4"]},
                        {"name": "expected_output", "value": "14"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            },
            "bonus": {
                "weight": 15,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["-5", "10"]},
                        {"name": "expected_output", "value": "5"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            },
            "penalty": {
                "weight": 20,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["abc", "xyz"]},
                        {"name": "expected_output", "value": "Error: Invalid input"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    },
    "4": {
        name: "With Subjects",
        description: "Organized with subject groupings",
        criteria: {
            "test_library": "input_output",
            "base": {
                "weight": 100,
                "subjects": [
                    {
                        "subject_name": "Addition",
                        "weight": 50,
                        "tests": [
                            { "name": "expect_output", "parameters": [
                                {"name": "inputs", "value": ["add", "5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {"name": "program_command", "value": "CMD"}
                            ]},
                            { "name": "expect_output", "parameters": [
                                {"name": "inputs", "value": ["add", "0", "0"]},
                                {"name": "expected_output", "value": "0"},
                                {"name": "program_command", "value": "CMD"}
                            ]}
                        ]
                    },
                    {
                        "subject_name": "Subtraction",
                        "weight": 50,
                        "tests": [
                            { "name": "expect_output", "parameters": [
                                {"name": "inputs", "value": ["subtract", "10", "4"]},
                                {"name": "expected_output", "value": "6"},
                                {"name": "program_command", "value": "CMD"}
                            ]}
                        ]
                    }
                ]
            },
            "bonus": {
                "weight": 15,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["multiply", "5", "3"]},
                        {"name": "expected_output", "value": "15"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    },
    "5": {
        name: "Nested Subjects",
        description: "Complex nested subject structure",
        criteria: {
            "test_library": "input_output",
            "base": {
                "weight": 100,
                "subjects": [
                    {
                        "subject_name": "Basic Operations",
                        "weight": 60,
                        "subjects": [
                            {
                                "subject_name": "Addition",
                                "weight": 30,
                                "tests": [
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["5", "3"]},
                                        {"name": "expected_output", "value": "8"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]}
                                ]
                            },
                            {
                                "subject_name": "Subtraction",
                                "weight": 30,
                                "tests": [
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["10", "4"]},
                                        {"name": "expected_output", "value": "6"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]}
                                ]
                            }
                        ]
                    },
                    {
                        "subject_name": "Advanced Operations",
                        "weight": 40,
                        "tests": [
                            { "name": "expect_output", "parameters": [
                                {"name": "inputs", "value": ["100", "25"]},
                                {"name": "expected_output", "value": "125"},
                                {"name": "program_command", "value": "CMD"}
                            ]}
                        ]
                    }
                ]
            }
        }
    }
};

// Language Commands
const languageCommands = {
    python: "python calculator.py",
    java: "java Calculator",
    node: "node calculator.js",
    cpp: "./calculator"
};

// Replace CMD placeholder in criteria
function replaceCmdPlaceholder(criteria, language) {
    const cmd = languageCommands[language] || languageCommands.python;
    const json = JSON.stringify(criteria);
    const replaced = json.replace(/"CMD"/g, `"${cmd}"`);
    return JSON.parse(replaced);
}

// Render Tree (simple text-based)
function renderTree(node, prefix = '', isLast = true) {
    let result = '';
    const connector = isLast ? '└── ' : '├── ';
    const extension = isLast ? '    ' : '│   ';

    if (node.name) {
        result += prefix + connector + node.name;
        if (node.weight !== undefined) result += ` (${node.weight})`;
        if (node.score !== undefined) result += ` [${node.score}/${node.total_weight}]`;
        result += '\n';
    }

    if (node.children) {
        node.children.forEach((child, i) => {
            const childIsLast = i === node.children.length - 1;
            result += renderTree(child, prefix + (node.name ? extension : ''), childIsLast);
        });
    }

    return result;
}

