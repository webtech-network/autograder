

class TestFiles:
    """
    This model is used to represent the base,bonus,penalty and fatal analysis tests, along with additional configuration files for the tests.
    """
    def __init__(self,test_base=None,test_bonus=None,test_penalty=None,fatal_tests=None,other_files=None):
        """
        Initializes the TestFiles model with the provided test files and other configuration files.

        :param test_base: The base test file.
        :param test_bonus: The bonus test file.
        :param test_penalty: The penalty test file.
        :param fatal_tests: Optional; the fatal tests file.
        :param other_files: Optional; a dictionary of other configuration files.
        """
        self.test_base = test_base
        self.test_bonus = test_bonus
        self.test_penalty = test_penalty
        self.fatal_tests = fatal_tests if fatal_tests is not None else []
        self.other_files = other_files if other_files is not None else {}
    def __str__(self):
        test_base = test_bonus = test_penalty = fatal_tests = other_files = "[Not Loaded]"
        if self.test_base:
            test_base = "[Loaded]"
        if self.test_bonus:
            test_bonus = "[Loaded]"
        if self.test_penalty:
            test_penalty = "[Loaded]"
        if self.fatal_tests:
            fatal_tests = "[Loaded]"
        if self.other_files:
            other_files = "[Loaded]"
        return f"TestFiles(test_base={test_base}, test_bonus={test_bonus}, " \
               f"test_penalty={test_penalty}, fatal_tests={fatal_tests}, " \
               f"other_files={other_files})"