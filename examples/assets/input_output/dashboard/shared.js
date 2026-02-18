/* Shared JavaScript utilities for Autograder Testing Dashboard */

// ============================================
// API URL Management
// ============================================

function getApiUrl() {
    return localStorage.getItem('autograder_api_url') || 'http://localhost:8000';
}

function saveApiUrl(url) {
    localStorage.setItem('autograder_api_url', url.replace(/\/$/, ''));
}

function loadApiUrl() {
    const stored = getApiUrl();
    const input = document.getElementById('apiUrl');
    if (input) input.value = stored;
}

// ============================================
// API Request Helper
// ============================================

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

// ============================================
// Criteria Templates
// ============================================

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
                        {"name": "inputs", "value": ["multiply", "6", "7"]},
                        {"name": "expected_output", "value": "42"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    },
    "5": {
        name: "Nested Subjects",
        description: "Complex hierarchical structure",
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
                                "weight": 50,
                                "tests": [
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["add", "5", "3"]},
                                        {"name": "expected_output", "value": "8"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]},
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["add", "-5", "10"]},
                                        {"name": "expected_output", "value": "5"},
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
                                    ]},
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["subtract", "5", "10"]},
                                        {"name": "expected_output", "value": "-5"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]}
                                ]
                            }
                        ]
                    },
                    {
                        "subject_name": "Advanced Operations",
                        "weight": 40,
                        "subjects": [
                            {
                                "subject_name": "Multiplication",
                                "weight": 50,
                                "tests": [
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["multiply", "6", "7"]},
                                        {"name": "expected_output", "value": "42"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]}
                                ]
                            },
                            {
                                "subject_name": "Division",
                                "weight": 50,
                                "tests": [
                                    { "name": "expect_output", "parameters": [
                                        {"name": "inputs", "value": ["divide", "20", "5"]},
                                        {"name": "expected_output", "value": "4"},
                                        {"name": "program_command", "value": "CMD"}
                                    ]}
                                ]
                            }
                        ]
                    }
                ]
            },
            "bonus": {
                "weight": 20,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["power", "2", "8"]},
                        {"name": "expected_output", "value": "256"},
                        {"name": "program_command", "value": "CMD"}
                    ]},
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["modulo", "17", "5"]},
                        {"name": "expected_output", "value": "2"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            },
            "penalty": {
                "weight": 15,
                "tests": [
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["divide", "10", "0"]},
                        {"name": "expected_output", "value": "Error: Division by zero"},
                        {"name": "program_command", "value": "CMD"}
                    ]},
                    { "name": "expect_output", "parameters": [
                        {"name": "inputs", "value": ["invalid", "5", "3"]},
                        {"name": "expected_output", "value": "Error: Unknown operation"},
                        {"name": "program_command", "value": "CMD"}
                    ]}
                ]
            }
        }
    }
};

// ============================================
// Code Examples
// ============================================

