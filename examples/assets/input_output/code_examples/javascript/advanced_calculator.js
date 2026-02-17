// Advanced Calculator - JavaScript/Node.js Version
// Supports multiple operations: add, subtract, multiply, divide, power, modulo, sqrt

const readline = require('readline');

const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

const lines = [];

rl.on('line', (line) => {
    lines.push(line.trim());

    // Check if we have enough input
    if (lines.length >= 1) {
        const operation = lines[0].toLowerCase();

        if (operation === 'sqrt' && lines.length === 2) {
            const num = parseFloat(lines[1]);
            if (isNaN(num) || num < 0) {
                console.log("Error: Invalid input");
            } else {
                console.log(Math.floor(Math.sqrt(num)));
            }
            rl.close();
            return;
        }

        if (lines.length === 3) {
            processCalculation();
            rl.close();
        }
    }
});

function processCalculation() {
    const operation = lines[0].toLowerCase();
    const a = parseInt(lines[1]);
    const b = parseInt(lines[2]);

    if (isNaN(a) || isNaN(b)) {
        console.log("Error: Invalid input");
        return;
    }

    switch (operation) {
        case 'add':
            console.log(a + b);
            break;
        case 'subtract':
            console.log(a - b);
            break;
        case 'multiply':
            console.log(a * b);
            break;
        case 'divide':
            if (b === 0) {
                console.log("Error: Division by zero");
            } else {
                console.log(Math.floor(a / b));
            }
            break;
        case 'power':
            console.log(Math.pow(a, b));
            break;
        case 'modulo':
            console.log(a % b);
            break;
        default:
            console.log("Error: Unknown operation");
    }
}

