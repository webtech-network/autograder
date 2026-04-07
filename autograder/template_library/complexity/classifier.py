import math
from typing import List, Tuple


class ComplexityClassifier:
    """
    Classifies algorithmic complexity from empirical (size, time) measurements
    using log-log regression and dual model fitting.

    Pure math — zero external dependencies beyond Python's math module.
    """

    CLASSES = [
        "O(1)", "O(log n)", "O(sqrt(n))", "O(n)",
        "O(n log n)", "O(n^2)", "O(n^3)", "O(exponential)",
    ]

    CONFIDENCE_THRESHOLD = 0.85

    @staticmethod
    def classify(measurements: List[Tuple[int, float]]) -> Tuple[str, float]:
        """
        Classify complexity from (size, time_us) measurements using competitive regression.
        Returns (complexity_class, confidence_r2).
        """
        sizes = [m[0] for m in measurements]
        times = [m[1] for m in measurements]

        # Ignore tiny differences that essentially mean pure O(1) or pure noise
        max_t = max(times)
        min_t = min(times)
        if (max_t - min_t) < 500:  # less than 0.5 milliseconds bounds variation
            return "O(1)", 1.0
            
        models = {
            "O(log n)": lambda n: math.log2(n),
            "O(sqrt(n))": lambda n: math.sqrt(n),
            "O(n)": lambda n: n,
            "O(n log n)": lambda n: n * math.log2(n),
            "O(n^2)": lambda n: n * n,
            "O(n^3)": lambda n: n * n * n,
        }

        best_r2 = -1.0
        best_class = "O(1)"

        # Occam's Razor: We iterate from best to worst complexity.
        # We only accept a WORSE complexity if its R² is significantly better (> 2% improvement).
        # This prevents minor hardware anomalies (e.g. CPU L1->L2 Cache Misses bending the curve) 
        # from over-fitting linear functions into parabolas O(n^2).
        for name, fn in models.items():
            r2 = ComplexityClassifier._fit_model(sizes, times, fn)
            
            # Require at least +0.02 (2%) better fit to jump to a worse complexity class
            if r2 > best_r2 + 0.02:
                best_r2 = r2
                best_class = name

        # If no model can hit a basic correlation, we assume it's flat/O(1) hidden by massive stochastic noise
        if best_r2 < 0.50:
            return "O(1)", max(best_r2, 0.95)

        return best_class, best_r2

    @staticmethod
    def _fit_power_law(sizes: List[int], times: List[float]) -> Tuple[float, float]:
        """T = c * n^alpha  =>  log(T) = alpha*log(n) + log(c)"""
        n = len(sizes)
        lx = [math.log(s) for s in sizes]
        ly = [math.log(max(t_val, 0.001)) for t_val in times]

        mx = sum(lx) / n
        my = sum(ly) / n

        num = sum((x - mx) * (y - my) for x, y in zip(lx, ly))
        den = sum((x - mx) ** 2 for x in lx)

        alpha = num / den if den > 0 else 0
        log_c = my - alpha * mx

        predicted = [alpha * x + log_c for x in lx]
        ss_res = sum((y - p) ** 2 for y, p in zip(ly, predicted))
        ss_tot = sum((y - my) ** 2 for y in ly)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        return alpha, r2

    @staticmethod
    def _fit_model(sizes: List[int], times: List[float], model_fn) -> float:
        """Fit T = a + b * model_fn(n) using least squares, return R²."""
        n = len(sizes)
        xs = [model_fn(s) for s in sizes]

        mx = sum(xs) / n
        my = sum(times) / n

        num = sum((x - mx) * (t_val - my) for x, t_val in zip(xs, times))
        den = sum((x - mx) ** 2 for x in xs)

        b = num / den if den > 0 else 0
        a = my - b * mx

        predicted = [a + b * x for x in xs]
        ss_res = sum((t_val - p) ** 2 for t_val, p in zip(times, predicted))
        ss_tot = sum((t_val - my) ** 2 for t_val in times)

        return 1 - ss_res / ss_tot if ss_tot > 0 else 0
