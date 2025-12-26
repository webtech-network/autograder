from typing import Optional
from .subject import SubjectConfig
from pydantic import BaseModel


class CriteriaConfig(BaseModel):
    test_library: str
    base: SubjectConfig
    bonus: Optional[SubjectConfig] = None
    penalty: Optional[SubjectConfig] = None
