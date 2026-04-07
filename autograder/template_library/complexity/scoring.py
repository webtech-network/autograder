from typing import Dict, Optional


class ComplexityScorer:
    """Computes a grade based on detected vs expected complexity."""

    # Ordered from most efficient to least
    CLASS_ORDER = [
        "O(1)", "O(log n)", "O(sqrt(n))", "O(n)",
        "O(n log n)", "O(n^2)", "O(n^3)", "O(exponential)",
    ]

    DEFAULT_GRADUATED_PENALTIES = {
        0: 100,   # equal or better
        1: 80,    # 1 class above
        2: 60,    # 2 classes above
        3: 30,    # 3 classes above
    }
    DEFAULT_GRADUATED_FLOOR = 0  # 4+ classes above

    @staticmethod
    def score(
        detected: str,
        expected: str,
        scoring: str,
        score_table: Optional[Dict[str, int]] = None,
    ) -> float:
        if scoring == "strict":
            return ComplexityScorer._score_strict(detected, expected)
        elif scoring == "graduated":
            return ComplexityScorer._score_graduated(detected, expected)
        elif scoring == "custom":
            return ComplexityScorer._score_custom(detected, expected, score_table or {})
        else:
            raise ValueError(f"Unknown scoring mode: '{scoring}'")

    @staticmethod
    def _class_index(complexity: str) -> int:
        try:
            return ComplexityScorer.CLASS_ORDER.index(complexity)
        except ValueError:
            return len(ComplexityScorer.CLASS_ORDER)

    @staticmethod
    def _score_strict(detected: str, expected: str) -> float:
        detected_idx = ComplexityScorer._class_index(detected)
        expected_idx = ComplexityScorer._class_index(expected)
        return 100.0 if detected_idx <= expected_idx else 0.0

    @staticmethod
    def _score_graduated(detected: str, expected: str) -> float:
        detected_idx = ComplexityScorer._class_index(detected)
        expected_idx = ComplexityScorer._class_index(expected)
        distance = detected_idx - expected_idx
        if distance <= 0:
            return 100.0
        return float(
            ComplexityScorer.DEFAULT_GRADUATED_PENALTIES.get(
                distance, ComplexityScorer.DEFAULT_GRADUATED_FLOOR
            )
        )

    @staticmethod
    def _score_custom(detected: str, expected: str, score_table: Dict[str, int]) -> float:
        if detected in score_table:
            return float(score_table[detected])
        # If not in table, treat equal-or-better as 100, else 0
        detected_idx = ComplexityScorer._class_index(detected)
        expected_idx = ComplexityScorer._class_index(expected)
        return 100.0 if detected_idx <= expected_idx else 0.0
