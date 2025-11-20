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


    def add_child(self,child: 'ResultNode'): 
        self.children.append(child)

    def get_all_tests_results(self) -> List[TestResult]:

        results = list(self.test_results)
        for child in self.children:
            results.extend(child.get_all_tests_results())
        
        return results
    
    def find_node(self, name: str, node_type: Optional[NodeType] = None) -> Optional['ResultNode']:

        if self.name == name:
            if NodeType is None or self.node_type == node_type:
                return self
            
        for child in self.children: 
            result = child.find_node(name, node_type)
            if result:
                return result
            
        return None
    
    def get_node_path(self, name: str) -> Optional[List['ResultNode']]:
        
        if self.name  == name:
            return [self]
        
        




    
