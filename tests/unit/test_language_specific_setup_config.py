"""Tests for language-specific setup configuration."""

import pytest
from autograder.services.pre_flight_service import PreFlightService
from sandbox_manager.models.sandbox_models import Language


class TestLanguageSpecificSetupConfig:
    """Test language-specific setup configuration resolution."""

    def test_language_specific_format_python(self):
        """Test language-specific format for Python."""
        setup_config = {
            "python": {
                "required_files": ["main.py"],
                "setup_commands": []
            },
            "java": {
                "required_files": ["Main.java"],
                "setup_commands": ["javac Main.java"]
            }
        }

        service = PreFlightService(setup_config, submission_language=Language.PYTHON)

        assert service.required_files == ["main.py"]
        assert service.setup_commands == []

    def test_language_specific_format_java(self):
        """Test language-specific format for Java."""
        setup_config = {
            "python": {
                "required_files": ["main.py"],
                "setup_commands": []
            },
            "java": {
                "required_files": ["Main.java"],
                "setup_commands": ["javac Main.java"]
            }
        }

        service = PreFlightService(setup_config, submission_language=Language.JAVA)

        assert service.required_files == ["Main.java"]
        assert service.setup_commands == ["javac Main.java"]

    def test_language_specific_format_cpp(self):
        """Test language-specific format for C++."""
        setup_config = {
            "cpp": {
                "required_files": ["main.cpp"],
                "setup_commands": ["g++ main.cpp -o main"]
            },
            "python": {
                "required_files": ["main.py"],
                "setup_commands": []
            }
        }

        service = PreFlightService(setup_config, submission_language=Language.CPP)

        assert service.required_files == ["main.cpp"]
        assert service.setup_commands == ["g++ main.cpp -o main"]

    def test_language_specific_format_node(self):
        """Test language-specific format for Node.js."""
        setup_config = {
            "node": {
                "required_files": ["package.json", "index.js"],
                "setup_commands": ["npm install"]
            }
        }

        service = PreFlightService(setup_config, submission_language=Language.NODE)

        assert service.required_files == ["package.json", "index.js"]
        assert service.setup_commands == ["npm install"]

    def test_language_not_in_config(self):
        """Test when submission language is not in the config."""
        setup_config = {
            "python": {
                "required_files": ["main.py"],
                "setup_commands": []
            },
            "java": {
                "required_files": ["Main.java"],
                "setup_commands": ["javac Main.java"]
            }
        }

        # Try to get config for C++ which is not defined
        service = PreFlightService(setup_config, submission_language=Language.CPP)


        # Should return empty config
        assert service.required_files == []
        assert service.setup_commands == []

    def test_empty_setup_config(self):
        """Test with empty setup config."""
        service = PreFlightService({}, submission_language=Language.PYTHON)

        assert service.required_files == []
        assert service.setup_commands == []

    def test_none_setup_config(self):
        """Test with None setup config."""
        service = PreFlightService(None, submission_language=Language.PYTHON)

        assert service.required_files == []
        assert service.setup_commands == []


    def test_all_languages_in_one_config(self):
        """Test config with all supported languages."""
        setup_config = {
            "python": {
                "required_files": ["main.py"],
                "setup_commands": ["pip install -r requirements.txt"]
            },
            "java": {
                "required_files": ["Main.java"],
                "setup_commands": ["javac Main.java"]
            },
            "node": {
                "required_files": ["index.js"],
                "setup_commands": ["npm install"]
            },
            "cpp": {
                "required_files": ["main.cpp"],
                "setup_commands": ["g++ main.cpp -o main"]
            }
        }

        # Test each language
        for lang, expected_files in [
            (Language.PYTHON, ["main.py"]),
            (Language.JAVA, ["Main.java"]),
            (Language.NODE, ["index.js"]),
            (Language.CPP, ["main.cpp"])
        ]:
            service = PreFlightService(setup_config, submission_language=lang)
            assert service.required_files == expected_files
            assert len(service.setup_commands) > 0

    def test_empty_language_specific_config(self):
        """Test language-specific config with empty values."""
        setup_config = {
            "python": {},
            "java": {
                "required_files": [],
                "setup_commands": []
            }
        }

        # Python with empty dict
        service_py = PreFlightService(setup_config, submission_language=Language.PYTHON)
        assert service_py.required_files == []
        assert service_py.setup_commands == []

        # Java with explicit empty arrays
        service_java = PreFlightService(setup_config, submission_language=Language.JAVA)
        assert service_java.required_files == []
        assert service_java.setup_commands == []

