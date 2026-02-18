# Testing Dashboard

Web-based interactive testing interface for the Autograder Input/Output template.

## Files

- **index.html** - Main dashboard landing page with navigation
- **page_config.html** - Configuration creator with visual tree builder
- **page_submit.html** - Code submission interface with real-time result polling
- **page_api.html** - Direct API operations (health checks, CRUD operations)
- **styles.css** - Shared CSS styles for all pages
- **shared.js** - Shared JavaScript utilities, code examples, and templates

## Usage

To launch the dashboard:

```bash
cd examples/assets/input_output/scripts
python serve_dashboard.py
```

Then open http://localhost:8080/index.html in your browser.

## Requirements

- The Autograder API must be running (default: http://localhost:8000)
- Modern web browser with JavaScript enabled
- Python 3.x for the server script

