"""final_scorer.py

This module contains the Scorer class, which manages the grading process for three test suites:
base, bonus, and penalty. It calculates the final score, generates feedback, and creates a
feedback file in Markdown format.

Classes:
    Scorer: Manages the grading process and provides methods to calculate scores and generate feedback.

Example:
    scorer = Scorer.create_with_scores("tests", "Arthur", config, "test_base.py", "test_bonus.py", "test_penalty.py")
    print(scorer.final_score)
"""

from grading.grader import Grader
from utils.report_generator import generate_md
from utils.path import Path
from utils.config_loader import Config
from time import sleep

class Scorer:
    """Manages the grading process for the three test suites: base, bonus, and penalty.

    Attributes:
        path (Path): Path to the test folder.
        author (str): Author of the code being graded.
        config (Config): Config instance containing configurations for all test files.
        base_grader (Grader): Grader instance for the base test file.
        bonus_grader (Grader): Grader instance for the bonus test file.
        penalty_grader (Grader): Grader instance for the penalty test file.
        final_score (int): Final score after grading all test files.
    """

    def __init__(self, test_folder, author, config):
        """Initializes a Scorer instance.

        Args:
            test_folder (str): Path to the test folder.
            author (str): Author of the code being graded.
            config (Config): Config instance containing configurations for all test files.
        """
        self.path = Path(__file__, test_folder)
        self.author = author
        self.config = config
        self.base_grader = None
        self.bonus_grader = None
        self.penalty_grader = None
        self.final_score = 0

    def set_base_score(self, filename):
        """Sets the base score by creating a Grader instance for the base test file.

        Args:
            filename (str): Name of the base test file.
        """
        self.base_grader = Grader.create(self.path.getFilePath(filename), self.config.base_config)

    def set_bonus_score(self, filename):
        """Sets the bonus score by creating a Grader instance for the bonus test file.

        Args:
            filename (str): Name of the bonus test file.
        """
        self.bonus_grader = Grader.create(self.path.getFilePath(filename), self.config.bonus_config)

    def set_penalty_score(self, filename):
        """Sets the penalty score by creating a Grader instance for the penalty test file.

        Args:
            filename (str): Name of the penalty test file.
        """
        self.penalty_grader = Grader.create(self.path.getFilePath(filename), self.config.penalty_config)

    def set_final_score(self):
        """Calculates the final score by combining the scores from base, bonus, and penalty test files.

        Returns:
            int: The final score.
        """
        final_score = (
            self.base_grader.generate_score()
            + self.bonus_grader.generate_score()
            - self.penalty_grader.generate_score()
        )
        self.final_score = final_score
        return final_score

    def get_feedback(self):
        """Generates feedback in Markdown format based on the test results.

        Returns:
            str: Feedback in Markdown format.
        """
        base_dict = {"passed": self.base_grader.passed_tests, "failed": self.base_grader.failed_tests}
        bonus_dict = {"passed": self.bonus_grader.passed_tests, "failed": self.bonus_grader.failed_tests}
        penalty_dict = {"passed": self.penalty_grader.passed_tests, "failed": self.penalty_grader.failed_tests}
        return generate_md(base_dict, bonus_dict, penalty_dict, self.final_score, self.author)

    def create_feedback(self):
        """Creates a feedback file in Markdown format with the test results and final score."""
        with open(self.path.getFilePath("feedback.md"), 'w', encoding="utf-8") as feedback:
            feedback.write(self.get_feedback())

    @classmethod
    def create_with_scores(cls, test_folder, author, config, base_file, bonus_file, penalty_file):
        """Creates a Scorer instance with the specified test files and author.

        Args:
            test_folder (str): Path to the test folder.
            author (str): Author of the code being graded.
            config (Config): Config instance containing configurations for all test files.
            base_file (str): Name of the base test file.
            bonus_file (str): Name of the bonus test file.
            penalty_file (str): Name of the penalty test file.

        Returns:
            Scorer: A Scorer instance with the specified test files and author.
        """
        scorer = cls(test_folder, author, config)
        scorer.set_base_score(base_file)
        scorer.set_bonus_score(bonus_file)
        scorer.set_penalty_score(penalty_file)
        scorer.set_final_score()
        sleep(2)
        return scorer

    @classmethod
    def quick_build(cls, author, config):
        """Quickly builds a Scorer instance with default test files and author.

        Args:
            author (str): Author of the code being graded.
            config (Config): Config instance containing configurations for all test files.

        Returns:
            Scorer: A Scorer instance with default test files and author.
        """
        scorer = Scorer.create_with_scores("tests", author, config, "test_base.py", "test_bonus.py", "test_penalty.py")
        return scorer


if __name__ == '__main__':
    score = Scorer.create_with_scores("tests", "Arthur", "test_base.py", "test_bonus.py", "test_penalty.py")
    print(score.final_score)