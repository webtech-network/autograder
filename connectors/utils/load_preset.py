import os
import shutil


def import_preset(preset, custom_criteria=False, custom_feedback=False):
    """
    Responsible for importing grading presets to the autograder core.
    Checks the preset name and imports the corresponding configuration files from the presets package.
    """
    # Get the project root directory
    if preset == "custom":
        return
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    preset_dir = os.path.join(project_root, 'presets', preset)
    request_bucket = os.path.join(project_root, 'autograder', 'core', 'request_bucket')
    validation_dir = os.path.join(project_root, 'autograder', 'core', 'validation')

    if not os.path.isdir(preset_dir):
        raise ValueError(f"Preset directory not found: {preset_dir}")

    os.makedirs(request_bucket, exist_ok=True)
    os.makedirs(validation_dir, exist_ok=True)

    # Handle specific presets
    if preset in ["html-css-js", "etapa-2"]:
        # Copy .json files to /core/request_bucket
        for file in os.listdir(preset_dir):
            if file.endswith('.json'):
                src = os.path.join(preset_dir, file)
                dst = os.path.join(request_bucket, file)
                shutil.copy2(src, dst)

        # Copy test files from /tests to /core/validation
        tests_dir = os.path.join(preset_dir, 'tests')
        if os.path.isdir(tests_dir):
            for file in os.listdir(tests_dir):
                src = os.path.join(tests_dir, file)
                dst = os.path.join(validation_dir, file)
                shutil.copy2(src, dst)
    else:
        raise ValueError(f"Unknown preset: {preset}. Please provide a valid preset name.")