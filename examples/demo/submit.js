/* Submit Page Logic */

const codeExamples = {
    python: {
        simple: `# Simple Calculator - Python Version
# This calculator adds two numbers from stdin

a = int(input())
b = int(input())
print(a + b)`,
        advanced: `# Advanced Calculator - Python Version
# Supports multiple operations: add, subtract, multiply, divide

def main():
    try:
        a = int(input())
        b = int(input())
        print(a + b)
    except Exception as e:
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()`,
        broken: `# Broken Calculator - Python Version
# This calculator has bugs

a = int(input())
b = int(input())
# Bug: subtracts instead of adds
print(a - b)`
    },
    java: {
        simple: `// Simple Calculator - Java Version
import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int a = scanner.nextInt();
        int b = scanner.nextInt();
        System.out.println(a + b);
        scanner.close();
    }
}`,
        advanced: `// Advanced Calculator - Java Version
import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        try {
            Scanner scanner = new Scanner(System.in);
            int a = scanner.nextInt();
            int b = scanner.nextInt();
            System.out.println(a + b);
            scanner.close();
        } catch (Exception e) {
            System.out.println("Error: Invalid input");
        }
    }
}`,
        broken: `// Broken Calculator - Java Version
import java.util.Scanner;

public class Calculator {
    public static void main(String[] args) {
        Scanner scanner = new Scanner(System.in);
        int a = scanner.nextInt();
        int b = scanner.nextInt();
        System.out.println(a - b); // Bug: subtracts instead of adds
        scanner.close();
    }
}`
    },
    node: {
        simple: `// Simple Calculator - JavaScript/Node.js Version
const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

const lines = [];

rl.on('line', (line) => {
    lines.push(line.trim());
    if (lines.length === 2) {
        const a = parseInt(lines[0]);
        const b = parseInt(lines[1]);
        console.log(a + b);
        rl.close();
    }
});`,
        advanced: `// Advanced Calculator - JavaScript/Node.js Version
const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

const lines = [];

rl.on('line', (line) => {
    lines.push(line.trim());
    if (lines.length === 2) {
        try {
            const a = parseInt(lines[0]);
            const b = parseInt(lines[1]);
            console.log(a + b);
        } catch (e) {
            console.log("Error: Invalid input");
        }
        rl.close();
    }
});`,
        broken: `// Broken Calculator - JavaScript/Node.js Version
const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

const lines = [];

rl.on('line', (line) => {
    lines.push(line.trim());
    if (lines.length === 2) {
        const a = parseInt(lines[0]);
        const b = parseInt(lines[1]);
        console.log(a - b); // Bug: subtracts instead of adds
        rl.close();
    }
});`
    },
    cpp: {
        simple: `// Simple Calculator - C++ Version
#include <iostream>

int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a + b << std::endl;
    return 0;
}`,
        advanced: `// Advanced Calculator - C++ Version
#include <iostream>

int main() {
    try {
        int a, b;
        std::cin >> a >> b;
        std::cout << a + b << std::endl;
    } catch (...) {
        std::cout << "Error: Invalid input" << std::endl;
    }
    return 0;
}`,
        broken: `// Broken Calculator - C++ Version
#include <iostream>

int main() {
    int a, b;
    std::cin >> a >> b;
    std::cout << a - b << std::endl; // Bug: subtracts instead of adds
    return 0;
}`
    }
};

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

function updateCode() {
    const language = document.getElementById('language').value;
    const example = document.getElementById('codeExample').value;

    document.getElementById('sourceCode').value = codeExamples[language][example];
    document.getElementById('filename').value = filenameMap[language];

    updateRequestPreview();
}

function updateRequestPreview() {
    const payload = {
        assignment_id: document.getElementById('assignmentId').value,
        user_id: document.getElementById('userId').value,
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
    } else {
        showMessage('submitResult', `Error: ${result.data.error || 'Failed to get result'}`, 'error');
    }
}

function updateResultDisplay(data) {
    // Update score
    const score = data.grade?.final_score !== undefined ? data.grade.final_score : '--';
    document.getElementById('scoreValue').textContent = score;

    // Update status
    document.getElementById('statusValue').textContent = data.status || '--';

    // Update score breakdown
    if (data.grade) {
        document.getElementById('baseValue').textContent = data.grade.base_score || 0;
        document.getElementById('bonusValue').textContent = data.grade.bonus_score || 0;
        document.getElementById('penaltyValue').textContent = data.grade.penalty_score || 0;
    }

    // Update result tree
    if (data.grade?.result_tree) {
        document.getElementById('resultTree').textContent = renderResultTree(data.grade.result_tree);
    } else {
        document.getElementById('resultTree').textContent = 'No result tree available';
    }
}

function renderResultTree(node, prefix = '', isLast = true) {
    let result = '';
    const connector = isLast ? '└── ' : '├── ';
    const extension = isLast ? '    ' : '│   ';

    if (node.name) {
        result += prefix + connector + node.name;
        if (node.score !== undefined && node.total_weight !== undefined) {
            result += ` [${node.score}/${node.total_weight}]`;
        }
        result += '\n';
    }

    if (node.children && node.children.length > 0) {
        node.children.forEach((child, i) => {
            const childIsLast = i === node.children.length - 1;
            result += renderResultTree(child, prefix + (node.name ? extension : ''), childIsLast);
        });
    }

    return result;
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

    // Get result immediately
    getResult();

    // Then poll every 2 seconds
    pollingInterval = setInterval(() => {
        getResult();
    }, 2000);
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
    document.getElementById('pollBtn').textContent = 'Start Polling';
    document.getElementById('pollingStatus').style.display = 'none';
}


