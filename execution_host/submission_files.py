"""A submission read from a directory: what the Action grades and what an author checks.

Both hosts read a checkout the same way, so a reference solution is graded
from exactly the files a student's repository would contribute.
"""
import os
import stat
from pathlib import Path

from autograder.models.dataclass.submission import SubmissionFile
from sandbox_manager.submission_contract import (
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_TOTAL_FILE_BYTES,
    validate_content,
    validate_filename,
)

#: Never graded: version control, workflow and definition files, and the Action's own output.
EXCLUDED_DIRECTORIES = (".git", ".github", ".autograder")


def collect_files(root) -> dict[str, SubmissionFile]:
    """Every regular UTF-8 file under ``root`` by relative POSIX path, within the submission limits.

    Raises ``ValueError`` naming the file or limit when the directory cannot be graded as is.
    """
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError(f"Submission directory {root} must be an existing readable directory.")
    files = {}
    total_bytes = 0

    def walk_error(error):
        raise ValueError(f"Submission directory {root} contains an unreadable directory.") from error

    for directory, directories, filenames in os.walk(root, onerror=walk_error):
        directories[:] = sorted(d for d in directories if d not in EXCLUDED_DIRECTORIES)
        for name in directories:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Submission directories must not be symbolic links.")
        for name in sorted(filenames):
            path = Path(directory) / name
            filename = validate_filename(path.relative_to(root).as_posix())
            if len(files) >= MAX_FILES:
                raise ValueError(f"Submission must contain at most {MAX_FILES} files.")
            try:
                if not stat.S_ISREG(path.lstat().st_mode):
                    raise ValueError(f"Submission files must be regular files: {filename}")
                # Binary reading preserves CRLF and bounds memory before decoding.
                limit = min(MAX_FILE_BYTES, MAX_TOTAL_FILE_BYTES - total_bytes)
                with path.open("rb") as handle:
                    data = handle.read(limit + 1)
                if len(data) > MAX_FILE_BYTES:
                    raise ValueError(f"Submission file exceeds {MAX_FILE_BYTES} bytes: {filename}")
                if total_bytes + len(data) > MAX_TOTAL_FILE_BYTES:
                    raise ValueError(f"Submission exceeds {MAX_TOTAL_FILE_BYTES} total file bytes.")
                content = validate_content(data.decode("utf-8"))
            except (OSError, UnicodeError) as exc:
                raise ValueError(f"Submission file is not readable UTF-8 text: {filename}") from exc
            files[filename] = SubmissionFile(filename=filename, content=content)
            total_bytes += len(data)
    if not files:
        raise ValueError(f"Submission directory {root} contains no submission files.")
    return files
