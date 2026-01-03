"""
Models for the Result Tree - represents executed grading results.
The result tree mirrors the criteria structure but contains actual execution results.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class NodeType(Enum):
    """Types of nodes in the result tree."""
    CATEGORY = "category"
    SUBJECT = "subject"
    TEST = "test"


@dataclass
class ResultNode:
    """
    Base node for the result tree.

    Represents a grading category or subject with a calculated score
    based on its children's scores and weights.
    """
    name: str
    node_type: NodeType
    weight: float
    score: float = 0.0
    max_possible: float = 100.0
    children: List['ResultNode'] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_score(self) -> float:
        """
        Calculate this node's score based on children.
        For leaf nodes (tests), score is already set.
        For parent nodes, calculate weighted average of children.

        Special case: ROOT node with BASE/BONUS/PENALTY uses additive scoring:
        - Base score (0-100)
        - Bonus adds points (bonus_score * bonus_weight / 100)
        - Penalty subtracts points (penalty_score * penalty_weight / 100)
        """
        if self.node_type == NodeType.TEST:
            # Leaf node - score already set from test execution
            return self.score

        if not self.children:
            return 0.0

        # Calculate children scores first
        for child in self.children:
            child.calculate_score()

        # Check if this is a ROOT node with BASE/BONUS/PENALTY categories
        child_names = {c.name.lower() for c in self.children}
        is_root_with_categories = (
            self.name.lower() == "root" and
            "base" in child_names
        )

        if is_root_with_categories:
            # Additive scoring for BASE/BONUS/PENALTY
            base_score = 0.0
            bonus_points = 0.0
            penalty_points = 0.0

            for child in self.children:
                child_name = child.name.lower()
                if child_name == "base":
                    base_score = child.score
                elif child_name == "bonus":
                    # Bonus adds: (bonus_score / 100) * bonus_weight
                    bonus_points = (child.score / 100.0) * child.weight
                elif child_name == "penalty":
                    # Penalty subtracts: (penalty_score / 100) * penalty_weight
                    penalty_points = (child.score / 100.0) * child.weight

            # Final score = base + bonus - penalty (capped at 0-100)
            self.score = max(0.0, min(100.0, base_score + bonus_points - penalty_points))
        else:
            # Standard weighted average for other nodes
            total_weight = sum(c.weight for c in self.children)
            if total_weight == 0:
                return 0.0

            weighted_sum = sum(c.score * c.weight for c in self.children)
            self.score = weighted_sum / total_weight

        return self.score

    def to_dict(self) -> dict:
        """Convert result node to dictionary representation."""
        return {
            "name": self.name,
            "type": self.node_type.value,
            "weight": self.weight,
            "score": round(self.score, 2),
            "max_possible": self.max_possible,
            "children": [child.to_dict() for child in self.children],
            "metadata": self.metadata
        }


@dataclass
class TestResultNode(ResultNode):
    """
    Leaf node representing a single test execution.

    Contains the actual test result and execution details.
    """
    test_name: str = ""
    test_function: Any = None  # Reference to the actual test function
    test_params: List[Any] = field(default_factory=list)
    file_target: Optional[str] = None
    execution_result: Optional[Any] = None  # TestResult object after execution
    error_message: Optional[str] = None
    passed: bool = False

    def __post_init__(self):
        """Set node type to TEST."""
        self.node_type = NodeType.TEST

    def execute(self, submission_files: Dict[str, Any]) -> float:
        """
        Execute the test function with provided parameters.
        Updates score, passed status, and execution_result.

        Returns:
            The test score (0-100)
        """
        if not self.test_function:
            self.error_message = "No test function assigned"
            self.score = 0.0
            self.passed = False
            return 0.0

        try:
            # Execute the test function
            # The test function should return a TestResult object
            self.execution_result = self.test_function.execute(
                *self.test_params,
                files=submission_files
            )

            # Extract score from result
            if hasattr(self.execution_result, 'score'):
                self.score = float(self.execution_result.score)
            else:
                self.score = 100.0 if self.execution_result else 0.0

            # Check if test passed (score >= 50 is considered passing)
            self.passed = self.score >= 50

            # Store result report/message
            if hasattr(self.execution_result, 'report'):
                self.metadata['report'] = self.execution_result.report
            elif hasattr(self.execution_result, 'message'):
                self.metadata['message'] = self.execution_result.message

            return self.score

        except Exception as e:
            self.error_message = f"Test execution failed: {str(e)}"
            self.score = 0.0
            self.passed = False
            self.metadata['error'] = str(e)
            return 0.0

    def to_dict(self) -> dict:
        """Convert test result node to dictionary with execution details."""
        base_dict = super().to_dict()
        base_dict.update({
            "test_name": self.test_name,
            "file_target": self.file_target,
            "passed": self.passed,
            "error_message": self.error_message,
            "params": self.test_params
        })
        return base_dict


@dataclass
class ResultTree:
    """
    Complete result tree for a grading session.

    Contains the root node and provides methods for score calculation
    and tree traversal.
    """
    root: ResultNode
    submission_id: Optional[str] = None
    template_name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_final_score(self) -> float:
        """
        Calculate and return the final score by traversing the tree.

        Returns:
            Final score (0-100)
        """
        return self.root.calculate_score()

    def get_all_test_results(self) -> List[TestResultNode]:
        """Get all test result nodes from the tree."""
        results = []
        self._collect_tests(self.root, results)
        return results

    def _collect_tests(self, node: ResultNode, collector: List[TestResultNode]):
        """Recursively collect all test nodes."""
        if isinstance(node, TestResultNode):
            collector.append(node)
        else:
            for child in node.children:
                self._collect_tests(child, collector)

    def get_failed_tests(self) -> List[TestResultNode]:
        """Get all failed test nodes."""
        return [test for test in self.get_all_test_results() if not test.passed]

    def get_passed_tests(self) -> List[TestResultNode]:
        """Get all passed test nodes."""
        return [test for test in self.get_all_test_results() if test.passed]

    def to_dict(self) -> dict:
        """Convert entire result tree to dictionary."""
        return {
            "submission_id": self.submission_id,
            "template_name": self.template_name,
            "final_score": round(self.root.score, 2),
            "tree": self.root.to_dict(),
            "metadata": self.metadata,
            "summary": {
                "total_tests": len(self.get_all_test_results()),
                "passed_tests": len(self.get_passed_tests()),
                "failed_tests": len(self.get_failed_tests())
            }
        }

    def print_tree(self, show_details: bool = True):
        """
        Print a visual representation of the result tree.

        Args:
            show_details: If True, show test parameters and error messages
        """
        print("\n" + "=" * 70)
        print("🎯 RESULT TREE")
        print("=" * 70)

        # Print header info
        if self.submission_id:
            print(f"📝 Submission: {self.submission_id}")
        if self.template_name:
            print(f"📋 Template: {self.template_name}")

        print(f"🏆 Final Score: {self.root.score:.2f}/100")

        summary = {
            "total": len(self.get_all_test_results()),
            "passed": len(self.get_passed_tests()),
            "failed": len(self.get_failed_tests())
        }
        print(f"📊 Tests: {summary['total']} total | "
              f"✅ {summary['passed']} passed | "
              f"❌ {summary['failed']} failed")

        print("\n" + "-" * 70)

        # Print tree structure
        self._print_node(self.root, "", show_details)

        print("=" * 70 + "\n")

    def _print_node(self, node: ResultNode, prefix: str, show_details: bool):
        """Recursively print a node and its children."""
        if isinstance(node, TestResultNode):
            self._print_test_node(node, prefix, show_details)
        else:
            self._print_parent_node(node, prefix, show_details)

    def _print_parent_node(self, node: ResultNode, prefix: str, show_details: bool):
        """Print a category or subject node."""
        # Choose icon based on node type
        if node.node_type == NodeType.CATEGORY:
            icon = "📁"
            name = node.name.upper()
        else:  # SUBJECT
            icon = "📘"
            name = node.name

        # Color code score
        score_str = f"{node.score:.1f}"
        if node.score >= 80:
            score_color = "🟢"
        elif node.score >= 60:
            score_color = "🟡"
        else:
            score_color = "🔴"

        print(f"{prefix}{icon} {name} "
              f"[weight: {node.weight:.0f}%] "
              f"{score_color} {score_str}/100")

        # Print children
        for child in node.children:
            self._print_node(child, prefix + "    ", show_details)

    def _print_test_node(self, node: TestResultNode, prefix: str, show_details: bool):
        """Print a test result node."""
        # Status icon
        status = "✅" if node.passed else "❌"

        # Score with color
        if node.score >= 80:
            score_color = "🟢"
        elif node.score >= 60:
            score_color = "🟡"
        else:
            score_color = "🔴"

        # Basic test info
        test_info = f"{prefix}🧪 {node.test_name} {status}"

        # Add file target if present
        if node.file_target:
            test_info += f" [file: {node.file_target}]"

        # Add score
        test_info += f" {score_color} {node.score:.1f}/100"

        print(test_info)

        # Show details if requested
        if show_details:
            # Show parameters
            if node.test_params:
                params_str = ", ".join(str(p) for p in node.test_params)
                print(f"{prefix}    ⚙️  params: ({params_str})")

            # Show error message if failed
            if node.error_message:
                print(f"{prefix}    ⚠️  error: {node.error_message}")

            # Show metadata report/message
            if 'report' in node.metadata:
                report = node.metadata['report']
                # Truncate long reports
                if len(report) > 80:
                    report = report[:77] + "..."
                print(f"{prefix}    💬 {report}")

    def print_summary(self):
        """Print a compact summary of the results."""
        print("\n" + "=" * 70)
        print("📊 GRADING SUMMARY")
        print("=" * 70)

        if self.submission_id:
            print(f"Submission: {self.submission_id}")

        print(f"\n🏆 Final Score: {self.root.score:.2f}/100")

        # Test statistics
        all_tests = self.get_all_test_results()
        passed = self.get_passed_tests()
        failed = self.get_failed_tests()

        print(f"\n📈 Test Results:")
        print(f"   Total:  {len(all_tests)}")
        print(f"   ✅ Passed: {len(passed)} ({len(passed)/len(all_tests)*100:.1f}%)")
        print(f"   ❌ Failed: {len(failed)} ({len(failed)/len(all_tests)*100:.1f}%)")

        # Score distribution
        if all_tests:
            avg_score = sum(t.score for t in all_tests) / len(all_tests)
            print(f"\n📊 Average Test Score: {avg_score:.2f}")

        # Show failed tests if any
        if failed:
            print(f"\n❌ Failed Tests:")
            for test in failed:
                print(f"   • {test.test_name}: {test.score:.1f}/100")
                if test.error_message:
                    print(f"     Error: {test.error_message}")

        print("=" * 70 + "\n")


