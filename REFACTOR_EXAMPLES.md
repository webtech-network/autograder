# Template Refactoring - Before & After Examples

## Example 1: HTML Test (web_dev.py)

### BEFORE
```python
class HasTag(TestFunction):
    @property
    def name(self): return "has_tag"
    
    @property
    def description(self): return "Verifica se uma tag HTML específica aparece um número mínimo de vezes."
    
    @property
    def parameter_description(self):
        return [
            {"name": "html_content", "description": "O conteúdo HTML a ser analisado.", "type": "string"},
            {"name": "tag", "description": "A tag HTML a ser pesquisada (por exemplo, 'div').", "type": "string"},
            {"name": "required_count", "description": "O número mínimo de vezes que a tag deve aparecer.", "type": "integer"}
        ]
    
    def execute(self, html_content: str, tag: str, required_count: int) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        # ... rest of implementation
```

### AFTER
```python
class HasTag(TestFunction):
    @property
    def name(self): return "has_tag"
    
    @property
    def description(self): return "Verifica se uma tag HTML específica aparece um número mínimo de vezes."
    
    @property
    def required_file(self): return "HTML"
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("tag", "A tag HTML a ser pesquisada (por exemplo, 'div').", "string"),
            ParamDescription("required_count", "O número mínimo de vezes que a tag deve aparecer.", "integer")
        ]
    
    def execute(self, html_content: str, tag: str, required_count: int) -> TestResult:
        soup = BeautifulSoup(html_content, 'html.parser')
        found_count = len(soup.find_all(tag))
        # ... rest of implementation
```

### Key Changes:
- ❌ Removed `html_content` from `parameter_description`
- ✅ Added `required_file` property returning `"HTML"`
- ✅ Changed parameter format from dict to `ParamDescription` objects
- ✅ `execute()` method signature unchanged (still accepts `html_content`)

---

## Example 2: Essay Test (essay_grader.py)

### BEFORE
```python
class ArgumentStrengthTest(TestFunction):
    @property
    def name(self): return "argument_strength"
    
    @property
    def description(self): return "Avalia a força e o suporte dos argumentos apresentados."
    
    @property
    def parameter_description(self):
        return [
            {"name": "essay_content", "description": "O texto do ensaio a ser analisado.", "type": "string"}
        ]
    
    def execute(self, *args, **kwargs) -> TestResult:
        prompt = "Avalie a força dos argumentos no ensaio em uma escala de 0 a 100..."
        return ai_executor.add_test(self.name, prompt)
```

### AFTER
```python
class ArgumentStrengthTest(TestFunction):
    @property
    def name(self): return "argument_strength"
    
    @property
    def description(self): return "Avalia a força e o suporte dos argumentos apresentados."
    
    @property
    def required_file(self): return "Essay"
    
    @property
    def parameter_description(self):
        return []
    
    def execute(self, *args, **kwargs) -> TestResult:
        prompt = "Avalie a força dos argumentos no ensaio em uma escala de 0 a 100..."
        return ai_executor.add_test(self.name, prompt)
```

### Key Changes:
- ❌ Removed `essay_content` from `parameter_description`
- ✅ Added `required_file` property returning `"Essay"`
- ✅ `parameter_description` now returns empty list (no configurable parameters)
- ✅ `execute()` method unchanged

---

## Example 3: Essay Test with Parameters (essay_grader.py)

### BEFORE
```python
class ToneAndStyleTest(TestFunction):
    @property
    def name(self): return "tone_and_style"
    
    @property
    def description(self): return "Avalia se o tom e o estilo de escrita do ensaio são apropriados."
    
    @property
    def parameter_description(self):
        return [
            {"name": "essay_content", "description": "O texto do ensaio.", "type": "string"},
            {"name": "expected_tone", "description": "O tom esperado (ex: formal, persuasivo).", "type": "string"}
        ]
    
    def execute(self, expected_tone: str) -> TestResult:
        prompt = f"Em uma escala de 0 a 100, o ensaio mantém um tom '{expected_tone}'?"
        return ai_executor.add_test(self.name, prompt)
```

