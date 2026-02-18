# Autograder Examples

Interactive demo and reference files for testing the autograder system.

## Quick Start

**Start demo:**
```bash
make examples-demo
```

Or manually:
```bash
cd examples/demo
python serve_demo.py
```

Then open: **http://localhost:8080**

> **Note:** API server must be running (`cd web && python main.py`)

## Directory Structure

```
examples/
├── demo/                    # Interactive web demo
│   ├── index.html          # Landing page
│   ├── template.html       # Template selector
│   ├── config.html         # Config creator
│   ├── submit.html         # Code submission
│   ├── api.html           # API explorer
│   ├── *.js, *.css        # Scripts and styles
│   └── serve_demo.py      # Demo server
│
└── assets/                 # Reference data
    ├── input_output/       # I/O template examples
    │   ├── code_examples/     # Python, Java, JS, C++
    │   ├── criteria_examples/ # 5 preset configs
    │   ├── sample_files/      # Config templates
    │   └── scripts/           # Utilities
    ├── web_dev/           # Web dev examples
    └── api_testing/       # API testing examples
```

## Using the Demo

### 1. Create Configuration
- Select **Input/Output** template
- Choose preset criteria (1-5)
- Select language
- Click **Create Configuration**

### 2. Submit Code  
- Select **Input/Output** template
- Click **Submit and Grade**
- Choose code example or write your own
- Click **Submit for Grading**

### 3. Explore API
- Click **View API Operations**
- Test endpoints directly

## Available Templates

| Template | Status |
|----------|--------|
| Input/Output | ✅ Available |
| Web Development | 🚧 Coming Soon |
| API Testing | 🚧 Coming Soon |

## Configuration

API endpoint (default: `http://localhost:8000`) can be changed on the landing page.

## Troubleshooting

**Demo won't start:** Ensure you're in `examples/demo/` directory  
**API connection failed:** Start API server first  
**Config not found:** Create config before submitting code




