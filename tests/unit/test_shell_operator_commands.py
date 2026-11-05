"""Argv commands written for a shell fail compilation at their exact path (ONB-01).

Commands are split without a shell (ARC-08), so a standalone ``&&``, ``|`` or
``>`` would silently become an argument and fail every submission.
"""
# Test names state each checked behaviour.
# pylint: disable=missing-function-docstring
import pytest

from autograder import DefinitionValidationError, compile_definition
from autograder.models import process

TEST = ["criteria", "base", "tests", 0, "parameters"]


def definition(program_command="python3 main.py", setup=(), languages=("python",)):
    value = {"schema_version": "1.0", "templates": ["input_output"], "languages": list(languages),
             "criteria": {"base": {"weight": 100, "tests": [{
                 "id": "run", "type": "dont_fail", "name": "Runs", "weight": 100,
                 "parameters": {"program_command": program_command}}]}}}
    if setup:
        value["preparation"] = {"languages": {languages[0]: {"setup_commands": [
            {"name": f"step {index}", "command": command} for index, command in enumerate(setup)]}}}
    return value


def errors(value):
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(value)
    return [(error["code"], error["path"]) for error in failure.value.errors()]


@pytest.mark.parametrize("command,operator", [
    ("javac Sum.java && java Sum", "&&"),
    ("python3 main.py || true", "||"),
    ("python3 main.py | tr a-z A-Z", "|"),
    ("python3 main.py ; echo done", ";"),
    ("python3 main.py > out.txt", ">"),
    ("python3 main.py >> out.txt", ">>"),
    ("python3 main.py < input.txt", "<"),
    ("python3 main.py 2> /dev/null", "2>"),
    ("python3 main.py 2>&1", "2>&1"),
    ("python3 server.py &", "&"),
])
def test_standalone_shell_operators_are_detected(command, operator):
    assert process.shell_operator(command) == operator


@pytest.mark.parametrize("command", [
    "python3 main.py",
    "python3 main.py '&&' \"|\" '>'",           # quoted operators are literal arguments
    "python3 main.py \\&\\& \\|",               # so are escaped ones
    "sh -c 'javac Sum.java && java Sum | tee log'",
    "sh -c \"python3 main.py > out.txt 2>&1\"",
    "python3 -c \"print('a && b | c; d > e')\"",
    "grep -E 'a|b' data.txt",
    "node index.js --mode=a->b 5",
])
def test_quoted_and_ordinary_words_are_not_operators(command):
    assert process.shell_operator(command) is None


def test_malformed_quoting_is_left_to_the_quoting_check():
    with pytest.raises(ValueError):
        process.shell_operator("python3 'main.py && x")


@pytest.mark.parametrize("value,expected", [
    (definition("javac Sum.java && java Sum", languages=("java",)),
     [("SHELL_OPERATOR", [*TEST, "program_command"])]),
    (definition({"python": "python3 main.py", "java": "java Sum > out.txt"}, languages=("python", "java")),
     [("SHELL_OPERATOR", [*TEST, "program_command", "java"])]),
    (definition("java Sum", setup=("javac Sum.java", "javac A.java && javac B.java"), languages=("java",)),
     [("SHELL_OPERATOR", ["preparation", "languages", "java", "setup_commands", 1, "command"])]),
    (definition("python3 main.py | sort", setup=("pip install x ; true",)),
     [("SHELL_OPERATOR", [*TEST, "program_command"]),
      ("SHELL_OPERATOR", ["preparation", "languages", "python", "setup_commands", 0, "command"])]),
])
def test_operator_fails_compilation_at_the_exact_path(value, expected):
    assert errors(value) == expected


def test_error_steers_compilation_to_setup_commands_and_pipelines_to_sh_c():
    with pytest.raises(DefinitionValidationError) as failure:
        compile_definition(definition("javac Sum.java && java Sum", languages=("java",)))
    message = failure.value.errors()[0]["message"]
    assert "`&&`" in message and "preparation.setup_commands" in message and "sh -c" in message


@pytest.mark.parametrize("value", [
    definition("java Sum", setup=("javac Sum.java",), languages=("java",)),
    definition("sh -c 'python3 main.py | sort'"),
    definition({"python": "python3 main.py '>'", "java": "sh -c 'java Sum 2>&1'"}, languages=("python", "java")),
    definition("CMD", setup=("sh -c 'python3 gen.py > data.txt'",)),
])
def test_quoted_operators_and_explicit_shells_compile(value):
    compile_definition(value)


def test_malformed_quoting_keeps_its_own_code():
    assert errors(definition("python3 'main.py && x")) == [("INVALID_COMMAND", [*TEST, "program_command"])]
