class AssignmentFiles:
    """
    Keeps all the configuration files for an assignment.
    """
    def __init__(self,submission_files,criteria,feedback,ai_feedback=None):
        self.submission_files = submission_files #dict of file names to file contents
        self.criteria = criteria
        self.feedback = feedback
        self.ai_feedback = ai_feedback
