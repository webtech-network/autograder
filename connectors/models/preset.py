import os
from connectors.models.test_files import TestFiles


class AssignmentConfig:
    def __init__(self, preset,test_files, criteria, feedback, ai_feedback=None):
        """
        Initializes the Preset model with the provided test files and configuration files.

        :param test_files: TestFiles; The test files associated with the preset.
        :param criteria: The criteria for grading.
        :param feedback: The feedback configuration.
        :param ai_feedback: Optional; AI-generated feedback configuration.
        """
        self.preset = preset
        self.test_files = test_files
        self.criteria = criteria
        self.feedback = feedback
        self.ai_feedback = ai_feedback if ai_feedback is not None else {}

    @classmethod
    def load_preset(cls, preset_name):
        """
        Loads a preset and generates a Preset object with the correct attributes.
        """
        if preset_name == "custom":
            print("Custom mode enabled. No preset files will be loaded.")
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        preset_dir = os.path.join(project_root, 'presets', preset_name)

        if not os.path.isdir(preset_dir):
            raise ValueError(f"Preset not found: {preset_dir}")

        # Initialize variables for test files
        test_base = None
        test_bonus = None
        test_penalty = None
        fatal_tests = None
        other_files = {}

        # Initialize variables for criteria and feedback
        criteria = None
        feedback = None
        ai_feedback = None

        # Iterate through files in the preset directory
        for file in os.listdir(preset_dir):
            file_path = os.path.join(preset_dir, file)

            if file.startswith("base_tests"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    test_base = f.read()
            elif file.startswith("bonus_tests"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    test_bonus = f.read()
            elif file.startswith("penalty_tests"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    test_penalty = f.read()
            elif file.startswith("fatal_analysis"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    fatal_tests = f.read()
            else:
                # Add other files to the other_files dictionary
                with open(file_path, 'r', encoding='utf-8') as f:
                    other_files[file] = f.read()

        # Create TestFiles object
        test_files = TestFiles(
            test_base=test_base,
            test_bonus=test_bonus,
            test_penalty=test_penalty,
            fatal_tests=fatal_tests,
            other_files=other_files
        )

        # Return a new Preset object
        return cls(
            preset=preset_name,
            test_files=test_files,
            criteria=criteria,
            feedback=feedback,
            ai_feedback=ai_feedback
        )
