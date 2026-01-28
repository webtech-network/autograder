from typing import List, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict

from autograder.core.models.test_result import TestResult



class NodeType(str, Enum):
    """Represents the types of nodes in the result tree"""
    ROOT = "root"
    CATEGORY = "category" #base, bonus, penalty 
    SUBJECT = "subject"

class ResultNode(BaseModel):
    """This class represents a node in the result tree"""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    node_type : NodeType
    name: str
    unweighted_score: Optional[float] = None
    weighted_score: Optional[float] = None
    weight: float = 0.0
    max_score: Optional[float] = None
    # Hierarchical structure 
    children: List['ResultNode'] = Field(default_factory=list)
    test_results: List[TestResult] = Field(default_factory=list)
    total_tests: int = 0

   
    def add_child(self,child: 'ResultNode'): 
        self.children.append(child)

    def get_all_tests_results(self) -> List[TestResult]:

        """Recursively get all tests results under the node"""

        results = list(self.test_results)
        for child in self.children:
            results.extend(child.get_all_tests_results())
        
        return results
    
    def find_node(self, name: str, node_type: Optional[NodeType] = None) -> Optional['ResultNode']:

        """By the name of the node, locates it in the tree.
        Returns the first matching node found."""

        if self.name == name:
            if node_type is None or self.node_type == node_type:
                return self
            
        for child in self.children: 
            result = child.find_node(name, node_type)
            if result:
                return result
            
        return None
    
    def get_node_path(self, name: str) -> Optional[List['ResultNode']]:

        """Get the path from the root to a determined node"""
        
        if self.name  == name:
            return [self]
        
        for child in self.children:
            child_path = child.get_node_path(name)
            if child_path:
                return [self] + child_path
            
        return None
    
    
    def to_dict(self) -> dict:
        """Convert the ResultNode to a dict representation"""
        return {
            "node_type": self.node_type,
            "name": self.name,
            "weighted_score": self.weighted_score,
            "unweighted_score": self.unweighted_score,
            "weight": self.weight,
            "max_score": self.max_score,
            "total_tests": self.total_tests,
            "test_results": [tr.to_dict() for tr in self.test_results],
            "children": [child.to_dict() for child in self.children]
        }
    
    def __repr__(self):
        score_info = f"weighted={self.weighted_score:.2f}" if self.weighted_score is not None else "no score"
        return f"ResultNode(type={self.node_type}, name='{self.name}', {score_info}, tests={self.total_tests})"
    



    
