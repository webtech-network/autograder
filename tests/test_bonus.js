// test_bonus.js
const { Calculator } = require('../submission/answer');
const fs = require('fs');
const results = [];
const subject = 'extras';

function recordResult(test, status, message = null) {
  results.push({ test, status, message, subject });
}

const calc = new Calculator();

try {
  recordResult('test_add_float', Math.abs(calc.add(0.1, 0.2) - 0.3) < 1e-9 ? 'passed' : 'failed', '0.1 + 0.2 should be close to 0.3');
  recordResult('test_large_numbers', calc.multiply(1e6, 1e6) === 1e12 ? 'passed' : 'failed', '1e6 * 1e6 should be 1e12');
} catch (e) {
  recordResult('test_bonus_exception', 'failed', e.message);
} finally {
  fs.writeFileSync('./results/test_bonus_results.json', JSON.stringify(results, null, 2));
}