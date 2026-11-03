
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
    def execute(self, evaluation, *, score: float = 100.0):
        return TestResult(test_name="mock_test", score=score, report="OK")


class CapturingTestFunction(MockTestFunction):
    """Test function that records the pipeline context passed to execute."""

    def __init__(self):
        self.evaluation = None

    def execute(self, evaluation, *, score: float = 100.0):
        self.evaluation = evaluation
        return super().execute(evaluation, score=score)

@pytest.fixture
def grader():
    return SubmissionGrader(submission_files={})

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

def test_generic_grader_does_not_interpret_parameter_names():
    """program_command is passed verbatim; resolution belongs to the execution evaluators."""
    received = []

    class Recording(MockTestFunction):
        def execute(self, evaluation, *, program_command: str):
            received.append(program_command)
            return TestResult("mock_test", 100, "OK")

    grader = SubmissionGrader(submission_files={}, submission_language="python")
    grader.process_test(TestNode(name="T1", test_function=Recording(), parameters={'program_command': 'CMD'}))
    assert received == ['CMD']


def test_session_is_bound_only_to_evaluators_declaring_execution():
    session = MagicMock()
    grader = SubmissionGrader(submission_files={}, sandbox=session)
    static, executing = CapturingTestFunction(), CapturingTestFunction()
    grader.process_test(TestNode(name="static", test_function=static))
    grader.process_test(TestNode(name="run", test_function=executing, capabilities=frozenset({"sandbox_execution"})))
    assert static.evaluation.session is None
    assert executing.evaluation.session is session


def test_get_file_target_all():
    file1 = SubmissionFile(filename="file1.py", content="")
    file2 = SubmissionFile(filename="file2.py", content="")
    grader = SubmissionGrader(
        submission_files={"file1.py": file1, "file2.py": file2}
    )
    
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100, file_target=None)
    
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
        submission_files={"file1.py": file1, "file2.py": file2}
    )
    
    tf = MockTestFunction()
    t1 = TestNode(name="T1", test_function=tf, weight=100, file_target=["file1.py"])
    
    target_files = grader.get_file_target(t1)
    assert len(target_files) == 1
    assert target_files[0] is file1


def test_process_test_passes_selected_files_with_their_metadata():
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
        evaluation_scope=scope,
    )
    test_function = CapturingTestFunction()
    test_node = TestNode(
        name="T1",
        test_function=test_function,
        file_target=["file1.py"],
    )

    grader.process_test(test_node)

    # The selected files carry their own metadata; scope only shapes selection.
    assert test_function.evaluation.files == (file1,)
    assert test_function.evaluation.files[0].metadata == {"change_status": "modified"}
    assert not hasattr(test_function.evaluation, "evaluation_scope")


def test_literal_file_named_all_does_not_select_other_files():
    filename = SubmissionFile(filename="all", content="")
    grader = SubmissionGrader(submission_files={"all": filename, "other.py": SubmissionFile("other.py", "")})
    target = TestNode(name="Literal filename", test_function=MockTestFunction(), file_target=["all"])
    assert grader.get_file_target(target) == [filename]


def test_finite_large_sibling_weights_preserve_ratio(grader):
    """Finite authored ratios remain meaningful even when their raw sum overflows."""
    function = MockTestFunction()
    category = CategoryNode(name="base", weight=100, tests=[
        TestNode(name="Pass", test_function=function, weight=1e308, parameters={"score": 100}),
        TestNode(name="Fail", test_function=function, weight=1e308, parameters={"score": 0}),
    ])
    result = grader.process_category(category)
    assert [test.weight for test in result.tests] == [50, 50]
    assert result.calculate_score() == 50
