
import pytest
from unittest.mock import MagicMock
from autograder.services.grader.criteria_grader import SubmissionGrader
from autograder.models.criteria_tree import CategoryNode, SubjectNode, TestNode
from autograder.models.abstract.test_function import TestFunction
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

@pytest.fixture
def grader():
    command_resolver = MagicMock()
    return SubmissionGrader(
        submission_files={},
        command_resolver=command_resolver
    )

def test_balance_nodes_only_subjects(grader):
    # If only subjects, they should sum to 100
    s1 = SubjectNode(name="S1", weight=30)
    s2 = SubjectNode(name="S2", weight=30)
    cat = CategoryNode(name="base", weight=100, subjects=[s1, s2])
    
    # We need to mock process_subject because it calls process_category/process_subject recursively
    # Actually SubmissionGrader.process_category calls __process_holder which calls process_subject
    
    # Let's mock process_test and process_subject to avoid deep recursion for this test
    grader.process_subject = MagicMock(side_effect=lambda s: MagicMock(weight=s.weight, score=100.0))
    
    result = grader.process_category(cat)
    
    # Weights should be balanced to 50/50 because original sum was 60
    assert result.subjects[0].weight == 50.0
    assert result.subjects[1].weight == 50.0

def test_balance_nodes_with_subjects_weight(grader):
    # Scenario: subjects_weight = 80
    # 1 subject, 1 test
    tf = MockTestFunction()
    s1 = SubjectNode(name="S1", weight=100)
    t1 = TestNode(name="T1", test_function=tf, weight=100)
    cat = CategoryNode(name="base", weight=100, subjects=[s1], tests=[t1], subjects_weight=80)
    
    grader.process_subject = MagicMock(side_effect=lambda s: MagicMock(weight=s.weight, score=100.0))
    # process_test is not mocked, it will execute the test
    
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
    s1 = SubjectNode(name="S1", weight=100)
    t1 = TestNode(name="T1", test_function=tf, weight=100, parameters={'score': 0.0})
    cat = CategoryNode(name="base", weight=100, subjects=[s1], tests=[t1], subjects_weight=80)
    
    # Mock process_subject to return a result node with score 100
    from autograder.models.result_tree import SubjectResultNode
    grader.process_subject = MagicMock(return_value=SubjectResultNode(name="S1", weight=100, subjects_weight=None, score=100.0))
    
    result = grader.process_category(cat)
    
    assert result.subjects[0].weight == pytest.approx(80.0)
    assert result.tests[0].weight == pytest.approx(20.0)
    
    # Score = 100 * 0.8 + 0 * 0.2 = 80
    assert result.calculate_score() == pytest.approx(80.0)

def test_balance_nodes_zero_weights(grader):
    # If all weights are zero, they should be equal and sum to 100 * factor
    s1 = SubjectNode(name="S1", weight=0)
    s2 = SubjectNode(name="S2", weight=0)
    cat = CategoryNode(name="base", weight=100, subjects=[s1, s2])
    
    grader.process_subject = MagicMock(side_effect=lambda s: MagicMock(weight=s.weight, score=100.0))
    
    result = grader.process_category(cat)
    
    assert result.subjects[0].weight == 50.0
    assert result.subjects[1].weight == 50.0
