from typing import List

from dataclasses import dataclass

@dataclass
class SubmissionFile:
    filename: str
    content: str

@dataclass
class Submission:
    username: str
    user_id: int
    assignment_id: int
    submission_files: List[SubmissionFile]
