
import pytest
from unittest.mock import MagicMock
from autograder.services.grader.criteria_grader import SubmissionGrader
from autograder.models.criteria_tree import CategoryNode, SubjectNode, TestNode
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.submission import EvaluationScope, SubmissionFile
from autograder.models.dataclass.test_result import TestResult

class MockTestFunction(TestFunction):
    @property
    def name(self) -> str:
        return "mock_test"
    @property
    def description(self) -> str:
        return "mock description"
    @property
    def parameter_description(self) -> list:
        return []
    def execute(self, files=None, sandbox=None, **kwargs):
        return TestResult(test_name="mock_test", score=kwargs.get('score', 100.0), report="OK")


class CapturingTestFunction(MockTestFunction):
    """Test function that records the pipeline context passed to execute."""

    def __init__(self):
        self.files = None
        self.kwargs = {}

    def execute(self, files=None, sandbox=None, **kwargs):
        self.files = files
        self.kwargs = kwargs
        return super().execute(files=files, sandbox=sandbox, **kwargs)

@pytest.fixture
def grader():
    command_resolver = MagicMock()
    # Mock command_resolver.resolve_command just in case tests have program_command
    command_resolver.resolve_command.side_effect = lambda c, lang: c
    return SubmissionGrader(
        submission_files={},
        command_resolver=command_resolver
    )

def test_balance_nodes_only_subjects(grader):
    # Need tests inside subjects to have real scores
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100)
    t2 = TestNode(name="T2", test_function=tf, weight=100)
    
    s1 = SubjectNode(name="S1", weight=30, tests=[t1])
    s2 = SubjectNode(name="S2", weight=30, tests=[t2])
    cat = CategoryNode(name="base", weight=100, subjects=[s1, s2])
    
    result = grader.process_category(cat)
    
    # Weights should be balanced to 50/50 because original sum was 60
    assert result.subjects[0].weight == 50.0
    assert result.subjects[1].weight == 50.0
    assert result.calculate_score() == 100.0

def test_balance_nodes_with_subjects_weight(grader):
    # Scenario: subjects_weight = 80
    tf = MockTestFunction()
    t_sub = TestNode(name="T_Sub", test_function=tf, weight=100)
    s1 = SubjectNode(name="S1", weight=100, tests=[t_sub])
    t1 = TestNode(name="T1", test_function=tf, weight=100)
    cat = CategoryNode(name="base", weight=100, subjects=[s1], tests=[t1], subjects_weight=80)
    
    result = grader.process_category(cat)
    
    # Subject should have weight 80, Test should have weight 20
    assert result.subjects[0].weight == pytest.approx(80.0)
    assert result.tests[0].weight == pytest.approx(20.0)
    
    # Final score should be 100 if both are 100
    assert result.calculate_score() == pytest.approx(100.0)

def test_balance_nodes_with_subjects_weight_and_scores(grader):
    # Scenario: subjects_weight = 80
    # Subject score = 100, Test score = 0
    tf = MockTestFunction()
    t_sub = TestNode(name="T_Sub", test_function=tf, weight=100, parameters={'score': 100.0})
    s1 = SubjectNode(name="S1", weight=100, tests=[t_sub])
    t1 = TestNode(name="T1", test_function=tf, weight=100, parameters={'score': 0.0})
    cat = CategoryNode(name="base", weight=100, subjects=[s1], tests=[t1], subjects_weight=80)
    
    result = grader.process_category(cat)
    
    assert result.subjects[0].weight == pytest.approx(80.0)
    assert result.tests[0].weight == pytest.approx(20.0)
    
    # Score = 100 * 0.8 + 0 * 0.2 = 80
    assert result.calculate_score() == pytest.approx(80.0)

def test_balance_nodes_zero_weights(grader):
    # If all weights are zero, they should be equal and sum to 100 * factor
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100)
    t2 = TestNode(name="T2", test_function=tf, weight=100)
    
    s1 = SubjectNode(name="S1", weight=0, tests=[t1])
    s2 = SubjectNode(name="S2", weight=0, tests=[t2])
    cat = CategoryNode(name="base", weight=100, subjects=[s1, s2])
    
    result = grader.process_category(cat)
    
    assert result.subjects[0].weight == 50.0
    assert result.subjects[1].weight == 50.0
    assert result.calculate_score() == 100.0

def test_balance_nodes_subjects_and_tests_missing_subjects_weight(grader):
    tf = MockTestFunction()
    s1 = SubjectNode(name="S1", weight=100, tests=[TestNode(name="T1", test_function=tf)])
    t2 = TestNode(name="T2", test_function=tf)
    
    cat = CategoryNode(name="base", weight=100, subjects=[s1], tests=[t2], subjects_weight=None)
    with pytest.raises(ValueError, match="missing 'subjects_weight' for base"):
        grader.process_category(cat)

def test_balance_nodes_empty(grader):
    # Should not break if there are no subjects/tests
    cat = CategoryNode(name="base", weight=100)
    result = grader.process_category(cat)
    assert result.score == 0.0

def test_process_test_program_command_resolution():
    command_resolver = MagicMock()
    command_resolver.resolve_command.return_value = "python3 main.py"
    
    grader = SubmissionGrader(
        submission_files={},
        command_resolver=command_resolver,
        submission_language="python"
    )
    
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100, parameters={'program_command': 'python {main}'})
    
    cat = CategoryNode(name="base", weight=100, tests=[t1])
    grader.process_category(cat)
    
    command_resolver.resolve_command.assert_called_once_with('python {main}', 'python')

def test_get_file_target_all():
    file1 = SubmissionFile(filename="file1.py", content="")
    file2 = SubmissionFile(filename="file2.py", content="")
    grader = SubmissionGrader(
        submission_files={"file1.py": file1, "file2.py": file2},
        command_resolver=MagicMock()
    )
    
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100, file_target=["all"])
    
    cat = CategoryNode(name="base", weight=100, tests=[t1])
    grader.process_category(cat)
    # The MockTestFunction would need to record what files it received to assert it, 
    # but process_test will just call it. Let's just assert get_file_target directly.
    target_files = grader.get_file_target(t1)
    assert len(target_files) == 2

def test_get_file_target_specific():
    file1 = SubmissionFile(filename="file1.py", content="")
    file2 = SubmissionFile(filename="file2.py", content="")
    grader = SubmissionGrader(
        submission_files={"file1.py": file1, "file2.py": file2},
        command_resolver=MagicMock()
    )
    
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100, file_target=["file1.py"])
    
    target_files = grader.get_file_target(t1)
    assert len(target_files) == 1
    assert target_files[0] is file1


def test_process_test_passes_scope_and_target_file_metadata():
    scope = EvaluationScope(scoped_files=["file1.py"])
    file1 = SubmissionFile(
        filename="file1.py",
        content="",
        metadata={"change_status": "modified"},
    )
    file2 = SubmissionFile(
        filename="file2.py",
        content="",
        metadata={"change_status": "added"},
    )
    grader = SubmissionGrader(
        submission_files={"file1.py": file1, "file2.py": file2},
        command_resolver=MagicMock(),
        evaluation_scope=scope,
    )
    test_function = CapturingTestFunction()
    test_node = TestNode(
        name="T1",
        test_function=test_function,
        file_target=["file1.py"],
    )

    grader.process_test(test_node)

    assert test_function.files == [file1]
    assert test_function.kwargs["evaluation_scope"] is scope
    assert test_function.kwargs["file_metadata"] == {
        "file1.py": {"change_status": "modified"},
    }
