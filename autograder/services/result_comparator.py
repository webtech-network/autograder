from typing import Dict, List
from autograder.models.result_tree import ResultTree, TestResultNode
from autograder.models.dataclass.comparison_result import ComparisonResult, TestDelta


class ResultComparator:
    """
    Stateless utility service that compares two ResultTree objects (baseline vs head)
    and computes a structured ComparisonResult containing overall score deltas
    and per-test status transitions.
    """

    @staticmethod
    def compare(
        baseline: ResultTree,
        head: ResultTree,
    ) -> ComparisonResult:
        """
        Compare a baseline ResultTree with a head ResultTree.

        Args:
            baseline: The baseline ResultTree (reference run).
            head: The head ResultTree (current run).

        Returns:
            ComparisonResult containing score_delta, improved flag, and test_deltas.
        """
        baseline_map: Dict[str, TestResultNode] = dict(baseline.iter_test_results())
        head_map: Dict[str, TestResultNode] = dict(head.iter_test_results())

        # Calculate overall final score delta
        score_delta = round(head.root.score - baseline.root.score, 2)
        improved = score_delta > 0

        # Preserve traversal order of head, then append removed paths from baseline
        all_paths: List[str] = list(head_map.keys())
        for path in baseline_map.keys():
            if path not in head_map:
                all_paths.append(path)

        test_deltas: List[TestDelta] = []
        for path in all_paths:
            in_head = path in head_map
            in_baseline = path in baseline_map

            if in_head and in_baseline:
                base_score = baseline_map[path].score
                head_score = head_map[path].score
                delta = round(head_score - base_score, 2)

                if delta > 0:
                    status = "improved"
                elif delta < 0:
                    status = "regressed"
                else:
                    status = "unchanged"

                test_deltas.append(
                    TestDelta(
                        path=path,
                        status=status,
                        baseline_score=base_score,
                        head_score=head_score,
                        delta=delta,
                    )
                )
            elif in_head:
                head_score = head_map[path].score
                test_deltas.append(
                    TestDelta(
                        path=path,
                        status="introduced",
                        baseline_score=None,
                        head_score=head_score,
                        delta=None,
                    )
                )
            else:
                base_score = baseline_map[path].score
                test_deltas.append(
                    TestDelta(
                        path=path,
                        status="removed",
                        baseline_score=base_score,
                        head_score=None,
                        delta=None,
                    )
                )

        return ComparisonResult(
            score_delta=score_delta,
            improved=improved,
            test_deltas=test_deltas,
        )
