from connectors.models.assignment_config import AssignmentConfig

class AutograderRequest:
    def __init__(
            self,
            submission_files: dict,
            assignment_config: AssignmentConfig,
            student_name,
            student_credentials=None,
            include_feedback=False,
            feedback_mode="default",
            openai_key=None,
            redis_url=None,
            redis_token=None):
        self.submission_files = submission_files
        self.assignment_config = assignment_config
        self.student_name = student_name
        self.student_credentials = student_credentials
        self.include_feedback = include_feedback
        self.feedback_mode = feedback_mode
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token
    def __str__(self):
        stri = f"{len(self.submission_files)} submission files.\n"
        stri += f"Assignment config: {self.assignment_config}\n"
        stri += f"Student name: {self.student_name}\n"
        stri += f"Feedback mode: {self.feedback_mode}\n"
        return stri