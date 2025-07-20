from autograder.core.grading.scorer import Scorer

scorer = Scorer.quick_build("")

final_score = scorer.final_score
print(final_score)