from connectors.models.assignment_config import AssignmentConfig


class CustomAssignmentConfig(AssignmentConfig):
    def __init__(self, criteria, feedback, setup, library_file):
        super().__init__(criteria, feedback, setup, template="custom")
        library_file = library_file # Like WebDevLibrary.py