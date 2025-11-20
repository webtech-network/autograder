from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

from autograder.core.models.test_result import TestResult



class NodeType(str, Enum):
    """Represents the types of nodes in the result tree"""
    ROOT = "root"
    CATEGORY = "category" #base, bonus, penalty 
    SUBJECT = "subject"

class ResultNode(BaseModel):
    """This class represents a node in the result tree"""
    
    node_type : NodeType
    name: str

    unweighted_score: Optional[float] = None
    weighted_score: Optional[float] = None
    weight: float = 0.0
    max_score: Optional[float] = None

    children: List['ResultNode'] = Field(default_factory=list)

    test_results: List[TestResult] = Field(default_factory=list)

    total_test: int = 0

    model_config =  {"arbitrary-types-allowed": True}

    



    
