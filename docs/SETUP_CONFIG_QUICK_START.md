# Quick Start: Setup Config for Compilation

## Problem
Previously, Java (and other compiled languages) required compilation in every test:
```json
"program_command": "javac Calculator.java && java Calculator"
```

This was inefficient and made error handling unclear.

## Solution
Use `setup_config` to compile once during preflight:

```json
{
  "setup_config": {
    "required_files": ["Calculator.java"],
    "setup_commands": ["javac Calculator.java"]
  },
  "criteria_config": {
    "tests": [{
      "program_command": "java Calculator"
    }]
  }
}
```

## Language Examples

### Java
```json
"setup_config": {
  "required_files": ["Calculator.java"],
  "setup_commands": [
    {
      "name": "Compile Calculator.java",
      "command": "javac Calculator.java"
    }
  ]
}
```

### C++
```json
"setup_config": {
  "required_files": ["calculator.cpp"],
  "setup_commands": [
    {
      "name": "Compile calculator.cpp",
      "command": "g++ calculator.cpp -o calculator"
    }
  ]
}
```

### Python (optional validation)
```json
"setup_config": {
  "required_files": ["calculator.py"],
  "setup_commands": []
}
```

## Benefits
✅ Compile once, not on every test  
✅ Clear compilation vs runtime error separation  
✅ Faster test execution  
✅ Better error messages  
✅ Validate required files exist  

## Migration
```bash
cd web
alembic upgrade head
```

## Documentation
- Full guide: [docs/setup_config_feature.md](setup_config_feature.md)
- Example config: [docs/example_java_config_with_setup.json](example_java_config_with_setup.json)

