import os
from connectors.models.test_files import TestFiles


class AssignmentConfig:
    def __init__(self, criteria, feedback, setup ,template="custom"):
        """
        Initializes the Preset model with the provided test files and configuration files.

        :param template: The template type (ex: "web dev",default is "custom").
        :param criteria: The assignment criteria configuration.
        :param feedback: The feedback configuration.
        :param setup: The setup configuration (mandatory test files and setup commands).
        """
        self.template = template
        self.criteria = criteria
        self.feedback = feedback
        self.setup = setup

    def __str__(self):
        """
        Returns a string representation of the AssignmentConfig object.
        """
        criteria = feedback = setup = "[Not Loaded]"
        if self.criteria:
            criteria = "[Loaded]"
        if self.feedback:
            feedback = "[Loaded]"

        if self.setup:
            setup = "[Loaded]"
        return f"AssignmentConfig(template={self.template}, criteria={criteria}, feedback={feedback}, setup={setup})"

