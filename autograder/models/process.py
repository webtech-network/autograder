"""The one process contract shared by every execution backend and consumer.

A :class:`ProcessRequest` states exactly what runs: an argument vector
(``argv``, never interpreted by a shell) or an explicit trusted shell script
(``shell``, run as ``/bin/sh -c <script>``), the exact ``stdin`` bytes, the
working directory and a process deadline. A :class:`ProcessResult` reports what
happened to a process that the backend ran: it exited with a code, it was
stopped at its deadline, or it could not be started. Anything else (transport,
provisioning, an invalidated sandbox, failed output readback) is raised as an
exception by the backend and is never a student result.

Preparation, the I/O and artifact evaluators and deliberate execution all use
``ExecutionSession.run_process`` with this contract; they differ only in how
they grade or report the result.
"""
import posixpath
import re
import shlex
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence, Tuple

#: Bounds of one request; hosts may enforce lower limits.
MAX_STDIN_BYTES = 1024 * 1024
MAX_TIMEOUT_SECONDS = 600
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_MAX_OUTPUT_BYTES = 1024 * 1024
MAX_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_ARGV_BYTES = 64 * 1024
WORKSPACE = "/app"
SHELL = "/bin/sh"


def lines_to_stdin(lines: Sequence[str]) -> bytes:
    """Exact stdin for line-oriented inputs: every line is terminated by ``\\n``.

    ``[]`` is empty stdin (no bytes, immediate EOF); ``[""]`` is one empty line.
    No escapes are interpreted and no element is ever an option, so ``"-n"`` and
    backslashes reach the program unchanged.
    """
    return "".join(f"{line}\n" for line in lines).encode("utf-8")


def split_command(command: str) -> Tuple[str, ...]:
    """POSIX-style argument splitting without a shell.

    Quotes group words; operators such as ``&&``, ``|`` or ``>`` are ordinary
    arguments (definitions reject them, see :func:`shell_operator`). Malformed
    quoting is an error, never a reason to use a shell.
    """
    try:
        argv = tuple(shlex.split(command))
    except ValueError as exc:
        raise ValueError(f"Command has malformed quoting: {exc}") from None
    if not argv:
        raise ValueError("Command must name an executable")
    return argv


#: A word made only of shell control/redirection characters, optionally with
#: file-descriptor digits (``&&``, ``|``, ``;``, ``>``, ``2>&1``, ``&`` ...).
_SHELL_OPERATOR = re.compile(r"[0-9]*[&|;<>]+[0-9-]*")


#: Compilation error for a definition command containing a shell operator.
SHELL_OPERATOR_MESSAGE = (
    "`{operator}` is shell syntax, but commands run without a shell, so it would reach the program as an "
    "argument. Put build steps such as compilation in preparation.setup_commands (one command each), quote "
    "the operator to pass it literally, or use sh -c '...' only for a real pipeline.")


