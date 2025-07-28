
from autograder.core.grading.models.result import Result
from autograder.core.report.reporter_factory import Reporter
import os
class Scorer:
    """This class is used to manage the grading process for the three test suites: base, bonus, and penalty."""
    def __init__(self,author,config,base_grader,bonus_grader,penalty_grader,driver=None):
        self.author = author # Author of the code being graded
        self.config = config # Config instance containing the configurations for all the test files
        self.base_grader = base_grader # Grader instance for the base test file
        self.bonus_grader = bonus_grader # Grader instance for the bonus test file
        self.penalty_grader = penalty_grader # Grader instance for the penalty test file
        self.driver = driver



    def get_final_score(self):
        """Calculate the final score by combining the scores from base, bonus, and penalty test files."""
        base_score = self.base_grader.generate_score() # Generate the score for the base test file
        final_score = base_score
        if base_score < 100:
            final_score = self.give_bonus_score(base_score,final_score) # If the base score is less than 100, add the bonus score
        penalty_score = self.penalty_grader.generate_score() # Generate the score for the penalty test file
        final_score -= penalty_score # Subtract the penalty score from the final score
        return final_score

    def give_bonus_score(self,base_score,final_score):
        """Add the bonus score to the final score if the base score is less than 100."""
        bonus_score = self.bonus_grader.generate_score()
        if 100 - base_score >= self.bonus_grader.test_config.weight:
            final_score += bonus_score
        elif 100 - base_score < self.bonus_grader.test_config.weight:
            final_score += (bonus_score/self.bonus_grader.test_config.weight) * (100 - base_score) # If the bonus score exceeds the remaining points to 100, scale it down
        return final_score

    def generate_result(self):
        """Generate a Result instance with the grading results"""
        final_score = self.get_final_score()
        if final_score < 0:
            final_score = 0
        base_dict = {"passed": self.base_grader.passed_tests,
                     "failed": self.base_grader.failed_tests}  # Format the base test results
        bonus_dict = {"passed": self.bonus_grader.passed_tests,
                      "failed": self.bonus_grader.failed_tests}  # Format the bonus test results
        penalty_dict = {"passed": self.penalty_grader.passed_tests,
                        "failed": self.penalty_grader.failed_tests}  # Format the penalty test results
        return Result(final_score,self.author,None,base_dict, bonus_dict, penalty_dict)

    def get_reporter(self,token, openai_key = None ,mode="default"):
        """Creates a Reporter instance with the students results"""
        result = self.generate_result()
        print("Failed validation in base:", result.base_results["failed"])
        print("Failed validation in bonus:", result.bonus_results["failed"])
        print("Penalties detected:", result.penalty_results["passed"])
        if mode == "ai":
            allowed = self.driver.decrement_token_quota(self.author)
            if allowed:
                return Reporter.create_ai_reporter(result,token,self.driver.get_token_quota(self.author),openai_key)
        return Reporter.create_default_reporter(result,token)


    @classmethod
    def build(cls, author,config,base_grader,bonus_grader,penalty_grader):
        """Quickly build a Scorer instance with default test files and author."""
        if base_grader and bonus_grader and penalty_grader:
            return cls(author,config,base_grader,bonus_grader,penalty_grader)
        else:
            raise ValueError("Grader instances for base, bonus, and penalty must be provided.")

    @staticmethod
    def build_and_grade(author,config,base_grader,bonus_grader,penalty_grader):
        scorer = Scorer.build(author,config,base_grader,bonus_grader,penalty_grader)
        return scorer.generate_result()