const codeExamples = {
    python: {
        simple: `a = int(input())
b = int(input())
print(a + b)`,
        advanced: `import math

operation = input().strip().lower()

if operation == "sqrt":
    num = float(input())
    print(int(math.sqrt(num)) if num >= 0 else "Error: Invalid input")
else:
    try:
        a, b = int(input()), int(input())
    except:
        print("Error: Invalid input")
        exit()
    
    ops = {
        "add": a + b,
        "subtract": a - b,
        "multiply": a * b,
        "divide": "Error: Division by zero" if b == 0 else a // b,
        "power": a ** b,
        "modulo": a % b
    }
    print(ops.get(operation, "Error: Unknown operation"))`,
        broken: `a = int(input())
b = int(input())
print(a - b)  # Bug: subtracts instead of adds`
    },
    java: {
        simple: `import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        System.out.println(sc.nextInt() + sc.nextInt());
    }
}`,
        advanced: `import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        String op = sc.nextLine().trim().toLowerCase();
        
        if (op.equals("sqrt")) {
            double n = Double.parseDouble(sc.nextLine());
            System.out.println(n < 0 ? "Error: Invalid input" : (int)Math.sqrt(n));
            return;
        }
        
        int a, b;
        try {
            a = Integer.parseInt(sc.nextLine().trim());
            b = Integer.parseInt(sc.nextLine().trim());
        } catch (Exception e) {
            System.out.println("Error: Invalid input");
            return;
        }
        
        switch(op) {
            case "add": System.out.println(a + b); break;
            case "subtract": System.out.println(a - b); break;
            case "multiply": System.out.println(a * b); break;
            case "divide": System.out.println(b == 0 ? "Error: Division by zero" : a/b); break;
            case "power": System.out.println((int)Math.pow(a,b)); break;
            case "modulo": System.out.println(a % b); break;
            default: System.out.println("Error: Unknown operation");
        }
    }
}`,
        broken: `import java.util.Scanner;
public class Calculator {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);
        System.out.println(sc.nextInt() - sc.nextInt()); // Bug!
    }
}`
    },
    javascript: {
        simple: `const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];
rl.on('line', l => {
    lines.push(l);
    if (lines.length === 2) {
        console.log(parseInt(lines[0]) + parseInt(lines[1]));
        rl.close();
    }
});`,
        advanced: `const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];

rl.on('line', l => {
    lines.push(l.trim());
    const op = lines[0].toLowerCase();
    
    if (op === 'sqrt' && lines.length === 2) {
        const n = parseFloat(lines[1]);
        console.log(n < 0 ? "Error: Invalid input" : Math.floor(Math.sqrt(n)));
        rl.close();
    } else if (lines.length === 3) {
        const a = parseInt(lines[1]), b = parseInt(lines[2]);
        if (isNaN(a) || isNaN(b)) { console.log("Error: Invalid input"); }
        else {
            const ops = {
                add: a + b, subtract: a - b, multiply: a * b,
                divide: b === 0 ? "Error: Division by zero" : Math.floor(a/b),
                power: Math.pow(a, b), modulo: a % b
            };
            console.log(ops[op] !== undefined ? ops[op] : "Error: Unknown operation");
        }
        rl.close();
    }
});`,
        broken: `const readline = require('readline');
const rl = readline.createInterface({ input: process.stdin });
const lines = [];
rl.on('line', l => {
    lines.push(l);
    if (lines.length === 2) {
        console.log(parseInt(lines[0]) - parseInt(lines[1])); // Bug!
        rl.close();
    }
});`
    },
    cpp: {
        simple: `#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}`,
        advanced: `#include <iostream>
#include <string>
#include <cmath>
#include <algorithm>

int main() {
    std::string op;
    std::getline(std::cin, op);
    std::transform(op.begin(), op.end(), op.begin(), ::tolower);
    
    if (op == "sqrt") {
        double n; std::cin >> n;
        if (n < 0) std::cout << "Error: Invalid input";
        else std::cout << (int)sqrt(n);
        std::cout << std::endl;
        return 0;
    }
    
    int a, b;
    if (!(std::cin >> a >> b)) {
        std::cout << "Error: Invalid input" << std::endl;
        return 0;
    }
    
    if (op == "add") std::cout << a + b;
    else if (op == "subtract") std::cout << a - b;
    else if (op == "multiply") std::cout << a * b;
    else if (op == "divide") {
        if (b == 0) std::cout << "Error: Division by zero";
        else std::cout << a / b;
    }
    else if (op == "power") std::cout << (int)pow(a, b);
    else if (op == "modulo") std::cout << a % b;
    else std::cout << "Error: Unknown operation";
    std::cout << std::endl;
    return 0;
}`,
        broken: `#include <iostream>
int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a - b << std::endl; // Bug!
    return 0;
}`
    }
};

const programCommands = {
    python: 'python3 calculator.py',
    java: 'java Calculator',
    javascript: 'node calculator.js',
    cpp: './calculator'
};

const setupConfigs = {
    python: {
        required_files: ['calculator.py'],
        setup_commands: []
    },
    java: {
        required_files: ['Calculator.java'],
        setup_commands: [
            {
                name: 'Compile Calculator.java',
                command: 'javac Calculator.java'
            }
        ]
    },
    node: {
        required_files: ['calculator.js'],
        setup_commands: []
    },
    cpp: {
        required_files: ['calculator.cpp'],
        setup_commands: [
            {
                name: 'Compile calculator.cpp',
                command: 'g++ calculator.cpp -o calculator'
            }
        ]
    }
};

const fileExtensions = {
    python: '.py',
    java: '.java',
    node: '.js',
    cpp: '.cpp'
};

// ============================================
// Tree Rendering
// ============================================

