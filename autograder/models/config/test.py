from typing import List, Optional
from pydantic import BaseModel


class TestConfig(BaseModel):
    name: str
    file: str
    calls: Optional[List[List[str]]] = None
