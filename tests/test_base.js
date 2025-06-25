// test_base.js
const { Calculator } = require('../submission/answer');
const fs = require('fs');
const results = [];
const subject = 'arithmetic';

function recordResult(test, status, message = null) {
  results.push({ test, status, message, subject });
}

const calc = new Calculator();

try {
  recordResult('test_add', calc.add(2, 3) === 5 ? 'passed' : 'failed', '2 + 3 should be 5');
  recordResult('test_subtract', calc.subtract(5, 2) === 3 ? 'passed' : 'failed', '5 - 2 should be 3');
  recordResult('test_multiply', calc.multiply(4, 3) === 12 ? 'passed' : 'failed', '4 * 3 should be 12');
  recordResult('test_divide', calc.divide(10, 2) === 5 ? 'passed' : 'failed', '10 / 2 should be 5');
} catch (e) {
  recordResult('test_base_exception', 'failed', e.message);
} finally {
  fs.writeFileSync('test_base_results.json', JSON.stringify(results, null, 2));
}