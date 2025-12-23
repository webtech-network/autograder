from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.builder.models.param_description import ParamDescription
from autograder.models.dataclass.test_result import TestResult
from autograder.context import request_context


class CheckFileExists(TestFunction):
    """Test to check if a specific file exists in the submission."""
    
    @property
    def name(self):
        return "check_file_exists"
    
    @property
    def description(self):
        return "Checks if a specified file exists in the student submission."
    
    @property
    def required_file(self):
        return None
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("filename", "The name of the file to check for.", "string")
        ]
    
    def execute(self, filename: str) -> TestResult:
        request = request_context.get_request()
        submission_files = request.submission_files
        
        if filename in submission_files:
            return TestResult(
                self.name,
                100,
                f"File '{filename}' was found in the submission.",
                parameters={"filename": filename}
            )
        else:
            return TestResult(
                self.name,
                0,
                f"File '{filename}' was NOT found in the submission.",
                parameters={"filename": filename}
            )


class CheckFunctionExists(TestFunction):
    """Test to check if a function is defined in a Python file."""
    
    @property
    def name(self):
        return "check_function_exists"
    
    @property
    def description(self):
        return "Checks if a function is defined in the main Python file."
    
    @property
    def required_file(self):
        return "PYTHON"
    
    @property
    def parameter_description(self):
        return [
            ParamDescription("function_name", "The name of the function to check for.", "string")
        ]
    
    def execute(self, python_content: str, function_name: str) -> TestResult:
        if f"def {function_name}(" in python_content:
            return TestResult(
                self.name,
                100,
                f"Function '{function_name}()' was found in the code.",
                parameters={"function_name": function_name}
            )
        else:
            return TestResult(
                self.name,
                0,
                f"Function '{function_name}()' was NOT found in the code.",
                parameters={"function_name": function_name}
            )


class CustomTemplate(Template):
    """A custom template for basic Python file checking."""
    
    @property
    def template_name(self):
        return "Custom Template"
    
    @property
    def template_description(self):
        return "A custom template for checking Python file structure."
    
    @property
    def requires_pre_executed_tree(self) -> bool:
        return False
    
    @property
    def requires_execution_helper(self) -> bool:
        return False
    
    def __init__(self, clean=False):
        self.tests = {
            "check_file_exists": CheckFileExists(),
            "check_function_exists": CheckFunctionExists()
        }
    
    def get_test(self, name: str) -> TestFunction:
        test = self.tests.get(name)
        if not test:
            raise AttributeError(f"Test '{name}' not found in custom template.")
        return test
