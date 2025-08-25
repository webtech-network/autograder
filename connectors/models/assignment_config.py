import os
from connectors.models.test_files import TestFiles


class AssignmentConfig:
    def __init__(self, test_files, criteria, feedback, setup ,preset="custom",ai_feedback=None,test_framework="pytest"):
        """
        Initializes the Preset model with the provided test files and configuration files.

        :param test_files: TestFiles; The test files associated with the preset.
        :param criteria: The criteria for grading.
        :param feedback: The feedback configuration.
        :param ai_feedback: Optional; AI-generated feedback configuration.
        """
        self.test_framework = test_framework
        self.preset = preset
        self.test_files = test_files
        self.criteria = criteria
        self.feedback = feedback
        self.ai_feedback = ai_feedback if ai_feedback is not None else {}
        self.setup = setup

    def set_test_framework(self, test_framework):
        """
        Sets the test framework for the assignment configuration.
        """
        self.test_framework = test_framework

    def __str__(self):
        """
        Returns a string representation of the AssignmentConfig object.
        """
        criteria = feedback = ai_feedback = setup = "[Not Loaded]"
        if self.criteria:
            criteria = "[Loaded]"
        if self.feedback:
            feedback = "[Loaded]"
        if self.ai_feedback:
            ai_feedback = "[Loaded]"
        if self.setup:
            setup = "[Loaded]"
        return f"AssignmentConfig(preset={self.preset}, test_framework={self.test_framework}, " \
                f"test_files={self.test_files}, criteria={criteria}, " \
                f"feedback={feedback}, " \
                f"ai_feedback={ai_feedback}" \
                f"setup={setup})"
    @classmethod
    def load_preset(cls, preset_name):
        """
        Loads a preset and generates a Preset object with the correct attributes.
        The test_framework is inferred from the test file extensions.
        """
        if preset_name == "custom":
            print("Custom mode enabled. No preset files will be loaded.")
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        preset_dir = os.path.join(project_root, 'presets', preset_name)

        if not os.path.isdir(preset_dir):
            raise ValueError(f"Preset not found: {preset_name}")

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
        setup = None

        for file in os.listdir(preset_dir):
            file_path = os.path.join(preset_dir, file)
            if file == "criteria.json":
                print("Loaded criteria.json")
                with open(os.path.join(preset_dir, file), 'r', encoding='utf-8') as f:
                    criteria = f.read()
            elif file == "feedback.json":
                print("Loaded feedback.json")
                with open(os.path.join(preset_dir, file), 'r', encoding='utf-8') as f:
                    feedback = f.read()
            elif file == "ai-feedback.json":
                print("Loaded ai-feedback.json")
                with open(os.path.join(preset_dir, file), 'r', encoding='utf-8') as f:
                    ai_feedback = f.read()
            elif file == "autograder-setup.json":
                print("Loaded autograder-setup.json")
                with open(os.path.join(preset_dir, file), 'r', encoding='utf-8') as f:
                    setup = f.read()
            else:
                # Add other files to the other_files dictionary
                if os.path.isdir(file_path) or file == "__init__.py":
                    continue
                print("Saving " + file+" to other_files")

                with open(file_path, 'r', encoding='utf-8') as f:
                    other_files[file] = f.read()


        # Iterate through files in the preset directory
        preset_tests_dir = os.path.join(preset_dir, "tests")

        # Determine test framework based on file extensions
        test_framework = "pytest"  # default
        for file in os.listdir(preset_tests_dir):
            if file.endswith(".py"):
                test_framework = "pytest"
                break
            elif file.endswith(".js"):
                test_framework = "jest"
                break
            elif file.endswith(".json"):
                test_framework = "ai"
                break

        for file in os.listdir(preset_tests_dir):
            file_path = os.path.join(preset_tests_dir, file)

            if file.startswith("test_base"):
                with open(file_path, 'r', encoding='utf-8') as f:

                    test_base = f.read()
            elif file.startswith("test_bonus"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    test_bonus = f.read()
            elif file.startswith("test_penalty"):
                with open(file_path, 'r', encoding='utf-8') as f:
                    test_penalty = f.read()

        # Create TestFiles object
        test_files = TestFiles(
            test_base=test_base,
            test_bonus=test_bonus,
            test_penalty=test_penalty,
            other_files=other_files
        )

        # Return a new Preset object with detected test_framework
        return cls(
            preset=preset_name,
            test_files=test_files,
            criteria=criteria,
            feedback=feedback,
            ai_feedback=ai_feedback,
            setup=setup,
            test_framework=test_framework
        )

    @classmethod
    def load_custom(cls,test_files,criteria,feedback,ai_feedback=None,setup=None,test_framework="pytest"):
        return cls(test_files,criteria,feedback,ai_feedback=ai_feedback,setup=setup,test_framework=test_framework)
