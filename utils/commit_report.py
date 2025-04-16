from github import Github
import base64
import os
def overwrite_report_in_repo(token,file_path="relatorio.md", new_content=""):
    try:
        # Get the current file content (if it exists)
        repo = os.getenv("GITHUB_REPOSITORY")
        g = Github(token)
        repo = g.get_repo(repo)
        try:
            file = repo.get_contents(file_path)
            file_sha = file.sha
        except:
            # If the file doesn't exist, no sha is retrieved
            file_sha = None

        # Encode the updated content in base64

        # Commit the new content to the repository (either overwrite or create new)
        commit_message = "Criando relatório..."
        if file_sha:
            repo.update_file(file_path, commit_message, new_content, file_sha)
        else:
            repo.create_file(file_path, commit_message, new_content)

        print(f"Report successfully overwritten in {file_path}")
    except Exception as e:
        print(f"Error while updating {file_path}: {str(e)}")