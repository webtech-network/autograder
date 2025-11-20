from typing import List,Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field

from autograder.core.models.test_result import TestResult



class NodeType(str, Enum):
    """Represents the types of nodes in the result tree"""
    ROOT = "root"
    CATEGORY = "category" #base, bonus, penalty 
    SUBJECT = "subject"

class ResultNode(BaseModel)
    
    node_type : NodeType
    name: str

    