### AFTER
```python
class ToneAndStyleTest(TestFunction):
    @property
    def name(self): return "tone_and_style"
    
    @property
    def description(self): return "Avalia se o tom e o estilo de escrita do ensaio são apropriados."
    
    @property
    def required_file(self): return "Essay"
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("expected_tone", "O tom esperado (ex: formal, persuasivo).", "string")
        ]
    
    def execute(self, expected_tone: str) -> TestResult:
        prompt = f"Em uma escala de 0 a 100, o ensaio mantém um tom '{expected_tone}'?"
        return ai_executor.add_test(self.name, prompt)
```

### Key Changes:
- ❌ Removed `essay_content` from `parameter_description`
- ✅ Added `required_file` property returning `"Essay"`
- ✅ Kept `expected_tone` parameter (it's a test configuration, not file content)
- ✅ Changed to `ParamDescription` format

---

## Example 4: API Test (api_testing.py)

### BEFORE
```python
class HealthCheckTest(TestFunction):
    @property
    def name(self): return "health_check"
    
    @property
    def description(self): return "Checks if a specific endpoint is running and returns a 200 OK."
    
    @property
    def parameter_description(self):
        return [
            {"name": "endpoint", "description": "The endpoint to test (e.g., '/health').", "type": "string"}
        ]
    
    def __init__(self, executor: SandboxExecutor):
        self.executor = executor
    
    def execute(self, endpoint: str) -> TestResult:
        # ... implementation using self.executor
```

### AFTER
```python
class HealthCheckTest(TestFunction):
    @property
    def name(self): return "health_check"
    
    @property
    def description(self): return "Checks if a specific endpoint is running and returns a 200 OK."
    
    @property
    def required_file(self): return None
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("endpoint", "The endpoint to test (e.g., '/health').", "string")
        ]
    
    def __init__(self, executor: SandboxExecutor):
        self.executor = executor
    
    def execute(self, endpoint: str) -> TestResult:
        # ... implementation using self.executor
```

### Key Changes:
- ✅ Added `required_file` property returning `None` (no specific file needed)
- ✅ Changed to `ParamDescription` format
- ✅ No file content parameter was present (test uses executor)

---

## Example 5: CSS Test (web_dev.py)

### BEFORE
```python
class CssUsesProperty(TestFunction):
    @property
    def name(self): return "css_uses_property"
    
    @property
    def description(self): return "Verifica se um par de propriedade e valor CSS específico existe."
    
    @property
    def parameter_description(self):
        return [
            {"name": "css_content", "description": "O conteúdo CSS a ser analisado.", "type": "string"},
            {"name": "prop", "description": "A propriedade CSS.", "type": "string"},
            {"name": "value", "description": "O valor esperado.", "type": "string"}
        ]
    
    def execute(self, css_content: str, prop: str, value: str) -> TestResult:
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}")
        found = pattern.search(css_content) is not None
        # ... rest of implementation
```

### AFTER
```python
class CssUsesProperty(TestFunction):
    @property
    def name(self): return "css_uses_property"
    
    @property
    def description(self): return "Verifica se um par de propriedade e valor CSS específico existe."
    
    @property
    def required_file(self): return "CSS"
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("prop", "A propriedade CSS.", "string"),
            ParamDescription("value", "O valor esperado.", "string")
        ]
    
    def execute(self, css_content: str, prop: str, value: str) -> TestResult:
        pattern = re.compile(rf"{re.escape(prop)}\s*:\s*.*{re.escape(value)}")
        found = pattern.search(css_content) is not None
        # ... rest of implementation
```

### Key Changes:
- ❌ Removed `css_content` from `parameter_description`
- ✅ Added `required_file` property returning `"CSS"`
- ✅ Changed to `ParamDescription` format
- ✅ `execute()` still accepts `css_content` as first parameter

---

## API Response Changes

### Template Info Endpoint BEFORE
```json
{
  "name": "has_tag",
  "description": "Verifica se uma tag HTML específica aparece um número mínimo de vezes.",
  "parameters": [
    {
      "name": "html_content",
      "description": "O conteúdo HTML a ser analisado.",
      "type": "string"
    },
    {
      "name": "tag",
      "description": "A tag HTML a ser pesquisada.",
      "type": "string"
    },
    {
      "name": "required_count",
      "description": "O número mínimo de vezes que a tag deve aparecer.",
      "type": "integer"
    }
  ]
}
```

### Template Info Endpoint AFTER
```json
{
  "name": "has_tag",
  "description": "Verifica se uma tag HTML específica aparece um número mínimo de vezes.",
  "required_file": "HTML",
  "parameters": [
    {
      "name": "tag",
      "description": "A tag HTML a ser pesquisada.",
      "type": "string"
    },
    {
      "name": "required_count",
      "description": "O número mínimo de vezes que a tag deve aparecer.",
      "type": "integer"
    }
  ]
}
```

### Key Differences:
- ✅ Added `required_file` field at test level
- ❌ Removed `html_content` from parameters
- ✅ Parameters only show configurable test options
- ✅ Frontend can now determine which file to read based on `required_file`

---

## File Type Mapping Reference

| `required_file` Value | Purpose | Used in Template |
|----------------------|---------|------------------|
| `"HTML"` | HTML file content tests | web_dev.py |
| `"CSS"` | CSS file content tests | web_dev.py |
| `"JavaScript"` | JavaScript file content tests | web_dev.py |
| `"Essay"` | Essay/text content tests | essay_grader.py |
| `None` | No specific file (uses executor, submission_files, etc.) | api_testing.py, input_output.py, some web_dev.py |

---

## Migration Checklist for Developers

When creating a new test class:

- [ ] Import `ParamDescription` from `autograder.builder.models.param_description`
- [ ] Add `required_file` property returning appropriate type or `None`
- [ ] Use `ParamDescription(name, description, type)` in `parameter_description`
- [ ] Do NOT include file content parameters in `parameter_description`
- [ ] File content should still be accepted in `execute()` method
- [ ] Test the API response to ensure `required_file` is present

---

## Common Patterns

### Pattern 1: Single File Content Test
```python
@property
def required_file(self): return "HTML"  # or "CSS", "JavaScript", "Essay"

@property
def parameter_description(self):
    return [
        ParamDescription("param1", "Description", "type"),
        # NO file content parameter here
    ]

def execute(self, html_content: str, param1: any) -> TestResult:
    # file_content is first parameter but not in parameter_description
```

### Pattern 2: No File Content (Executor-based)
```python
@property
def required_file(self): return None

@property
def parameter_description(self):
    return [
        ParamDescription("endpoint", "API endpoint", "string"),
    ]

def execute(self, endpoint: str) -> TestResult:
    # uses self.executor instead of file content
```

### Pattern 3: No File Content (Submission Files)
```python
@property
def required_file(self): return None

@property
def parameter_description(self):
    return [
        ParamDescription("submission_files", "All submission files", "dictionary"),
        ParamDescription("dir_path", "Directory path", "string"),
    ]

def execute(self, submission_files: dict, dir_path: str) -> TestResult:
    # works with entire submission structure
```

### Pattern 4: No Parameters
```python
@property
def required_file(self): return "HTML"

@property
def parameter_description(self):
    return []  # empty list

def execute(self, html_content: str) -> TestResult:
    # only needs file content, no other configuration
```

---

## Testing the Changes

### Unit Test Example
```python
def test_parameter_description_format():
    test = HasTag()
    params = test.parameter_description
    
    # Check it returns list of ParamDescription objects
    assert isinstance(params, list)
    assert all(isinstance(p, ParamDescription) for p in params)
    
    # Check file content is not included
    param_names = [p.name for p in params]
    assert "html_content" not in param_names
    
    # Check required_file is set
    assert test.required_file == "HTML"
```

### Integration Test Example
```python
def test_template_info_api():
    template = WebDevTemplate()
    info = get_template_info(template)
    
    for test_info in info:
        # Check required_file exists
        assert "required_file" in test_info
        
        # Check parameters don't include file content
        param_names = [p["name"] for p in test_info["parameters"]]
        assert not any(
            name.endswith("_content") 
            for name in param_names
        )
```

---

## Benefits Summary

1. **Cleaner API**: File content handling is implicit, not exposed in API
2. **Better UX**: Frontend knows which file to read from `required_file`
3. **Type Safety**: `ParamDescription` dataclass ensures consistency
4. **Maintainability**: Single source of truth for file type requirements
5. **Flexibility**: `None` value allows tests that don't need specific files
6. **Documentation**: Clear separation between file input and test parameters
