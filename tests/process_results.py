"""ProcessResult builders for tests that fake an execution session."""
from autograder.models.process import ProcessResult, ProcessStatus


def exited(stdout="", stderr="", code=0, duration=0.01):
    return ProcessResult(ProcessStatus.EXITED, code, stdout, stderr, duration=duration)


def timed_out(stdout="", stderr="", duration=30):
    return ProcessResult(ProcessStatus.TIMED_OUT, None, stdout, stderr, duration=duration)


def not_started(executable="missing"):
    return ProcessResult(ProcessStatus.NOT_STARTED, missing_executable=executable)
