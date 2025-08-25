


class AutograderResponse:
    """
    Represents the response from the autograder.
    """

    def __init__(self,status, final_score: float = 0.0, feedback: str = ""):
        self.status = status
        self.final_score = final_score
        self.feedback = feedback

    def __repr__(self):
        return f"AutograderResponse(status={self.status}, final_score={self.final_score}, feedback_size={len(self.feedback)})"""