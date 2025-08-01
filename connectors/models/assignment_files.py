class AssignmentFiles:
    """
    Keeps all the configuration files for an assignment.
    """
    def __init__(self,submission_files,criteira,feedback,ai_feedback=None):
        self.submission_files = submission_files
        self.criteria = criteira
        self.feedback = feedback
        self.ai_feedback = ai_feedback