function renderTree(criteria) {
    const lines = [];

    const indent = (level) => '│  '.repeat(level);
    const branch = (isLast) => isLast ? '└─ ' : '├─ ';

    const renderTests = (tests, level) => {
        tests.forEach((test, idx) => {
            const isLast = idx === tests.length - 1;
            const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
            const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
            lines.push(`${indent(level)}${branch(isLast)}<span class="tree-test">🧪 ${test.name}</span>`);
            lines.push(`${indent(level)}${isLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
        });
    };

    const renderSubjects = (subjects, level) => {
        subjects.forEach((s, idx) => {
            const isLast = idx === subjects.length - 1;
            lines.push(`${indent(level)}${branch(isLast)}<span class="tree-subject">📁 ${s.subject_name}</span> <span class="tree-param">(${s.weight}%)</span>`);

            const nextLevel = level + (isLast ? 0 : 0) + 1;
            const childIndent = indent(level) + (isLast ? '   ' : '│  ');

            if (s.subjects) {
                s.subjects.forEach((child, childIdx) => {
                    const childIsLast = childIdx === s.subjects.length - 1 && !s.tests;
                    renderSubjectsWithIndent(child, childIndent, childIsLast, s.subjects.length - 1 === childIdx);
                });
            }
            if (s.tests) {
                s.tests.forEach((test, testIdx) => {
                    const testIsLast = testIdx === s.tests.length - 1;
                    const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
                    const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
                    lines.push(`${childIndent}${testIsLast ? '└─ ' : '├─ '}<span class="tree-test">🧪 ${test.name}</span>`);
                    lines.push(`${childIndent}${testIsLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
                });
            }
        });
    };

    const renderSubjectsWithIndent = (s, baseIndent, isLast, isActuallyLast) => {
        lines.push(`${baseIndent}${isActuallyLast ? '└─ ' : '├─ '}<span class="tree-subject">📁 ${s.subject_name}</span> <span class="tree-param">(${s.weight}%)</span>`);

        const childIndent = baseIndent + (isActuallyLast ? '   ' : '│  ');

        if (s.subjects) {
            s.subjects.forEach((child, idx) => {
                renderSubjectsWithIndent(child, childIndent, false, idx === s.subjects.length - 1 && !s.tests);
            });
        }
        if (s.tests) {
            s.tests.forEach((test, idx) => {
                const testIsLast = idx === s.tests.length - 1;
                const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
                const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
                lines.push(`${childIndent}${testIsLast ? '└─ ' : '├─ '}<span class="tree-test">🧪 ${test.name}</span>`);
                lines.push(`${childIndent}${testIsLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
            });
        }
    };

    // Base
    lines.push(`<span class="tree-category">📦 BASE</span> <span class="tree-param">(${criteria.base.weight}%)</span>`);
    if (criteria.base.subjects) {
        criteria.base.subjects.forEach((s, idx) => {
            const isLast = idx === criteria.base.subjects.length - 1 && !criteria.base.tests;
            renderSubjectsWithIndent(s, '', false, isLast);
        });
    }
    if (criteria.base.tests) {
        criteria.base.tests.forEach((test, idx) => {
            const isLast = idx === criteria.base.tests.length - 1;
            const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
            const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
            lines.push(`${isLast ? '└─ ' : '├─ '}<span class="tree-test">🧪 ${test.name}</span>`);
            lines.push(`${isLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
        });
    }

    // Bonus
    if (criteria.bonus) {
        lines.push('');
        lines.push(`<span class="tree-category bonus">⭐ BONUS</span> <span class="tree-param">(+${criteria.bonus.weight}%)</span>`);
        if (criteria.bonus.tests) {
            criteria.bonus.tests.forEach((test, idx) => {
                const isLast = idx === criteria.bonus.tests.length - 1;
                const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
                const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
                lines.push(`${isLast ? '└─ ' : '├─ '}<span class="tree-test">🧪 ${test.name}</span>`);
                lines.push(`${isLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
            });
        }
    }

    // Penalty
    if (criteria.penalty) {
        lines.push('');
        lines.push(`<span class="tree-category penalty">⚠️ PENALTY</span> <span class="tree-param">(-${criteria.penalty.weight}%)</span>`);
        if (criteria.penalty.tests) {
            criteria.penalty.tests.forEach((test, idx) => {
                const isLast = idx === criteria.penalty.tests.length - 1;
                const inputs = test.parameters.find(p => p.name === 'inputs')?.value || [];
                const expected = test.parameters.find(p => p.name === 'expected_output')?.value || '';
                lines.push(`${isLast ? '└─ ' : '├─ '}<span class="tree-test">🧪 ${test.name}</span>`);
                lines.push(`${isLast ? '   ' : '│  '}<span class="tree-param">   [${inputs.join(', ')}] → "${expected}"</span>`);
            });
        }
    }

    return lines.join('\n');
}

// ============================================
// Utility Functions
// ============================================

function getCriteriaWithCommand(templateId, language) {
    const template = JSON.parse(JSON.stringify(criteriaTemplates[templateId].criteria));
    const cmd = programCommands[language];

    const updateCmd = (obj) => {
        if (Array.isArray(obj)) {
            obj.forEach(updateCmd);
        } else if (typeof obj === 'object' && obj !== null) {
            if (obj.parameters) {
                const param = obj.parameters.find(p => p.name === 'program_command');
                if (param) param.value = cmd;
            }
            Object.values(obj).forEach(updateCmd);
        }
    };

    updateCmd(template);
    return template;
}

function showResponse(elementId, result) {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.innerHTML = `<div class="response-info">
        <span class="status-code ${result.ok ? 'success' : 'error'}">${result.status || 'ERR'}</span>
        <span class="response-time">${result.duration}ms</span>
    </div>
    <pre>${JSON.stringify(result.data, null, 2)}</pre>`;
}

