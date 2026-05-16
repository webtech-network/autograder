import unittest
from unittest.mock import MagicMock
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language

class TestIssue315Security(unittest.TestCase):
    def setUp(self):
        self.mock_container = MagicMock()
        self.sandbox = SandboxContainer(
            language=Language.PYTHON,
            container_ref=self.mock_container
        )
        
        # Setup mock result for exec_run
        self.mock_result = MagicMock()
        self.mock_result.exit_code = 0
        self.mock_result.output = (b"", b"")
        self.mock_container.exec_run.return_value = self.mock_result

    def test_run_commands_injection_blocked(self):
        """
        Verify that shell injection in program_command is blocked in run_commands.
        """
        # A malicious program_command that tries to escape
        malicious_command = "python3 main.py ) && touch /tmp/pwned && ( #"
        
        self.sandbox.run_commands(["input1"], program_command=malicious_command)
        
        # Verify the actual command sent to exec_run
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        # In the fixed version, it should be ['/bin/sh', '-c', "..."]
        # and the program_command part should be quoted.
        self.assertEqual(cmd_sent[0], "/bin/sh")
        self.assertEqual(cmd_sent[1], "-c")
        
        full_cmd_string = cmd_sent[2]
        print(f"\nCommand sent to shell: {full_cmd_string}")
        
        # Check that '&&' is quoted and thus NOT a shell operator
        self.assertIn("'&&'", full_cmd_string)
        self.assertNotIn(") && touch /tmp/pwned", full_cmd_string)

    def test_run_command_injection_blocked(self):
        """
        Verify that run_command bypasses the shell and thus blocks injection.
        """
        malicious_command = "echo hello && touch /tmp/pwned"
        self.sandbox.run_command(malicious_command)
        
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        # In the fixed version, it should be a list of parts, NO /bin/sh
        self.assertIsInstance(cmd_sent, list)
        self.assertEqual(cmd_sent, ["echo", "hello", "&&", "touch", "/tmp/pwned"])
        self.assertNotEqual(cmd_sent[0], "/bin/sh")
        
    def test_run_command_with_spaces_supported(self):
        """
        Verify that run_command still supports spaces in arguments when correctly quoted.
        """
        command_with_spaces = 'cat "file with space.txt"'
        self.sandbox.run_command(command_with_spaces)
        
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        self.assertEqual(cmd_sent, ["cat", "file with space.txt"])

    def test_run_commands_with_spaces_supported(self):
        """
        Verify that run_commands supports spaces in program_command.
        """
        program_with_spaces = 'python3 "my script.py"'
        self.sandbox.run_commands(["input1"], program_command=program_with_spaces)
        
        exec_run_call = self.mock_container.exec_run.call_args
        full_cmd_string = exec_run_call[1]['cmd'][2]
        
        # Should be something like: echo 'input1' | 'python3' 'my script.py'
        self.assertIn("'my script.py'", full_cmd_string)
        self.assertIn("python3", full_cmd_string)

    def test_run_commands_no_program_command(self):
        """
        Verify that run_commands works when program_command is None.
        """
        self.sandbox.run_commands(["input1", "input2"])
        
        exec_run_call = self.mock_container.exec_run.call_args
        full_cmd_string = exec_run_call[1]['cmd'][2]
        
        # Should just be echo ...
        self.assertTrue(full_cmd_string.startswith("echo "))
        self.assertIn("input1", full_cmd_string)
        self.assertIn("input2", full_cmd_string)

    def test_run_command_malformed_shlex_fallback(self):
        """
        Verify that run_command falls back to shell if shlex fails (e.g. unclosed quote).
        """
        malformed_command = 'echo "unclosed quote'
        self.sandbox.run_command(malformed_command)
        
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        # Should fallback to /bin/sh -c
        self.assertEqual(cmd_sent, ["/bin/sh", "-c", malformed_command])

if __name__ == '__main__':
    unittest.main()
