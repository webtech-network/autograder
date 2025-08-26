from typing import List


class Root:
    """Root node of a criteria tree."""
    def __init__(self):
        pass

class Category:
    """First childs of the root node, representing major categories.(base,bonus,penalty)"""
    def __init__(self,category_name:str):
        self.category_name = category_name
        pass

class Subject:
    """Childs of Category nodes, representing subjects within a category."""
    def __init__(self,subject_name:str,subject_weight:int):
        self.subject_name = subject_name
        self.subject_weight = subject_weight
        pass

class Test:
    """Leaf nodes of the tree, representing individual tests."""
    def __init__(self,test_name:str,test_weight:int):
        self.test_name = test_name
        self.test_calls: List[TestCall] = []
        pass

class TestCall:
    def __init__(self,args):
        self.args = args
        pass