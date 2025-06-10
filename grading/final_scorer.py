from grading.grader import Grader
from utils.report_generator import generate_md
from utils.path import Path
from utils.config_loader import Config
from time import sleep

class Scorer:
    """This class is used to manage the grading process for the three test suites: base, bonus, and penalty."""
    def __init__(self,test_folder,author,config):
        self.path = Path(__file__,test_folder) # Path to the test folder
        self.author = author # Author of the code being graded
        self.config = config # Config instance containing the configurations for all the test files
        self.base_grader = None # Grader instance for the base test file
        self.bonus_grader = None # Grader instance for the bonus test file
        self.penalty_grader = None # Grader instance for the penalty test file
        self.final_score = 0  # Final score after grading all test files

    def set_base_score(self,filename):
        """Set the base score by creating a Grader instance for the base test file."""
        self.base_grader = Grader.create(self.path.getFilePath(filename),self.config.base_config)

    def set_bonus_score(self,filename):
        """Set the bonus score by creating a Grader instance for the bonus test file."""
        self.bonus_grader = Grader.create(self.path.getFilePath(filename),self.config.bonus_config)

    def set_penalty_score(self,filename):
        """Set the penalty score by creating a Grader instance for the penalty test file."""
        self.penalty_grader = Grader.create(self.path.getFilePath(filename),self.config.penalty_config)

    def set_final_score(self):
        """Calculate the final score by combining the scores from base, bonus, and penalty test files."""
        final_score = (self.base_grader.generate_score())+(self.bonus_grader.generate_score()) - (self.penalty_grader.generate_score())
        self.final_score = final_score
        return final_score

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
    def create_with_scores(cls,test_folder,author, config: Config ,base_file,bonus_file,penalty_file):
        """Create a Scorer instance with the specified test files and author."""
        scorer = cls(test_folder,author,config)
        scorer.set_base_score(base_file)
        scorer.set_bonus_score(bonus_file)
        scorer.set_penalty_score(penalty_file)
        scorer.set_final_score()
        sleep(2)
        return scorer

    @classmethod
    def quick_build(cls, author,config):
        """Quickly build a Scorer instance with default test files and author."""
        scorer = Scorer.create_with_scores("tests", author,config, "test_base.py", "test_bonus.py", "test_penalty.py")
        return scorer

if __name__ == '__main__':
    score = Scorer.create_with_scores("tests","Arthur","test_base.py","test_bonus.py","test_penalty.py")
    print(score.final_score)
