"""Docker's exec API at its socket, for hermetic tests of execs fed on stdin.

``exec_start(socket=True)`` returns one end of a real socket pair; a thread on the
other end plays the daemon: it reads stdin to EOF, records it, then answers with
Docker's multiplexed stream and the configured exit code.
"""
import io
from socket import socketpair
import struct
import tarfile
import threading


class StdinExecApi:
    """Appends ``(cmd, user, workdir)`` of each exec to ``calls``; ``stdin`` maps exec IDs to their input."""

    def __init__(self, calls=None, exit_code=0, output=b""):
        self.calls = [] if calls is None else calls
        self.stdin = {}
        self.exit_code, self.output = exit_code, output

    def exec_create(self, container, cmd, user=None, workdir=None, stdin=False, **_):
        assert stdin is True, "only execs fed on stdin reach the low-level API"
        self.calls.append((cmd, user, workdir))
        exec_id = str(len(self.calls))
        self.stdin[exec_id] = None
        return {"Id": exec_id}

    def exec_start(self, exec_id, socket=False):
        assert socket is True
        ours, theirs = socketpair()

        def daemon():
            received = bytearray()
            while chunk := theirs.recv(65536):
                received += chunk
            self.stdin[exec_id] = bytes(received)
            if self.output:
                theirs.sendall(struct.pack(">BxxxL", 2, len(self.output)) + self.output)
            theirs.close()

        threading.Thread(target=daemon, daemon=True).start()
        return ours

    def exec_inspect(self, _exec_id):
        return {"ExitCode": self.exit_code}

    def archives(self):
        """Each staged archive as ``{name: (bytes, mode)}``, in exec order."""
        staged = []
        for data in self.stdin.values():
            with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                staged.append({member.name: (archive.extractfile(member).read(), member.mode)
                               for member in archive.getmembers()})
        return staged

