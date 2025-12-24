import unittest
from autograder.steps.pre_flight_step import PreFlightStep
from autograder.models.dataclass.step_result import StepStatus
from autograder.models.dataclass.preflight_error import PreflightCheckType


class TestPreFlightStep(unittest.TestCase):

    def test_no_required_files_passes(self):
        """Test that step passes when no required files are specified"""
        setup_config = {}
        step = PreFlightStep(setup_config)

        result = step.execute(['file1.py', 'file2.py'])

        self.assertEqual(result.status, StepStatus.SUCCESS)
        self.assertIsNone(result.error)
        self.assertTrue(result.is_successful)

    def test_required_files_all_present_passes(self):
        """Test that step passes when all required files are present"""
        setup_config = {
            'required_files': ['file1.py', 'file2.py']
        }
        step = PreFlightStep(setup_config)

        result = step.execute(['file1.py', 'file2.py', 'file3.py'])

        self.assertEqual(result.status, StepStatus.SUCCESS)
        self.assertIsNone(result.error)
        self.assertTrue(result.is_successful)

    def test_required_files_missing_fails(self):
        """Test that step fails when required files are missing"""
        setup_config = {
            'required_files': ['file1.py', 'file2.py']
        }
        step = PreFlightStep(setup_config)

        result = step.execute(['file1.py'])  # file2.py is missing

        self.assertEqual(result.status, StepStatus.FAIL)
        self.assertIsNotNone(result.error)
        self.assertFalse(result.is_successful)
        self.assertIn('file2.py', result.error)
        self.assertEqual(result.failed_at_step, 'PreFlightStep')

    def test_multiple_missing_files_all_reported(self):
        """Test that all missing files are reported in the error"""
        setup_config = {
            'required_files': ['file1.py', 'file2.py', 'file3.py']
        }
        step = PreFlightStep(setup_config)

        result = step.execute(['file1.py'])  # file2.py and file3.py are missing

        self.assertEqual(result.status, StepStatus.FAIL)
        self.assertIn('file2.py', result.error)
        self.assertIn('file3.py', result.error)

    def test_setup_commands_not_run_when_file_check_fails(self):
        """Test that setup commands are not checked if file check fails"""
        setup_config = {
            'required_files': ['missing.py'],
            'setup_commands': ['npm install']
        }
        step = PreFlightStep(setup_config)

        result = step.execute(['other.py'])

        # Should fail on file check, not even attempt setup commands
        self.assertEqual(result.status, StepStatus.FAIL)
        self.assertIn('missing.py', result.error)

        # Verify only file check errors are present
        file_check_errors = [e for e in step._pre_flight_service.fatal_errors
                           if e.type == PreflightCheckType.FILE_CHECK]
        setup_errors = [e for e in step._pre_flight_service.fatal_errors
                       if e.type == PreflightCheckType.SETUP_COMMAND]

        self.assertGreater(len(file_check_errors), 0)
        self.assertEqual(len(setup_errors), 0)


if __name__ == '__main__':
    unittest.main()

