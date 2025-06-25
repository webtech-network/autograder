// test_penalty.js
const fs = require('fs');
const results = [];
const subject = 'forbidden';

function recordResult(test, status, message = null) {
  results.push({ test, status, message, subject });
}

try {
  const code = fs.readFileSync('../submission/answer.js', 'utf-8');
  if (/eval\s*\(/.test(code)) {
    recordResult('test_no_eval', 'failed', 'Use of eval is forbidden');
  } else {
    recordResult('test_no_eval', 'passed');
  }
} catch (e) {
  recordResult('test_penalty_exception', 'failed', e.message);
} finally {
  fs.writeFileSync('test_penalty_results.json', JSON.stringify(results, null, 2));
}