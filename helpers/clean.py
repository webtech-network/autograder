
import os
import shutil



def recreate_directory(directory_path: str):
    print(f"Resetting directory: {directory_path}")
    if os.path.isdir(directory_path):
        try:
            shutil.rmtree(directory_path)
        except Exception as e:
            print(f'Error: Failed to delete directory {directory_path}. Reason: {e}')
    try:
        os.makedirs(directory_path, exist_ok=True)
    except Exception as e:
        print(f'Error: Failed to create directory {directory_path}. Reason: {e}')

print("Finishing session and cleaning up workspace...")

# Get the project root (two levels up from this file)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Define paths for the directories that need to be cleaned, relative to project root
validation_path = os.path.join(project_root, "autograder", "validation")
request_bucket_path = os.path.join(project_root, "autograder", "request_bucket")

# Clean and recreate the top-level directories.
recreate_directory(validation_path)
recreate_directory(request_bucket_path)

# Recreate the essential nested directory structure inside the now-clean parent directories.
validation_results_path = os.path.join(validation_path, "results")
submission_path = os.path.join(request_bucket_path, "submission")

os.makedirs(validation_results_path, exist_ok=True)
os.makedirs(submission_path, exist_ok=True)

print("Cleanup complete. Ready for a new session.")