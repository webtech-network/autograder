from connectors.models.assignment_files import AssignmentFiles


class AutograderRequest:
    def __init__(
            self,
            assignment_files: AssignmentFiles,
            student_name, preset,
            test_framework=None,
            feedback_mode="default",
            openai_key=None,
            redis_url=None,
            redis_token=None):
        self.assignment_files = assignment_files
        self.student_name = student_name
        self.preset = preset
        self.test_framework = test_framework
        self.feedback_mode = feedback_mode
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token

    @classmethod
    def create_request(cls):
        pass
