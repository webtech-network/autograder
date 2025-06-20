import pytest
from unittest.mock import MagicMock, patch
from grading.final_scorer import Scorer
from grading.grader import Grader
from utils.config_loader import Config

@pytest.fixture
def mock_grader():
    """Fixture to create a mock Grader instance."""
    grader = MagicMock(spec=Grader)
    grader.generate_score.return_value = 80
    grader.passed_tests = ["test1", "test2"]
    grader.failed_tests = ["test3"]
    return grader

@pytest.fixture
def mock_config():
    """Fixture to create a mock Config instance."""
    config = MagicMock(spec=Config)
    config.base_config = MagicMock()
    config.bonus_config = MagicMock()
    config.penalty_config = MagicMock()
    return config

@pytest.fixture
def scorer_instance(mock_config):
    """Fixture to create a Scorer instance."""
    scorer = Scorer("test_folder", "author_name")
    scorer.config = mock_config
    return scorer

def test_scorer_initialization(scorer_instance):
    """Test the initialization of the Scorer class."""
    assert scorer_instance.path is not None
    assert scorer_instance.author == "author_name"
    assert scorer_instance.config is not None
    assert scorer_instance.base_grader is None
    assert scorer_instance.bonus_grader is None
    assert scorer_instance.penalty_grader is None
    assert scorer_instance.final_score == 0

@patch("grading.grader.Grader.create")
def test_set_base_score(mock_grader_create, scorer_instance, mock_grader):
    """Test setting the base score."""
    mock_grader_create.return_value = mock_grader
    scorer_instance.set_base_score("base_test.py")
    assert scorer_instance.base_grader == mock_grader
    mock_grader_create.assert_called_once_with("grading/tests/base_test.py", scorer_instance.config.base_config)

@patch("grading.grader.Grader.create")
def test_set_bonus_score(mock_grader_create, scorer_instance, mock_grader):
    """Test setting the bonus score."""
    mock_grader_create.return_value = mock_grader
    scorer_instance.set_bonus_score("bonus_test.py")
    assert scorer_instance.bonus_grader == mock_grader
    mock_grader_create.assert_called_once_with("grading/tests/bonus_test.py", scorer_instance.config.bonus_config)

@patch("grading.grader.Grader.create")
def test_set_penalty_score(mock_grader_create, scorer_instance, mock_grader):
    """Test setting the penalty score."""
    mock_grader_create.return_value = mock_grader
    scorer_instance.set_penalty_score("penalty_test.py")
    assert scorer_instance.penalty_grader == mock_grader
    mock_grader_create.assert_called_once_with("grading/tests/penalty_test.py", scorer_instance.config.penalty_config)

def test_set_final_score(scorer_instance, mock_grader):
    """Test calculating the final score."""
    scorer_instance.base_grader = mock_grader
    scorer_instance.bonus_grader = mock_grader
    scorer_instance.penalty_grader = mock_grader
    final_score = scorer_instance.set_final_score()
    assert final_score == 80 + 80 - 80
    assert scorer_instance.final_score == final_score

@patch("utils.report_generator.generate_md")
def test_get_feedback(mock_generate_md, scorer_instance, mock_grader):
    """Test generating feedback."""
    scorer_instance.base_grader = mock_grader
    scorer_instance.bonus_grader = mock_grader
    scorer_instance.penalty_grader = mock_grader
    scorer_instance.final_score = 80
    scorer_instance.get_feedback()
    mock_generate_md.assert_called_once()

@patch("builtins.open", create=True)
@patch("utils.report_generator.generate_md")
def test_create_feedback(mock_generate_md, mock_open, scorer_instance, mock_grader):
    """Test creating feedback file."""
    mock_generate_md.return_value = "Feedback content"
    scorer_instance.base_grader = mock_grader
    scorer_instance.bonus_grader = mock_grader
    scorer_instance.penalty_grader = mock_grader
    scorer_instance.final_score = 80
    scorer_instance.create_feedback()
    mock_open.assert_called_once_with(scorer_instance.path.getFilePath("feedback.md"), 'w', encoding="utf-8")
    mock_open().write.assert_called_once_with("Feedback content")

@patch("grading.final_scorer.Config.create_config")
@patch("grading.grader.Grader.create")
def test_create_with_scores(mock_grader_create, mock_config_create, mock_grader):
    """Test creating a Scorer instance with scores."""
    mock_grader_create.return_value = mock_grader
    mock_config_create.return_value = MagicMock()
    scorer = Scorer.create_with_scores("test_folder", "author_name", "config.json", "base_test.py", "bonus_test.py", "penalty_test.py")
    assert scorer.config is not None
    assert scorer.base_grader == mock_grader
    assert scorer.bonus_grader == mock_grader
    assert scorer.penalty_grader == mock_grader
    assert scorer.final_score == 80 + 80 - 80

@patch("grading.final_scorer.Scorer.create_with_scores")
def test_quick_build(mock_create_with_scores):
    """Test quick building a Scorer instance."""
    mock_create_with_scores.return_value = MagicMock()
    scorer = Scorer.quick_build("author_name")
    mock_create_with_scores.assert_called_once_with("tests", "author_name", "criteria.json", "test_base.py", "test_bonus.py", "test_penalty.py")
    assert scorer is not None