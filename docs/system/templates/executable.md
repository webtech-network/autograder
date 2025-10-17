## **Executable Template Guide**

This guide covers the configuration of assignments that **require** student code to be executed in a secure sandbox environment. These templates are essential for assignments involving backend APIs and command-line applications.

### **API Template**

The API template is for assignments where students build and run a web server. It requires a `setup.json` file to configure the sandbox.

#### `setup.json` Configuration

This file defines the runtime environment for the student's API.

```json
{
  "runtime_image": "node:18-alpine",
  "container_port": 8000,
  "start_command": "node server.js",
  "commands": {
    "install_dependencies": "npm install"
  }
}
```

* **`runtime_image`**: The Docker image to use for the sandbox (e.g., `node:18-alpine`, `python:3.10-slim`).
* **`container_port`**: The port inside the container that the student's application will listen on.
* **`start_command`**: The command to start the student's server.
* **`commands`**: A dictionary of commands to run before the tests, such as installing dependencies.

#### `criteria.json` Configuration

The `criteria.json` for the API template will specify the endpoints to test.

```json
{
  "base": {
    "subjects": {
      "api_functionality": {
        "weight": 100,
        "tests": [
          {
            "name": "health_check",
            "calls": [["/health"]]
          },
          {
            "name": "check_response_json",
            "calls": [["/api/user", "userId", 1]]
          }
        ]
      }
    }
  }
}
```

#### **Configuration Tips**

* The API tests do not require a `file` parameter, as they interact with a running server, not a static file.
* The arguments in `calls` specify the endpoint and any expected response data.

### **I/O Template**

The Input/Output (I/O) template is for assignments where students write command-line programs that read from standard input and write to standard output.

#### `setup.json` Configuration

The `setup.json` for the I/O template defines the runtime and how to run the student's program.

```json
{
  "runtime_image": "python:3.11-slim",
  "start_command": "python calculator.py"
}
```

* **`runtime_image`**: The Docker image for the sandbox.
* **`start_command`**: The command to execute the student's script.

#### `criteria.json` Configuration

The `criteria.json` defines the inputs to be sent to the program and the expected output.

```json
{
  "base": {
    "subjects": {
      "calculation_tests": {
        "weight": 100,
        "tests": [
          {
            "name": "expect_output",
            "calls": [
              [["sum", 2, 2], "4.0"]
            ]
          },
          {
            "name": "expect_output",
            "calls": [
              [["subtract", 10, 5], "5.0"]
            ]
          }
        ]
      }
    }
  }
}
```

#### **Configuration Tips**

* The `expect_output` test takes two arguments in its `calls` array:
    1.  A list of strings to be passed to the program's standard input, one line at a time.
    2.  The exact string that the program is expected to print to standard output.
