This guide explains the fundamental principles of the WebTech Autograder, including how it evaluates student submissions and how the grading criteria are structured. Understanding these concepts is key to effectively creating and managing your assignments.

## The Grading Process

The autograder evaluates a student's submission by running three distinct test suites, each with a specific purpose:

* **Base Tests**: These tests check for the **mandatory requirements** of an assignment. A student's submission must pass these tests to meet the minimum criteria for the assignment. The base score is the foundation of the final grade.

* **Bonus Tests**: These tests check for **optional features or extra credit**. Passing these tests adds points to the student's score, allowing them to improve their grade by going above and beyond the basic requirements.

* **Penalty Tests**: These tests check for things that are **explicitly forbidden** in the assignment, such as the use of deprecated HTML tags or incorrect coding practices. If a submission passes a penalty test, points are deducted from the final score.

This three-tiered approach provides a flexible and comprehensive way to assess student work, rewarding both core competency and extra effort while discouraging bad practices.

## How Grading Criteria is Managed

The autograder uses a hierarchical, tree-like structure to manage grading criteria, making the process transparent, organized, and highly customizable. This entire structure is defined in the `criteria.json` file.

### The Grading Artifacts Tree

The grading configuration and test artifacts are organized into a logical tree with four levels:

* **Level 1 (Root): `criteria.json`**
  The entire configuration file acts as the root of the tree.

* **Level 2: Test Categories**
  The root has exactly three children, representing the test file categories: `base`, `bonus`, and `penalty`.

* **Level 3: Subjects**
  Each test category contains one or more **subjects** (e.g., `html`, `css`, `javascript`, `api-endpoints`). You can define as many subjects as you need for your assignment.

* **Level 4 (Leaves): Unit Tests**
  Each subject contains the actual **unit tests** (the test functions defined in your test files).

This structure ensures that every test is mapped to a specific subject and category, allowing you to assign weights and customize the grading logic with precision.

### Visualizing the Tree Structure

Here is a diagram illustrating the grading tree:

![Grading Artifacts Tree](/imgs/tree_structure.png)

By understanding this structure, you can create sophisticated and well-organized grading schemes for any assignment.
