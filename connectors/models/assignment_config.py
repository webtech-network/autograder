import os
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field


class AssignmentConfig(BaseModel):
    template: str = "custom"
    criteria: Dict[str, Any]
    feedback: Dict[str, Any]
    setup: Dict[str, Any]
    custom_template_str: Optional[str] = None
    
    def __str__(self) -> str:
        """
        Returns a string representation of the AssignmentConfig object.
        """
        criteria = "[Loaded]" if self.criteria else "[Not Loaded]"
        feedback = "[Loaded]" if self.feedback else "[Not Loaded]"
        setup = "[Loaded]" if self.setup else "[Not Loaded]"
        template_str = "[Loaded]" if self.custom_template_str else "[Not Loaded]"
        
        return (
            f"AssignmentConfig(template={self.template}, criteria={criteria}, "
            f"feedback={feedback}, setup={setup}, custom_template_str={template_str})"
        )