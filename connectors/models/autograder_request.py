from connectors.models.assignment_config import AssignmentConfig

class AutograderRequest:
    def __init__(
            self,
            submission_files: dict,
            assignment_config: AssignmentConfig,
            student_name,
            student_credentials=None,
            feedback_mode="default",
            openai_key=None,
            redis_url=None,
            redis_token=None):
        self.submission_files = submission_files
        self.assignment_config = assignment_config
        self.student_name = student_name
        self.student_credentials = student_credentials
        self.feedback_mode = feedback_mode
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token
