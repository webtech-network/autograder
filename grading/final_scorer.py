from grading.grader import get_test_results,get_score
from utils.report_generator import generate_md
from utils.path import Path
from time import sleep

class Scorer:
    def __init__(self,test_folder):
        self.path = Path(__file__,test_folder)
        self.base = ()
        self.bonus = ()
        self.penalty = ()
        self.final_score = 0
    def set_base_score(self,filename):
        self.base = get_test_results(self.path.getFilePath(filename))
    def set_bonus_score(self,filename):
        self.bonus = get_test_results(self.path.getFilePath(filename))
    def set_penalty_score(self,filename):
        self.penalty = get_test_results(self.path.getFilePath(filename))
    def set_final_score(self):
        final_score = (get_score(self.base[0],9) * 0.8 )+(get_score(self.bonus[0],4) * 0.2) - (get_score(self.penalty[0],5) * 0.3)
        self.final_score = final_score
        return final_score
    def get_feedback(self):
        def get_feedback(self):
            base_dict = {"passed": self.base[0], "failed": self.base[1]}
            bonus_dict = {"passed": self.bonus[0], "failed": self.bonus[1]}
            penalty_dict = {"passed": self.penalty[0], "failed": self.penalty[1]}
            return generate_md(base_dict, bonus_dict, penalty_dict, self.final_score, self.author)

    @classmethod
    def create_with_scores(cls,test_folder,base_file,bonus_file,penalty_file):
        scorer = cls(test_folder)
        scorer.set_base_score(base_file)
        scorer.set_bonus_score(bonus_file)
        scorer.set_penalty_score(penalty_file)
        scorer.set_final_score()
        sleep(2)
        return scorer
