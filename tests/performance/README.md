# Performance Testing Guide

This directory contains tools for testing the autograder's concurrent performance and load handling capabilities.

## Tools Available

### 1. Concurrent Submissions Test (`test_concurrent_submissions.py`)

**Comprehensive performance testing with detailed metrics.**

**Features:**
- Creates test assignment automatically
- Submits multiple requests concurrently
- Tracks submission and grading times
- Tests all 4 languages (Python, Java, Node.js, C++)
- Generates detailed performance reports

**Usage:**
```bash
# Run all scenarios (5, 10, 20, 50 concurrent submissions)
python tests/performance/test_concurrent_submissions.py

# The script will:
# 1. Create a test assignment
# 2. Run multiple test scenarios
# 3. Track timing and success rates
# 4. Generate detailed metrics
```

**Output:**
```
PERFORMANCE METRICS
============================================================
Total Submissions:    10
Successful:           10 (100.0%)
Failed:               0
Total Time:           2.34s
Throughput:           4.27 submissions/sec

Submission Times:
  Average:            234ms
  Min:                156ms
  Max:                412ms

Grading Times:
  Average:            1823ms

Language Breakdown:
  python  :          3/3 (100.0%)
  java    :          2/2 (100.0%)
  node    :          3/3 (100.0%)
  cpp     :          2/2 (100.0%)
```

---

### 2. Stress Test (`test_stress.py`)

**Quick and simple stress testing.**

**Features:**
- Fast execution
- Simple metrics
- Customizable submission count
- No grading wait (submission-only testing)

**Usage:**
```bash
# Run with default scenarios (5, 10, 20, 50 submissions)
python tests/performance/test_stress.py

# Run with custom count
python tests/performance/test_stress.py 100

# Before running, make sure the assignment exists:
# - Assignment ID: "calc-multi-lang"
# - Or modify ASSIGNMENT_ID in the script
```

**Example:**
```bash
$ python tests/performance/test_stress.py 20

============================================================
STRESS TEST: 20 submissions
============================================================

Submitting 20 requests...

============================================================
RESULTS
============================================================
Total Time:      1.23s
Successful:      20/20 (100.0%)
Failed:          0
Throughput:      16.26 req/s
Avg Time:        189ms
Min Time:        142ms
Max Time:        287ms
============================================================
```

---

### 3. Locust Load Testing (`locustfile.py`)

**Web-based load testing with GUI and detailed statistics.**

**Features:**
- Web UI for monitoring
- Configurable user count and spawn rate
- Real-time charts and statistics
- Distributed testing support
- Multiple task types (submit, check status, get config)

**Installation:**
```bash
pip install locust
```

**Usage:**

1. **Create the test assignment first:**
```bash
curl -X POST "http://localhost:8000/api/v1/configs" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "calc-multi-lang",
    "template_name": "input_output",
    "language": "python",
    "criteria_config": {
      "test_library": "input_output",
      "base": {
        "weight": 100,
        "tests": [{
          "name": "expect_output",
          "parameters": [
            {"name": "inputs", "value": ["5", "3"]},
            {"name": "expected_output", "value": "8"},
            {"name": "program_command", "value": {
              "python": "python3 calculator.py",
              "java": "java Calculator",
              "node": "node calculator.js",
              "cpp": "./calculator"
            }}
          ]
        }]
      }
    },
    "setup_config": {"required_files": [], "setup_commands": []}
  }'
```

2. **Start Locust:**
```bash
# With web UI (recommended)
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# Headless mode (no UI)
locust -f tests/performance/locustfile.py \
  --host=http://localhost:8000 \
  --users 10 \
  --spawn-rate 2 \
  --run-time 60s \
  --headless
```

3. **Open the Web UI:**
   - Navigate to http://localhost:8089
   - Set number of users (e.g., 10)
   - Set spawn rate (e.g., 2 users/second)
   - Click "Start Swarming"

4. **Monitor the test:**
   - View real-time statistics
   - See request rates and response times
   - Download detailed reports

**Locust Dashboard Features:**
- Statistics table (requests, failures, response times)
- Charts (RPS, response time distribution)
- Failures log
- Export data (CSV)

---

## Test Scenarios

### Scenario 1: Low Concurrency (5-10 users)
**Purpose:** Baseline performance measurement

```bash
python tests/performance/test_stress.py 10
```

**Expected:**
- 100% success rate
- Low response times (<500ms)
- Stable throughput

---

### Scenario 2: Medium Concurrency (20-50 users)
**Purpose:** Normal load testing

