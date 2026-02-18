# Quick Start: Performance Testing

## 🚀 Fast Track (5 minutes)

### Step 1: Start the API
```bash
# Terminal 1
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

### Step 2: Setup Test Assignment
```bash
# Terminal 2
./tests/performance/setup.sh
```

### Step 3: Run Quick Test
```bash
# Test with 10 concurrent submissions
python tests/performance/test_stress.py 10
```

**Done!** You've just tested concurrent submissions.

---

## 📊 Want More Details?

### Test with Comprehensive Metrics
```bash
python tests/performance/test_concurrent_submissions.py
```

This will:
- Test 4 different scenarios (5, 10, 20, 50 submissions)
- Test all 4 languages (Python, Java, Node.js, C++)
- Track submission AND grading times
- Generate detailed performance reports

---

## 🎛️ Interactive Load Testing

### Install Locust
```bash
pip install locust
```

### Start Locust
```bash
locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

### Open Web UI
1. Go to http://localhost:8089
2. Enter number of users: **10**
3. Enter spawn rate: **2**
4. Click **Start Swarming**
5. Watch real-time statistics!

---

## 📈 Monitor Performance

### Real-Time Dashboard
```bash
# Terminal 3
python tests/performance/monitor.py
```

This shows:
- ✅ API health status
- 📊 CPU, Memory, Disk usage
- 🌐 Network activity
- ⏱️ Response times

**Keep this running while you test!**

---

## 🎯 Test Scenarios

### Light Load (Baseline)
```bash
python tests/performance/test_stress.py 5
```
**Expected:** 100% success, <500ms response time

### Normal Load
```bash
python tests/performance/test_stress.py 20
```
**Expected:** >95% success, <1s response time

### Heavy Load
```bash
python tests/performance/test_stress.py 50
```
**Expected:** >85% success, <2s response time

### Stress Test (Find Breaking Point)
```bash
python tests/performance/test_stress.py 100
```
**Watch for:** Success rate drop, error increase

---

## 📝 What to Look For

### ✅ Good Signs
- Success rate: 95-100%
- Avg response time: <1 second
- No error spikes
- Stable CPU/memory

### ⚠️ Warning Signs
- Success rate: 85-95%
- Avg response time: 1-3 seconds
- Occasional timeouts
- Rising memory usage

### ❌ Problems
- Success rate: <85%
- Avg response time: >3 seconds
- Many errors/timeouts
- Memory leaks

---

## 🔧 Troubleshooting

### "Connection refused"
➡️ Start the API first:
```bash
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

### "Assignment not found"
➡️ Run setup script:
```bash
./tests/performance/setup.sh
```

### High failure rate
➡️ Check:
- Database connection limits
- Sandbox manager running
- System resources (CPU/memory)

---

## 📚 Full Documentation

See `tests/performance/README.md` for:
- Detailed usage guides
- Performance targets
- Optimization tips
- Advanced scenarios

---

## 💡 Tips

1. **Start small** - Test with 5-10 submissions first
2. **Monitor resources** - Watch CPU and memory
3. **Be patient** - Grading takes time
4. **Cool down** - Wait between large tests
5. **Use realistic data** - Test with actual assignments

---

## 🎓 Example Session

```bash
# Terminal 1: Start API
uvicorn web.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Setup and test
./tests/performance/setup.sh
python tests/performance/test_stress.py 20

# Terminal 3: Monitor (optional)
python tests/performance/monitor.py

# Terminal 4: Locust (optional)
locust -f tests/performance/locustfile.py --host=http://localhost:8000
# Open http://localhost:8089
```

---

## 🎉 Success Criteria

Your system is performing well if:
- ✅ 20 concurrent submissions: >95% success
- ✅ Average response time: <1 second
- ✅ No errors or timeouts
- ✅ CPU usage: <70%
- ✅ Memory stable (no leaks)

**Congratulations!** 🎊