def shell_operator(command: str) -> Optional[str]:
    """The first standalone, unquoted shell operator word of ``command``, if any.

    :func:`split_command` passes such a word to the program as an argument, so
    its presence means the command was written for a shell. Quoted or escaped
    operators (``'&&'``, ``\\|``) and operators inside a word are literal text.
    Malformed quoting raises ``ValueError`` exactly as in :func:`split_command`.
    """
    lexer = shlex.shlex(command, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    start = 0
    try:
        while (word := lexer.get_token()) is not None:
            end = lexer.instream.tell()
            # The raw text equals the word only when no quote or escape produced it.
            if command[start:end].strip() == word and _SHELL_OPERATOR.fullmatch(word):
                return word
            start = end
    except ValueError as exc:
        raise ValueError(f"Command has malformed quoting: {exc}") from None
    return None


@dataclass(frozen=True)
class ProcessRequest:
    """One process to run in an execution session.

    Exactly one of ``argv`` (argument vector, no shell) or ``shell`` (explicit
    trusted ``/bin/sh -c`` script) is set. ``timeout`` is the process deadline in
    seconds, measured by the executing host from process start to exit; it
    excludes stdin staging and output readback, which have their own bounds.
    ``max_output_bytes`` bounds each of stdout and stderr at the host.
    """
    argv: Optional[Tuple[str, ...]] = None
    shell: Optional[str] = None
    stdin: bytes = b""
    cwd: str = WORKSPACE
    timeout: float = DEFAULT_TIMEOUT_SECONDS
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES

    def __post_init__(self):
        if (self.argv is None) == (self.shell is None):
            raise ValueError("A process request needs exactly one of argv or shell")
        if self.argv is not None:
            object.__setattr__(self, "argv", tuple(self.argv))
            if not self.argv or not all(isinstance(item, str) for item in self.argv):
                raise ValueError("argv must be a nonempty sequence of strings")
            if not self.argv[0]:
                raise ValueError("argv[0] must name an executable")
        elif not isinstance(self.shell, str) or not self.shell.strip():
            raise ValueError("shell must be a nonempty script")
        words = self.argv if self.argv is not None else (self.shell,)
        if any("\x00" in word for word in words):
            raise ValueError("Commands cannot contain NUL characters")
        if sum(len(word.encode("utf-8")) for word in words) > MAX_ARGV_BYTES:
            raise ValueError(f"Command exceeds {MAX_ARGV_BYTES} bytes")
        if not isinstance(self.stdin, (bytes, bytearray)):
            raise ValueError("stdin must be bytes")
        object.__setattr__(self, "stdin", bytes(self.stdin))
        if len(self.stdin) > MAX_STDIN_BYTES:
            raise ValueError(f"stdin exceeds {MAX_STDIN_BYTES} bytes")
        if (not isinstance(self.cwd, str) or not self.cwd.startswith("/") or "\x00" in self.cwd
                or posixpath.normpath(self.cwd) != self.cwd):
            raise ValueError("cwd must be a normalized absolute path")
        if not 0 < self.timeout <= MAX_TIMEOUT_SECONDS:
            raise ValueError(f"timeout must be within (0, {MAX_TIMEOUT_SECONDS}] seconds")
        if not 0 < self.max_output_bytes <= MAX_OUTPUT_BYTES:
            raise ValueError(f"max_output_bytes must be within [1, {MAX_OUTPUT_BYTES}]")

    @classmethod
    def command(cls, command: str, **options) -> "ProcessRequest":
        """An argument-vector request from a command string (see :func:`split_command`)."""
        return cls(argv=split_command(command), **options)

    @property
    def program(self) -> Tuple[str, ...]:
        """The argument vector that is executed (``/bin/sh -c`` for shell requests)."""
        return self.argv if self.argv is not None else (SHELL, "-c", self.shell)


class ProcessStatus(Enum):
    """What happened to a process the backend tried to run."""
    EXITED = "exited"            # the process ran and returned exit_code (any value)
    TIMED_OUT = "timed_out"      # the deadline passed; the backend terminated it
    NOT_STARTED = "not_started"  # the executable was not found or not executable


class ResponseCategory(Enum):
    """Student-facing classification of a started process (deliberate execution wire values)."""
    SUCCESS = "success"
    RUNTIME_ERROR = "runtime_error"
    TIMEOUT = "timeout"


@dataclass(frozen=True)
class ProcessResult:
    """A process outcome. Infrastructure failures are raised, never returned.

    ``exit_code`` is the code the process returned, or ``None`` when it timed out
    or never started. A code such as 137 is reported as returned: it may come
    from ``exit(137)`` or from a SIGKILL (for example the memory limit), and only
    ``TIMED_OUT`` means that the deadline stopped the process. Outputs are decoded
    UTF-8 (invalid bytes replaced) after bounding at the host.
    """
    status: ProcessStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    duration: float = 0.0
    #: The executable that could not be started (``NOT_STARTED`` only).
    missing_executable: Optional[str] = field(default=None)

    @property
    def started(self) -> bool:
        return self.status is not ProcessStatus.NOT_STARTED

    @property
    def succeeded(self) -> bool:
        return self.status is ProcessStatus.EXITED and self.exit_code == 0

    @property
    def truncated(self) -> bool:
        return self.stdout_truncated or self.stderr_truncated

    @property
    def category(self) -> ResponseCategory:
        """Classification by exit status only; output wording never matters."""
        if self.status is ProcessStatus.NOT_STARTED:
            raise ValueError("A process that never started has no category")
        if self.status is ProcessStatus.TIMED_OUT:
            return ResponseCategory.TIMEOUT
        return ResponseCategory.SUCCESS if self.exit_code == 0 else ResponseCategory.RUNTIME_ERROR


def decode_output(data: bytes, truncated: bool) -> str:
    """Decode bounded output; a multibyte character cut by truncation is dropped."""
    if truncated:
        data = data[:len(data) - _incomplete_tail(data)]
    return data.decode("utf-8", errors="replace")


def _incomplete_tail(data: bytes) -> int:
    """Length of a UTF-8 sequence left incomplete at the end of ``data``."""
    for back in range(1, min(4, len(data)) + 1):
        byte = data[-back]
        if byte & 0xC0 != 0x80:  # an ASCII or lead byte
            needed = 1 if byte < 0x80 else 2 if byte >> 5 == 0b110 else 3 if byte >> 4 == 0b1110 else 4
            return back if needed > back else 0
    return 0
