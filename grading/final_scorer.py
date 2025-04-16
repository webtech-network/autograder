from grading.grader import Grader
from utils.report_generator import generate_md
from utils.path import Path
from utils.config_loader import Config
from time import sleep

class Scorer:
    def __init__(self,test_folder,author,config):
        self.path = Path(__file__,test_folder)
        self.author = author
        self.config = config
        self.base_grader = None
        self.bonus_grader = None
        self.penalty_grader = None
        self.final_score = 0

    def set_base_score(self,filename):
        self.base_grader = Grader.create(self.path.getFilePath(filename),self.config.base_config)

    def set_bonus_score(self,filename):
        self.bonus_grader = Grader.create(self.path.getFilePath(filename),self.config.bonus_config)

    def set_penalty_score(self,filename):
        self.penalty_grader = Grader.create(self.path.getFilePath(filename),self.config.penalty_config)

    def set_final_score(self):
        final_score = (self.base_grader.generate_score())+(self.bonus_grader.generate_score()) - (self.penalty_grader.generate_score())
        self.final_score = final_score
        return final_score

    def get_feedback(self):
        base_dict = {"passed": self.base_grader.passed_tests, "failed": self.base_grader.failed_tests}
        bonus_dict = {"passed": self.bonus_grader.passed_tests, "failed": self.bonus_grader.failed_tests}
        penalty_dict = {"passed": self.penalty_grader.passed_tests, "failed": self.penalty_grader.failed_tests}
        return generate_md(base_dict, bonus_dict, penalty_dict, self.final_score, self.author)

    def create_feedback(self):
        with open(self.path.getFilePath("feedback.md"),'w',encoding="utf-8") as feedback:
            feedback.write(self.get_feedback())

    @classmethod
    def create_with_scores(cls,test_folder,author, config: Config ,base_file,bonus_file,penalty_file):
        scorer = cls(test_folder,author,config)
        scorer.set_base_score(base_file)
        scorer.set_bonus_score(bonus_file)
        scorer.set_penalty_score(penalty_file)
        scorer.set_final_score()
        sleep(2)
        return scorer

    @classmethod
    def quick_build(cls, author,config):
        scorer = Scorer.create_with_scores("tests", author,config, "test_base.py", "test_bonus.py", "test_penalty.py")
        return scorer

if __name__ == '__main__':
    score = Scorer.create_with_scores("tests","Arthur","test_base.py","test_bonus.py","test_penalty.py")
    print(score.final_score)
