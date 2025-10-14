# Setup Configuration

## Overview

The **setup.json** file configures the **pre-grading environment** and validation checks that run before the actual grading process begins. It serves two critical purposes:

1. **Pre-Flight Checks**: Validate submission requirements (file existence, structure)
2. **Sandbox Environment**: Configure isolated Docker containers for secure code execution

---

## Why Setup Configuration Matters

### Security First

When grading assignments that require **executing student code**, we cannot trust what that code might do. It could:
- Access sensitive system files
- Make network requests
- Consume excessive resources
- Contain malicious code

**Solution**: The setup configuration allows you to define a **sandbox environment** (Docker container) that isolates student code from the autograder system, ensuring security and stability.

### Early Failure Detection

Pre-flight checks catch common submission errors **before** grading begins:
- Missing required files
- Incorrect project structure
- Missing dependencies

This saves processing time and provides immediate, clear feedback to students.

---

## Configuration Modes

The setup configuration operates in two modes depending on whether code execution is required:

### Mode 1: Simple Pre-Flight Checks (No Execution)
For assignments where you only need to analyze code structure, syntax, or static properties without running student code.

### Mode 2: Sandbox Execution (With Docker Container)
For assignments where you need to **run student code** (APIs, web servers, scripts, etc.) in a secure, isolated environment.

---

## Configuration Structure

### Basic Structure (Pre-Flight Checks Only)

```json
{
  "file_checks": [
    "index.html",
    "css/styles.css",
    "app.js"
  ],
  "commands": []
}
```

### Full Structure (With Sandbox Container)

```json
{
  "file_checks": [
    "server.js",
    "package.json"
  ],
  "runtime_image": "node:18-alpine",
  "container_port": 3000,
  "commands": [
    "npm install",
    "node server.js"
  ]
}
```

---

## Configuration Options

### 1. `file_checks` (Array of Strings)

**Purpose**: List of files that **must exist** in the student's submission before grading begins.

**Behavior**: 
- The autograder checks if each file exists in the submission
- If any file is missing, grading is halted and a fatal error is reported
- Paths are relative to the submission root

**Example**:
```json
"file_checks": [
  "index.html",
  "css/styles.css",
  "js/app.js",
  "imgs/logo.png"
]
```

**Use Cases**:
- Ensure all required HTML files are present
- Verify proper project structure (CSS in `/css`, images in `/imgs`)
- Check for configuration files (`package.json`, `requirements.txt`)

---

### 2. `commands` (Array of Strings)

**Purpose**: Shell commands to execute during setup (typically for starting services or installing dependencies).

**Behavior**:
- Commands run **inside the sandbox container** (if configured)
- Executed in the order specified
- Can be used for background processes (e.g., starting a web server)

**Example**:
```json
"commands": [
  "npm install",
  "pip install -r requirements.txt",
  "node server.js"
]
```

**Common Use Cases**:
- Install dependencies (`npm install`, `pip install`)
- Start web servers (`node server.js`, `python app.py`)
- Run database migrations
- Start background services

**⚠️ Note**: Background processes (servers) should be started last in the commands array.

---

### 3. `runtime_image` (String) - **Required for Sandbox Mode**

**Purpose**: Specifies the Docker image to use for the sandbox container.

**Behavior**:
- Must be a valid Docker image name (from Docker Hub or custom registry)
- The container is created from this image
- If not specified, sandbox mode is disabled

**Example**:
```json
"runtime_image": "node:18-alpine"
```

**Common Images**:
- **Node.js**: `node:18-alpine`, `node:20-slim`
- **Python**: `python:3.11-slim`, `python:3.9-alpine`
- **PHP**: `php:8.2-fpm-alpine`
- **Ruby**: `ruby:3.2-alpine`
- **Multi-language**: `ubuntu:22.04` (install tools via commands)

**Tip**: Use Alpine-based images when possible for smaller size and faster startup.

---

### 4. `container_port` (Integer) - **Optional**

**Purpose**: The port number inside the container where the student's application will run.

**Behavior**:
- Enables dynamic port mapping from container to host
- The autograder automatically maps this container port to a random available host port
- Use `SandboxExecutor.get_mapped_port()` to retrieve the host port during testing
- Essential for testing web servers, APIs, and network services

**Example**:
```json
"container_port": 3000
```

**When to Use**:
- Testing Express.js, Flask, or other web frameworks
- Grading API implementations
- Testing socket servers
- Any assignment requiring HTTP requests to student code

**How It Works**:
```
Container Port 3000 → Dynamically Mapped → Host Port 54321 (random)
                                              ↑
                                    Tests connect here
```

---

## Complete Examples

### Example 1: Static Website (No Execution)

For an HTML/CSS/JavaScript assignment that doesn't require running a server:

```json
{
  "file_checks": [
    "index.html",
    "detalhes.html",
    "css/styles.css",
    "app.js"
  ],
  "commands": []
}
```

