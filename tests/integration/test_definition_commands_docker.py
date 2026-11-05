"""Definition commands in real containers: compile in setup, pipe only through sh -c (ONB-01).

Commands run without a shell, so the pre-ARC-08 habit ``javac Sum.java && java Sum``
used to compile and then fail a correct solution with ``javac: invalid flag: &&``.
It is now rejected at compilation, before any sandbox is acquired.
"""
# Test names state each checked behaviour.
# pylint: disable=missing-function-docstring
from dataclasses import replace

import pytest

from autograder import DefinitionValidationError, Submission, SubmissionFile, build_pipeline, evaluate_submission
from autograder.models.language import Language
from execution_host.docker import DockerHost
from tests.sandbox_profiles import sandbox_config

SUM_JAVA = """import java.util.Scanner;

public class Sum {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);
        System.out.println(in.nextInt() + in.nextInt());
    }
}
"""
FILES = {
    "Sum.java": SUM_JAVA,
    "main.py": "print('hello from python')\n",
    "args.py": "import sys\nprint(' '.join(sys.argv[1:]))\n",
}


def definition(language, tests, setup=()):
    value = {"schema_version": "1.0", "templates": ["input_output"], "languages": [language],
             "criteria": {"base": {"weight": 100, "tests": tests}}}
    if setup:
        value["preparation"] = {"languages": {language: {"setup_commands": [
            {"name": f"step {index}", "command": command} for index, command in enumerate(setup)]}}}
    return value


def expect(test_id, command, expected, inputs=()):
    return {"id": test_id, "type": "expect_output", "name": test_id, "parameters": {
        "program_command": command, "inputs": list(inputs), "expected_output": expected}}


def submission(language, *names):
    return Submission("s", "s", "a", {name: SubmissionFile(name, FILES[name]) for name in names},
                      language=language)


@pytest.fixture(scope="module")
def docker_host(tmp_path_factory):
    config = tmp_path_factory.mktemp("host") / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON, Language.JAVA)))
    host = DockerHost(mode="local", config_file=str(config))
    yield host
    host.close()


def test_correct_java_compiled_in_setup_commands_scores_100(docker_host):
    value = definition("java", [expect("sum", "java Sum", "5", ["2", "3"]),
                                expect("negative", "java Sum", "-1", ["2", "-3"])], setup=("javac Sum.java",))
    outcome = build_pipeline(definition=value, capabilities=docker_host.capabilities).run(
        submission(Language.JAVA, "Sum.java")).outcome
    assert outcome.status == "completed", outcome.error
    assert outcome.score == 100, [test.report for test in outcome.tree.base.tests]


def test_explicit_shell_pipeline_and_quoted_operators_grade(docker_host):
    value = definition("python", [
        expect("pipeline", "sh -c 'python3 main.py | tr a-z A-Z'", "HELLO FROM PYTHON"),
        expect("quoted", "python3 args.py '&&' \"|\" \\>", "&& | >"),
    ], setup=("sh -c 'python3 main.py > generated.txt'",))
    outcome = build_pipeline(definition=value, capabilities=docker_host.capabilities).run(
        submission(Language.PYTHON, "main.py", "args.py")).outcome
    assert outcome.status == "completed", outcome.error
    assert {test.id: test.score for test in outcome.tree.base.tests} == {"pipeline": 100, "quoted": 100}


@pytest.mark.parametrize("value,path", [
    (definition("java", [expect("sum", "javac Sum.java && java Sum", "5", ["2", "3"])]),
     ["criteria", "base", "tests", 0, "parameters", "program_command"]),
    (definition("java", [expect("sum", {"java": "java Sum | cat"}, "5", ["2", "3"])], setup=("javac Sum.java",)),
     ["criteria", "base", "tests", 0, "parameters", "program_command", "java"]),
    (definition("java", [expect("sum", "java Sum", "5", ["2", "3"])], setup=("javac Sum.java ; true",)),
     ["preparation", "languages", "java", "setup_commands", 0, "command"]),
])
def test_operator_form_is_rejected_before_any_sandbox_is_acquired(tmp_path, value, path):
    config = tmp_path / "sandbox.yml"
    config.write_text(sandbox_config((Language.JAVA,)))
    host = DockerHost(mode="local", config_file=str(config))
    acquired = []

    def execution(language):
        acquired.append(language)
        return host.capabilities.execution(language)

    capabilities = replace(host.capabilities, execution=execution)
    try:
        for run in (lambda: build_pipeline(definition=value, capabilities=capabilities),
                    lambda: evaluate_submission(submission(Language.JAVA, "Sum.java"), definition=value,
                                                capabilities=capabilities)):
            with pytest.raises(DefinitionValidationError) as failure:
                run()
            assert [(error["code"], error["path"]) for error in failure.value.errors()] == [("SHELL_OPERATOR", path)]
        assert not acquired
        assert host._manager is None  # pylint: disable=protected-access  # no sandbox manager was ever started
    finally:
        host.close()
