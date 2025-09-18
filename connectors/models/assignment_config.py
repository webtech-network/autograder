import os
from connectors.models.test_files import TestFiles


class AssignmentConfig:
    def __init__(self, criteria: dict, feedback: dict, setup: dict ,template="custom", custom_template_str: str = None):
        """
        Initializes the Preset model with the provided test files and configuration files.

        :param template: The template type (ex: "web dev",default is "custom").
        :param criteria: The assignment criteria configuration.
        :param feedback: The feedback configuration.
        :param setup: The setup configuration (mandatory test files and setup commands).
        :param custom_template_str: Optional; the python file that represents the custom template.
        """
        self.template = template
        self.criteria = criteria
        self.feedback = feedback
        self.setup = setup
        self.custom_template_str = custom_template_str

    def __str__(self):
        """
        Returns a string representation of the AssignmentConfig object.
        """
        criteria = feedback = setup = template = template_str =  "[Not Loaded]"
        if self.criteria:
            criteria = "[Loaded]"
        if self.feedback:
            feedback = "[Loaded]"
        if self.setup:
            setup = "[Loaded]"
        if self.custom_template_str:
            template_str = "[Loaded]"

        return f"AssignmentConfig(template={self.template}, criteria={criteria}, feedback={feedback}, setup={setup}, custom_template_str={template_str})"