```bash
python tests/performance/test_concurrent_submissions.py
# Or
locust -f tests/performance/locustfile.py --users 30 --spawn-rate 5
```

**Expected:**
- High success rate (>95%)
- Moderate response times (<2s)
- Consistent throughput

---

### Scenario 3: High Concurrency (100+ users)
**Purpose:** Stress testing and breaking point identification

```bash
python tests/performance/test_stress.py 100
# Or
locust -f tests/performance/locustfile.py --users 100 --spawn-rate 10
```

**Metrics to watch:**
- Success rate degradation
- Response time increase
- Error rates
- System resource usage

---

## Interpreting Results

### Key Metrics

1. **Throughput (req/s)**
   - Higher is better
   - Indicates how many submissions/second the system can handle

2. **Response Time**
   - Average: Overall performance
   - P95/P99: Worst-case scenarios
   - Lower is better

3. **Success Rate**
   - Should be >95% under normal load
   - <90% indicates problems

4. **Grading Time**
   - Time to complete grading after submission
   - Varies by language and test complexity

### What to Look For

✅ **Good Performance:**
- Success rate >95%
- Avg response time <1s for submissions
- Stable throughput
- No error spikes

⚠️ **Degraded Performance:**
- Success rate 85-95%
- Avg response time 1-3s
- Occasional timeouts
- Some errors

❌ **Poor Performance:**
- Success rate <85%
- Avg response time >3s
- Frequent timeouts
- Many errors

---

## Optimization Tips

### If Performance is Poor:

1. **Check Database Connections:**
   - Increase connection pool size
   - Monitor slow queries

2. **Sandbox Management:**
   - Verify sandbox pool sizes
   - Check Docker resource limits

3. **API Server:**
   - Increase worker processes
   - Check CPU/memory usage

4. **Background Tasks:**
   - Monitor queue lengths
   - Check task execution times

---

## Monitoring During Tests

### System Resources
```bash
# Monitor CPU and memory
htop

# Monitor Docker containers
docker stats

# Monitor network
iftop
```

### Application Logs
```bash
# Web API logs
tail -f logs/api.log

# Autograder logs
tail -f logs/autograder.log
```

### Database
```bash
# PostgreSQL: Active connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# PostgreSQL: Slow queries
psql -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

---

## Best Practices

1. **Start Small:** Begin with 5-10 concurrent users
2. **Ramp Up Gradually:** Increase load incrementally
3. **Monitor Resources:** Watch CPU, memory, disk I/O
4. **Use Realistic Data:** Test with actual assignment configurations
5. **Test Different Languages:** Ensure all language sandboxes work
6. **Long-Running Tests:** Run for 5-10 minutes to catch memory leaks
7. **Cool Down:** Allow system to recover between tests

---

## Troubleshooting

### Issue: High Failure Rate

**Possible causes:**
- Database connection pool exhausted
- Sandbox pool too small
- API server overloaded
- Network timeouts

**Solutions:**
- Increase connection limits
- Scale sandbox manager
- Add more API workers
- Increase timeout values

---

### Issue: Slow Response Times

**Possible causes:**
- Slow database queries
- Sandbox creation delays
- CPU bottleneck
- Disk I/O bottleneck

**Solutions:**
- Optimize database indexes
- Pre-warm sandbox pools
- Scale horizontally
- Use faster storage

---

### Issue: Memory Growth

**Possible causes:**
- Memory leaks
- Large result trees
- Unclosed connections

**Solutions:**
- Profile with memory_profiler
- Implement result pagination
- Check connection cleanup

---

## Example Test Run

```bash
# 1. Start the autograder API
uvicorn web.main:app --host 0.0.0.0 --port 8000

# 2. In another terminal, run comprehensive test
python tests/performance/test_concurrent_submissions.py

# 3. Or run stress test
python tests/performance/test_stress.py 50

# 4. Or start Locust for interactive testing
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

---

## Performance Targets

Based on typical hardware (4 CPU, 8GB RAM):

| Metric | Target | Good | Acceptable |
|--------|--------|------|------------|
| Throughput | >20 req/s | 10-20 | 5-10 |
| Avg Response Time | <500ms | <1s | <2s |
| P95 Response Time | <1s | <2s | <5s |
| Success Rate | 100% | >98% | >95% |

---

## Need Help?

1. Check logs for error messages
2. Review system resource usage
3. Check database performance
4. Verify sandbox manager is running
5. Test with a single submission first

---

## Contributing

To add new performance tests:

1. Add script to `tests/performance/`
2. Document usage in this README
3. Include example output
4. Note any prerequisites

