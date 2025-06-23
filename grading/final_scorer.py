from grading.grader import Grader
from utils.report_generator import generate_md
from utils.path import Path
from utils.config_loader import Config
from time import sleep

class Scorer:
    """This class is used to manage the grading process for the three test suites: base, bonus, and penalty."""
    def __init__(self,test_folder,author):
        self.path = Path(__file__,test_folder) # Path to the test folder
        self.author = author # Author of the code being graded
        self.config = None # Config instance containing the configurations for all the test files
        self.base_grader = None # Grader instance for the base test file
        self.bonus_grader = None # Grader instance for the bonus test file
        self.penalty_grader = None # Grader instance for the penalty test file
        self.final_score = 0  # Final score after grading all test files

    def set_base_score(self,filename):
        """Set the base score by creating a Grader instance for the base test file."""
        self.base_grader = Grader.create(f"tests/{filename}",self.config.base_config)

    def set_bonus_score(self,filename):
        """Set the bonus score by creating a Grader instance for the bonus test file."""
        self.bonus_grader = Grader.create(f"tests/{filename}",self.config.bonus_config)

    def set_penalty_score(self,filename):
        """Set the penalty score by creating a Grader instance for the penalty test file."""
        self.penalty_grader = Grader.create(f"tests/{filename}",self.config.penalty_config)

    def set_final_score(self):
        """Calculate the final score by combining the scores from base, bonus, and penalty test files."""
        base_score = self.base_grader.generate_score() # Generate the score for the base test file
        self.final_score = base_score
        if base_score < 100:
            self.give_bonus_score(base_score) # If the base score is less than 100, add the bonus score
        penalty_score = self.penalty_grader.generate_score() # Generate the score for the penalty test file
        self.final_score -= penalty_score # Subtract the penalty score from the final score
        return self.final_score

    def give_bonus_score(self,base_score):
        """Add the bonus score to the final score if the base score is less than 100."""
        bonus_score = self.bonus_grader.generate_score()
        if 100 - base_score >= self.bonus_grader.test_config.weight:
            self.final_score += bonus_score
        elif 100 - base_score < self.bonus_grader.test_config.weight:
            self.final_score += (bonus_score/self.bonus_grader.test_config.weight) * (100 - base_score) # If the bonus score exceeds the remaining points to 100, scale it down

    def get_feedback(self):
        """Generate feedback in Markdown format based on the test results."""
        base_dict = {"passed": self.base_grader.passed_tests, "failed": self.base_grader.failed_tests} # Format the base test results
        bonus_dict = {"passed": self.bonus_grader.passed_tests, "failed": self.bonus_grader.failed_tests} # Format the bonus test results
        penalty_dict = {"passed": self.penalty_grader.passed_tests, "failed": self.penalty_grader.failed_tests} # Format the penalty test results
        return generate_md(base_dict, bonus_dict, penalty_dict, self.final_score, self.author) # Calls the generate_md function to create the feedback

    def create_feedback(self):
        """Create a feedback file in Markdown format with the test results and final score."""
        with open(self.path.getFilePath("feedback.md"),'w',encoding="utf-8") as feedback:
            feedback.write(self.get_feedback())

    @classmethod
    def create_with_scores(cls,test_folder,author, config_file ,base_file,bonus_file,penalty_file):
        """Create a Scorer instance with the specified test files and author."""
        scorer = cls(test_folder,author)
        scorer.config = Config.create_config(config_file) # Load the configuration from the specified file
        scorer.set_base_score(base_file)
        scorer.set_bonus_score(bonus_file)
        scorer.set_penalty_score(penalty_file)
        scorer.set_final_score()
        sleep(2)
        return scorer

    @classmethod
    def quick_build(cls, author):
        """Quickly build a Scorer instance with default test files and author."""
        scorer = Scorer.create_with_scores("tests", author,"criteria.json", "test_base.py", "test_bonus.py", "test_penalty.py")
        return scorer
