from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from connectors.models.assignment_config import AssignmentConfig


class AutograderRequest(BaseModel):
    submission_files: Dict[str, Any]
    assignment_config: AssignmentConfig
    student_name: str
    student_credentials: Optional[str] = None
    include_feedback: bool = False
    feedback_mode: str = "default"
    openai_key: Optional[str] = None
    redis_url: Optional[str] = None
    redis_token: Optional[str] = None
    criteria_tree: Optional[Any] = None
    reporter: Optional[Any] = None
    feedback_report: Optional[Any] = None
    
    def __str__(self) -> str:
        stri = f"{len(self.submission_files)} submission files.\n"
        stri += f"Assignment config: {self.assignment_config}\n"
        stri += f"Student name: {self.student_name}\n"
        stri += f"Feedback mode: {self.feedback_mode}\n"
        return stri
    
    @classmethod
    def build_empty_request(cls) -> "AutograderRequest":
        return cls(
            submission_files={},
            assignment_config=AssignmentConfig(
                criteria={}, 
                feedback={}, 
                setup={}, 
                template=""
            ),
            student_name="",
            include_feedback=False
        )