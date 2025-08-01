import os
import shutil


def load_preset(preset, custom_criteria=False, custom_feedback=False):
    """
    Responsible for importing grading presets to the autograder core.
    Checks the preset name and imports the corresponding configuration files from the presets package.
    Cleans the /validation (except __init__.py) and /request_bucket folders before importing.
    """
    if preset == "custom":
        print("Custom mode enabled. No preset files will be loaded.")
        return
    if preset in ["html-css-js", "etapa-2"]:
        print("Loading preset: " + preset)
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
        preset_dir = os.path.join(project_root, 'presets', preset)
        request_bucket = os.path.join(project_root, 'autograder', '', 'request_bucket')
        validation_dir = os.path.join(project_root, 'autograder', 'validation')

        if not os.path.isdir(preset_dir):
            raise ValueError(f"Preset directory not found: {preset_dir}")

        os.makedirs(request_bucket, exist_ok=True)
        os.makedirs(validation_dir, exist_ok=True)

        # Clean request_bucket
        for file in os.listdir(request_bucket):
            file_path = os.path.join(request_bucket, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

        # Clean validation_dir except __init__.py
        for file in os.listdir(validation_dir):
            file_path = os.path.join(validation_dir, file)
            if os.path.isfile(file_path) and file != '__init__.py':
                os.remove(file_path)

        # Handle specific presets

        # Copy .json files to /request_bucket
        for file in os.listdir(preset_dir):
            if file.endswith('.json'):
                src = os.path.join(preset_dir, file)
                dst = os.path.join(request_bucket, file)
                shutil.copy2(src, dst)

        #Copy all other files to /validation
        for file in os.listdir(preset_dir):
            if not file.endswith('.json') and file != 'tests' and file !='__init__.py':
                src = os.path.join(preset_dir, file)
                dst = os.path.join(validation_dir, file)
                shutil.copy2(src, dst)
        # Copy test files from /tests to /validation/tests
        tests_dir = os.path.join(preset_dir, 'tests')
        tests_dst_dir = os.path.join(validation_dir, 'tests')
        if os.path.isdir(tests_dir):
            # Clean the destination directory first
            if os.path.isdir(tests_dst_dir):
                for file in os.listdir(tests_dst_dir):
                    file_path = os.path.join(tests_dst_dir, file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
            else:
                os.makedirs(tests_dst_dir, exist_ok=True)
            for file in os.listdir(tests_dir):
                src = os.path.join(tests_dir, file)
                dst = os.path.join(tests_dst_dir, file)
                shutil.copy2(src, dst)
    else:
        raise ValueError(f"Unknown preset: {preset}. Please provide a valid preset name.")



if __name__ == "__main__":
    load_preset("html-css-js")