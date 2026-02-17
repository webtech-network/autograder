// Simple Calculator - JavaScript/Node.js Version
// This calculator adds two numbers from stdin

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
});