**What happens**:
1. ✅ Checks if all 4 files exist
2. ✅ If all present, grading proceeds
3. ❌ If any missing, grading stops with error message
4. ℹ️ No container needed (static analysis only)

---

### Example 2: Node.js API Server

For an assignment requiring students to build an Express.js API:

```json
{
  "file_checks": [
    "server.js",
    "package.json",
    "routes/api.js"
  ],
  "runtime_image": "node:18-alpine",
  "container_port": 3000,
  "commands": [
    "npm install",
    "node server.js"
  ]
}
```

**What happens**:
1. ✅ Checks if required files exist
2. 🐳 Creates a Node.js Docker container
3. 📦 Copies student files to `/home/user/` in container
4. ⚙️ Runs `npm install` to install dependencies
5. 🚀 Starts server with `node server.js` (background process)
6. 🔗 Maps container port 3000 to random host port
7. ✅ Grading tests can now make HTTP requests to the server

---

### Example 3: Python Flask Application

For a Flask web application assignment:

```json
{
  "file_checks": [
    "app.py",
    "requirements.txt",
    "templates/index.html"
  ],
  "runtime_image": "python:3.11-slim",
  "container_port": 5000,
  "commands": [
    "pip install --no-cache-dir -r requirements.txt",
    "python app.py"
  ]
}
```

**What happens**:
1. ✅ Validates file structure
2. 🐳 Creates Python container
3. 📦 Places student code in container
4. 📚 Installs Python packages from requirements.txt
5. 🌐 Starts Flask app on port 5000
6. 🧪 Tests can access the web app

---

### Example 4: Database-Backed Application

For an assignment with a database requirement:

```json
{
  "file_checks": [
    "app.py",
    "database.py",
    "schema.sql",
    "requirements.txt"
  ],
  "runtime_image": "python:3.11-slim",
  "container_port": 8000,
  "commands": [
    "apt-get update && apt-get install -y sqlite3",
    "pip install -r requirements.txt",
    "sqlite3 database.db < schema.sql",
    "python app.py"
  ]
}
```

**What happens**:
1. ✅ Checks for required files including SQL schema
2. 🐳 Starts Python container
3. 📦 Installs SQLite
4. 📚 Installs Python dependencies
5. 🗄️ Creates and initializes database
6. 🚀 Starts application
7. ✅ Tests can interact with the running app

---

## How the Sandbox Works

### Container Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Container Creation                                        │
│    - Image: runtime_image from setup.json                   │
│    - Command: "sleep infinity" (keeps container alive)      │
│    - Network: bridge mode                                   │
│    - Security: no-new-privileges enabled                    │
│    - Ports: Dynamic mapping if container_port specified     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. File Transfer                                            │
│    - Student submission files packaged as .tar archive      │
│    - Transferred to /home/user/ inside container            │
│    - Files extracted and ready for use                      │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Command Execution                                        │
│    - Each command from setup.json executed in order         │
│    - Working directory: /home/user/                         │
│    - Last command typically starts the service              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. Test Execution                                           │
│    - Tests run and interact with containerized code         │
│    - HTTP requests go to mapped host port                   │
│    - Additional commands can be executed in container       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Cleanup                                                  │
│    - Container stopped and removed                          │
│    - Resources freed                                        │
│    - Results collected                                      │
└─────────────────────────────────────────────────────────────┘
```

### Security Features

The sandbox provides multiple layers of security:

✅ **Process Isolation**: Student code runs in a separate container  
✅ **Network Isolation**: Bridge networking prevents direct host access  
✅ **File System Isolation**: Container has its own file system  
✅ **No New Privileges**: Security option prevents privilege escalation  
✅ **Resource Limits**: Docker can limit CPU, memory, and disk usage  
✅ **Automatic Cleanup**: Container is destroyed after grading

---

## Pre-Flight Check Flow

```
┌──────────────────────────────────┐
│  Autograder receives request     │
└────────────┬─────────────────────┘
             ↓
┌──────────────────────────────────┐
│  Load setup.json configuration   │
└────────────┬─────────────────────┘
             ↓
┌──────────────────────────────────┐
│  Run Pre-Flight Checks           │
│  - Check each file in file_checks│
│  - Record any missing files      │
└────────────┬─────────────────────┘
             ↓
      Are all files present?
             ├─── NO ──→ ┌──────────────────────────┐
             │           │ Return Fatal Error       │
             │           │ Status: "fail"           │
             │           │ Score: 0.0               │
             │           │ Feedback: Missing files  │
             │           └──────────────────────────┘
             │
             YES
             ↓
      Is runtime_image set?
             ├─── NO ──→ ┌──────────────────────────┐
             │           │ Skip Sandbox             │
             │           │ Continue to Grading      │
             │           └──────────────────────────┘
             │
             YES
             ↓
┌──────────────────────────────────┐
│  Start Sandbox Container         │
│  - Pull/use runtime_image        │
│  - Copy submission files         │
│  - Execute setup commands        │
└────────────┬─────────────────────┘
             ↓
