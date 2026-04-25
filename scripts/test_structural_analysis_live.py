import sys
import os

# Add the project root to the PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.pipeline_execution import PipelineExecution
from autograder.steps.structural_analysis_step import StructuralAnalysisStep
from autograder.models.dataclass.step_result import StepName
from sandbox_manager.models.sandbox_models import Language

def main():
    print("🚀 Starting real submission test for StructuralAnalysisStep...")
    
    # 1. Create a mock submission with some real code
    python_code = """
def calculate_sum(a, b):
    result = a + b
    return result

print(calculate_sum(10, 20))
"""
    
    submission = Submission(
        username="test_student",
        user_id=123,
        assignment_id=1,
        submission_files={
            "main.py": SubmissionFile(filename="main.py", content=python_code),
            "config.json": SubmissionFile(filename="config.json", content='{"key": "value"}')
        },
        language=Language.PYTHON
    )
    
    print(f"📦 Created submission with files: {list(submission.submission_files.keys())}")
    
    # 2. Start pipeline execution
    pipeline_exec = PipelineExecution.start_execution(submission)
    
    # 3. Run the StructuralAnalysisStep
    print("⚙️  Running StructuralAnalysisStep...")
    step = StructuralAnalysisStep()
    pipeline_exec = step.execute(pipeline_exec)
    
    # 4. Check the results
    result_data = pipeline_exec.get_step_result(StepName.STRUCTURAL_ANALYSIS).data
    roots = result_data.roots
    
    print("\n📊 --- Structural Analysis Results ---")
    for filename, root_node in roots.items():
        if root_node is None:
            print(f"❌ {filename}: Failed to parse or skipped")
        else:
            print(f"✅ {filename}: Successfully parsed into AST!")
            
            # Let's try to query the AST!
            # Example: find all function definitions
            try:
                # In ast-grep, we can find nodes. For python, a function definition is typically a `function_definition` node.
                # Or we can just use a simple pattern match.
                funcs = root_node.root().find_all(pattern="def $FUNC($ARGS): $$$BODY")
                if funcs:
                    print(f"   🔍 Found {len(funcs)} function(s) in {filename}:")
                    for f in funcs:
                        func_name = f.get_match("FUNC").text()
                        print(f"      - {func_name}()")
                else:
                    print(f"   🔍 No functions found in {filename}.")
            except Exception as e:
                print(f"   ⚠️ Could not run ast-grep query: {e}")

if __name__ == "__main__":
    main()
