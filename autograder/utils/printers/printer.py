from typing import List


class Printer:
    def __init__(self) -> None:
        self.__depth = 0

    def print(self, formatted: str) -> None:
        print(f"{'    ' * self.__depth}{formatted}")

    def print_lines(self, lines: List[str]) -> None:
        prefix = "    " * self.__depth
        for line in lines:
            print(f"{prefix}{line}")

    def increase_depth(self) -> None:
        self.__depth += 1

    def decrease_depth(self) -> None:
        self.__depth -= 1
