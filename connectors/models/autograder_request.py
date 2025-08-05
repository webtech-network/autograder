from connectors.models.preset import Preset
from connectors.models.test_files import TestFiles


class AutograderRequest:
    def __init__(
            self,
            assignment_files: dict,
            preset: Preset,
            student_name,
            test_framework,
            feedback_mode="default",
            openai_key=None,
            redis_url=None,
            redis_token=None):
        self.assignment_files = assignment_files
        self.preset = preset
        self.student_name = student_name
        self.test_framework = test_framework
        self.feedback_mode = feedback_mode
        self.openai_key = openai_key
        self.redis_url = redis_url
        self.redis_token = redis_token
