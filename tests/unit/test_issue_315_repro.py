import unittest
from unittest.mock import MagicMock
from sandbox_manager.sandbox_container import SandboxContainer
from sandbox_manager.models.sandbox_models import Language

class TestIssue315Reproduction(unittest.TestCase):
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

    def test_run_commands_injection(self):
        """
        Demonstrate that program_command can be used for shell injection in run_commands.
        """
        # A malicious program_command that escapes the intended command
        malicious_command = "python3 main.py ) && touch /tmp/pwned && ( #"
        
        self.sandbox.run_commands(["input1"], program_command=malicious_command)
        
        # Verify the actual command sent to exec_run
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        full_cmd_string = cmd_sent[2]
        print(f"\nCommand sent to shell: {full_cmd_string}")
        
        # Check if the injected part is in the command outside of the parentheses it was supposed to be in
        self.assertIn("&& touch /tmp/pwned", full_cmd_string)
        
    def test_run_command_injection(self):
        """
        Check if run_command is also vulnerable.
        """
        malicious_command = "echo hello && touch /tmp/pwned"
        self.sandbox.run_command(malicious_command)
        
        exec_run_call = self.mock_container.exec_run.call_args
        cmd_sent = exec_run_call[1]['cmd']
        
        full_cmd_string = cmd_sent[2]
        self.assertEqual(full_cmd_string, malicious_command)

if __name__ == '__main__':
    unittest.main()
