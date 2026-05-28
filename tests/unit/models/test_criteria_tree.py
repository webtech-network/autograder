import pytest
from unittest.mock import MagicMock
from autograder.models.criteria_tree import TestNode, SubjectNode, CategoryNode, CriteriaTree
from autograder.models.abstract.test_function import TestFunction

def create_mock_test_function():
    tf = MagicMock(spec=TestFunction)
    tf.name = "mock_test"
    return tf

def test_test_node_repr():
    tf = create_mock_test_function()
    node = TestNode(name="my_test", test_function=tf)
    assert repr(node) == "TestNode(my_test)"

    node_with_params = TestNode(name="my_test", test_function=tf, parameters={"p": 1})
    assert repr(node_with_params) == "TestNode(my_test, params={'p': 1})"

    node_with_file = TestNode(name="my_test", test_function=tf, file_target=["test.py"])
    assert repr(node_with_file) == "TestNode(my_test, file=['test.py'])"

    node_with_both = TestNode(name="my_test", test_function=tf, parameters={"p": 1}, file_target=["test.py"])
    assert repr(node_with_both) == "TestNode(my_test, params={'p': 1}, file=['test.py'])"

def test_subject_node_repr():
    tf = create_mock_test_function()
    test_node = TestNode(name="test", test_function=tf)
    subject_with_tests = SubjectNode(name="subject1", weight=50.0, tests=[test_node])
    assert repr(subject_with_tests) == "SubjectNode(subject1, weight=50.0, tests=1)"

    subject_with_subjects = SubjectNode(name="subject2", weight=100.0, subjects=[subject_with_tests])
    assert repr(subject_with_subjects) == "SubjectNode(subject2, weight=100.0, subjects=1)"

def test_category_node_repr():
    tf = create_mock_test_function()
    test_node = TestNode(name="test", test_function=tf)
    category_with_tests = CategoryNode(name="cat1", weight=100.0, tests=[test_node])
    assert repr(category_with_tests) == "CategoryNode(cat1, weight=100.0, tests=1)"

    subject_node = SubjectNode(name="subj1", weight=100.0, tests=[test_node])
    category_with_subjects = CategoryNode(name="cat2", weight=100.0, subjects=[subject_node])
    assert repr(category_with_subjects) == "CategoryNode(cat2, weight=100.0, subjects=1)"

def test_criteria_tree_repr():
    base = CategoryNode(name="base", weight=100.0)
    bonus = CategoryNode(name="bonus", weight=10.0)
    penalty = CategoryNode(name="penalty", weight=10.0)

    tree_base_only = CriteriaTree(base=base)
    assert repr(tree_base_only) == "CriteriaTree(categories=['base'])"

    tree_bonus = CriteriaTree(base=base, bonus=bonus)
    assert "bonus" in repr(tree_bonus)
    assert repr(tree_bonus) == "CriteriaTree(categories=['base', 'bonus'])"

    tree_full = CriteriaTree(base=base, bonus=bonus, penalty=penalty)
    assert repr(tree_full) == "CriteriaTree(categories=['base', 'bonus', 'penalty'])"

def test_subject_get_all_tests_recursive():
    tf = create_mock_test_function()
    
    t1 = TestNode(name="t1", test_function=tf)
    t2 = TestNode(name="t2", test_function=tf)
    t3 = TestNode(name="t3", test_function=tf)
    
    # Sub 2 has t3
    sub2 = SubjectNode(name="sub2", weight=50.0, tests=[t3])
    
    # Sub 1 has t2 and contains sub2
    sub1 = SubjectNode(name="sub1", weight=100.0, tests=[t2], subjects=[sub2])
    
    # Base subject has t1 and contains sub1
    base_sub = SubjectNode(name="base_sub", weight=100.0, tests=[t1], subjects=[sub1])
    
    tests = base_sub.get_all_tests()
    assert len(tests) == 3
    assert tests[0].name == "t1"
    assert tests[1].name == "t2"
    assert tests[2].name == "t3"

def test_category_get_all_tests_recursive():
    tf = create_mock_test_function()
    
    t1 = TestNode(name="t1", test_function=tf)
    t2 = TestNode(name="t2", test_function=tf)
    t3 = TestNode(name="t3", test_function=tf)
    t4 = TestNode(name="t4", test_function=tf)
    
    sub2 = SubjectNode(name="sub2", weight=50.0, tests=[t4])
    sub1 = SubjectNode(name="sub1", weight=100.0, tests=[t3], subjects=[sub2])
    
    cat = CategoryNode(name="cat", weight=100.0, tests=[t1, t2])
    cat.add_subjects([sub1])
    
    tests = cat.get_all_tests()
    assert len(tests) == 4
    names = [t.name for t in tests]
    assert names == ["t1", "t2", "t3", "t4"]

def test_category_get_all_tests_no_tests():
    cat = CategoryNode(name="empty", weight=100.0)
    assert cat.get_all_tests() == []
