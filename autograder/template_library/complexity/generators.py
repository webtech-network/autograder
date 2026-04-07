import random
from typing import Dict, Optional


class InputGenerator:
    """Generates test inputs of varying sizes for complexity benchmarking."""

    GENERATORS = {
        "random_array",
        "sorted_array",
        "sorted_array_with_queries",
        "reverse_sorted_array",
        "random_string",
        "random_pairs",
        "single_number",
        "random_matrix",
    }

    @staticmethod
    def generate(generator_name: str, size: int, input_args: Optional[Dict] = None) -> str:
        """
        Generate a test input string for the given size.

        Args:
            generator_name: Name of the generator (e.g., "random_array").
            size: The input size N.
            input_args: Optional extra arguments (min_value, max_value, etc.).

        Returns:
            A string ready to be sent as stdin to the student's program.
        """
        args = input_args or {}
        generators = {
            "random_array": InputGenerator._random_array,
            "sorted_array": InputGenerator._sorted_array,
            "reverse_sorted_array": InputGenerator._reverse_sorted_array,
            "random_string": InputGenerator._random_string,
            "random_pairs": InputGenerator._random_pairs,
            "single_number": InputGenerator._single_number,
            "random_matrix": InputGenerator._random_matrix,
        }

        gen_fn = generators.get(generator_name)
        if gen_fn is None:
            raise ValueError(
                f"Unknown input generator: '{generator_name}'. "
                f"Available: {sorted(generators.keys())}"
            )
        return gen_fn(size, **args)

    @staticmethod
    def _random_array(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        data = [random.randint(min_value, max_value) for _ in range(size)]
        return f"{size}\n{' '.join(map(str, data))}"

    @staticmethod
    def _sorted_array(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        data = sorted(random.randint(min_value, max_value) for _ in range(size))
        return f"{size}\n{' '.join(map(str, data))}"

    @staticmethod
    def _sorted_array_with_queries(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        """Generates a sorted array of size N, followed by N queries to search."""
        data = sorted(random.randint(min_value, max_value) for _ in range(size))
        queries = [random.randint(min_value, max_value) for _ in range(size)]
        return f"{size}\n{' '.join(map(str, data))}\n{' '.join(map(str, queries))}"

    @staticmethod
    def _reverse_sorted_array(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        data = sorted((random.randint(min_value, max_value) for _ in range(size)), reverse=True)
        return f"{size}\n{' '.join(map(str, data))}"

    @staticmethod
    def _random_string(size: int, **_) -> str:
        chars = "abcdefghijklmnopqrstuvwxyz"
        return "".join(random.choice(chars) for _ in range(size))

    @staticmethod
    def _random_pairs(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        lines = [str(size)]
        for _ in range(size):
            a = random.randint(min_value, max_value)
            b = random.randint(min_value, max_value)
            lines.append(f"{a} {b}")
        return "\n".join(lines)

    @staticmethod
    def _single_number(size: int, **_) -> str:
        return str(size)

    @staticmethod
    def _random_matrix(size: int, min_value: int = 1, max_value: int = 1_000_000, **_) -> str:
        lines = [str(size)]
        for _ in range(size):
            row = [random.randint(min_value, max_value) for _ in range(size)]
            lines.append(" ".join(map(str, row)))
        return "\n".join(lines)
