
class TestResult:
    def __init__(self, test_name: str, score: int, message: str = ""):
        self.test_name = test_name
        self.score = score
        self.message = message

    def __repr__(self):
        return f"<TestResult {self.test_name}: score->{self.score} - {self.message}>"