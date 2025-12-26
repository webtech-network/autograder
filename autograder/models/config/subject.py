from typing import Dict, List, Optional
from .test import TestConfig
from pydantic import BaseModel, model_validator


class SubjectConfig(BaseModel):
    weight: Optional[int] = None
    subjects: Optional[Dict[str, "SubjectConfig"]] = None
    tests: Optional[List[TestConfig | str]] = None
    subjects_weight: Optional[int] = None

    @model_validator(mode="after")
    def check_subjects_and_tests(self) -> "SubjectConfig":
        if self.subjects is None and self.tests is None:
            raise ValueError(
                "You needs to defined at least one of: 'subjects' or 'tests'"
            )

        if self.subjects and self.tests:
            if self.subjects_weight is None:
                raise ValueError(
                    "When defining both subjects and tests, you need to define subjects_weight"
                )

            if self.subjects_weight <= 0 or self.subjects_weight >= 100:
                raise ValueError(
                    "subjects_weight needs to be in exclusive range ]0,100["
                )

        return self