┌──────────────────────────────────┐
│  Continue to Grading Phase       │
│  (Tests can now execute)         │
└──────────────────────────────────┘
```

---

## Best Practices

### 1. **Always Specify Required Files**
```json
"file_checks": [
  "index.html",
  "main.js"
]
```
Even if not using a container, file checks catch basic errors early.

### 2. **Use Lightweight Images**
```json
// ✅ Good: Small and fast
"runtime_image": "node:18-alpine"

// ❌ Avoid: Large and slow
"runtime_image": "node:18"
```
Alpine images are smaller and start faster.

### 3. **Install Only What's Needed**
```json
"commands": [
  "npm install --production",  // Skip dev dependencies
  "pip install --no-cache-dir -r requirements.txt"  // Don't cache
]
```

### 4. **Order Commands Logically**
```json
"commands": [
  "npm install",        // 1. Install first
  "npm run build",      // 2. Build if needed
  "node server.js"      // 3. Start server last
]
```

### 5. **Use Explicit Ports**
```json
"container_port": 3000,
"commands": [
  "node server.js --port 3000"  // Match the container_port
]
```

### 6. **Handle Background Processes**
If your server needs to run in the background, it's automatically handled. The last command in the array typically starts the service.

### 7. **Check Project Structure**
```json
"file_checks": [
  "src/index.js",      // Enforces folder structure
  "public/index.html",
  "package.json"
]
```

### 8. **Consider Startup Time**
- Minimize commands that take a long time
- Pre-build custom images if installations are complex
- Use caching strategies when possible

---

## Common Patterns

### Pattern 1: Simple Web Page (No Server)
```json
{
  "file_checks": ["index.html", "styles.css"],
  "commands": []
}
```

### Pattern 2: Node.js Express API
```json
{
  "file_checks": ["server.js", "package.json"],
  "runtime_image": "node:18-alpine",
  "container_port": 3000,
  "commands": ["npm install", "node server.js"]
}
```

### Pattern 3: Python Script (No Server)
```json
{
  "file_checks": ["main.py", "requirements.txt"],
  "runtime_image": "python:3.11-slim",
  "commands": ["pip install -r requirements.txt"]
}
```

### Pattern 4: Python Flask App
```json
{
  "file_checks": ["app.py", "requirements.txt"],
  "runtime_image": "python:3.11-slim",
  "container_port": 5000,
  "commands": [
    "pip install -r requirements.txt",
    "python app.py"
  ]
}
```

### Pattern 5: Multi-Stage Setup
```json
{
  "file_checks": ["app.js", "database.json"],
  "runtime_image": "node:18-alpine",
  "container_port": 8080,
  "commands": [
    "npm install",
    "npm run init-db",
    "npm run migrate",
    "npm start"
  ]
}
```

---

## Troubleshooting

### Issue: "File not found" errors

**Cause**: File paths in `file_checks` don't match submission structure  
**Solution**: Ensure paths are relative to submission root, check for typos

### Issue: Container fails to start

**Cause**: Invalid `runtime_image` name  
**Solution**: Verify image exists on Docker Hub or your registry

### Issue: Port mapping not working

**Cause**: Application not listening on `container_port`  
**Solution**: Ensure your student's server code uses the correct port

### Issue: Commands fail silently

**Cause**: Commands have errors but grading continues  
**Solution**: Check container logs, ensure commands are valid for the image

### Issue: Slow grading

**Cause**: Large images or many commands  
**Solution**: Use Alpine images, minimize installations, consider custom pre-built images

---

## Advanced: Custom Docker Images

For complex setups, create a custom Docker image with pre-installed dependencies:

**Dockerfile**:
```dockerfile
FROM node:18-alpine
RUN npm install -g express sequelize
RUN apk add --no-cache postgresql-client
WORKDIR /home/user
```

**Build and push**:
```bash
docker build -t myregistry/custom-node-env:latest .
docker push myregistry/custom-node-env:latest
```

**setup.json**:
```json
{
  "runtime_image": "myregistry/custom-node-env:latest",
  "container_port": 3000,
  "commands": ["node server.js"]  // Dependencies already installed!
}
```

---

## Related Documentation

- **[Criteria Configuration](./criteria_config.md)** - Define your grading tests
- **[Feedback Configuration](./feedback_config.md)** - Customize student feedback
- **[Templates Guide](../templates/)** - Use pre-built grading logic
- **[Getting Started](../getting_started.md)** - Overview of the autograder

---

## Summary

The setup configuration:
- ✅ Validates submission files before grading begins
- ✅ Configures secure sandbox environments for code execution
- ✅ Provides Docker-based isolation for untrusted student code
- ✅ Enables dynamic port mapping for testing web applications
- ✅ Executes setup commands (dependencies, database, services)
- ✅ Ensures security through containerization
- ✅ Prevents malicious code from affecting the grading system

Proper setup configuration is **essential** for assignments requiring code execution and ensures a secure, reliable grading process! 🔒
