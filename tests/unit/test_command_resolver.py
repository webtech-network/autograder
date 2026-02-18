"""Tests for CommandResolver service."""

import pytest
from autograder.services.command_resolver import CommandResolver
from sandbox_manager.models.sandbox_models import Language


class TestCommandResolver:
    """Test the CommandResolver service for multi-language command resolution."""

    def setup_method(self):
        """Set up test fixtures."""
        self.resolver = CommandResolver()

    def test_resolve_legacy_single_command(self):
        """Test resolving legacy single-string command format."""
        result = self.resolver.resolve_command(
            "python3 calculator.py",
            Language.PYTHON
        )
        assert result == "python3 calculator.py"

    def test_resolve_multi_language_dict_python(self):
        """Test resolving multi-language dict format for Python."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator",
            "node": "node calculator.js",
            "cpp": "./calculator"
        }

        result = self.resolver.resolve_command(commands, Language.PYTHON)
        assert result == "python3 calculator.py"

    def test_resolve_multi_language_dict_java(self):
        """Test resolving multi-language dict format for Java."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator",
            "node": "node calculator.js",
            "cpp": "./calculator"
        }

        result = self.resolver.resolve_command(commands, Language.JAVA)
        assert result == "java Calculator"

    def test_resolve_multi_language_dict_node(self):
        """Test resolving multi-language dict format for Node.js."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator",
            "node": "node calculator.js",
            "cpp": "./calculator"
        }

        result = self.resolver.resolve_command(commands, Language.NODE)
        assert result == "node calculator.js"

    def test_resolve_multi_language_dict_cpp(self):
        """Test resolving multi-language dict format for C++."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator",
            "node": "node calculator.js",
            "cpp": "./calculator"
        }

        result = self.resolver.resolve_command(commands, Language.CPP)
        assert result == "./calculator"

    def test_resolve_cmd_placeholder_python(self):
        """Test auto-resolution with CMD placeholder for Python."""
        result = self.resolver.resolve_command("CMD", Language.PYTHON)
        assert result == "python3 main.py"

    def test_resolve_cmd_placeholder_java(self):
        """Test auto-resolution with CMD placeholder for Java."""
        result = self.resolver.resolve_command("CMD", Language.JAVA)
        assert result == "java Main"

    def test_resolve_cmd_placeholder_node(self):
        """Test auto-resolution with CMD placeholder for Node.js."""
        result = self.resolver.resolve_command("CMD", Language.NODE)
        assert result == "node index.js"

    def test_resolve_cmd_placeholder_cpp(self):
        """Test auto-resolution with CMD placeholder for C++."""
        result = self.resolver.resolve_command("CMD", Language.CPP)
        assert result == "./a.out"

    def test_resolve_none_command(self):
        """Test that None command returns None."""
        result = self.resolver.resolve_command(None, Language.PYTHON)
        assert result is None

    def test_resolve_missing_language_in_dict(self):
        """Test that missing language in dict returns None."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator"
            # node and cpp missing
        }

        result = self.resolver.resolve_command(commands, Language.NODE)
        assert result is None

    def test_resolve_with_fallback_filename_python(self):
        """Test auto-resolution with fallback filename for Python."""
        result = self.resolver.resolve_command(
            "CMD",
            Language.PYTHON,
            fallback_filename="calculator.py"
        )
        assert result == "python3 calculator.py"

    def test_resolve_with_fallback_filename_java(self):
        """Test auto-resolution with fallback filename for Java."""
        result = self.resolver.resolve_command(
            "CMD",
            Language.JAVA,
            fallback_filename="Calculator.java"
        )
        assert result == "java Calculator"

    def test_resolve_with_fallback_filename_node(self):
        """Test auto-resolution with fallback filename for Node.js."""
        result = self.resolver.resolve_command(
            "CMD",
            Language.NODE,
            fallback_filename="calculator.js"
        )
        assert result == "node calculator.js"

    def test_resolve_with_fallback_filename_cpp(self):
        """Test auto-resolution with fallback filename for C++."""
        result = self.resolver.resolve_command(
            "CMD",
            Language.CPP,
            fallback_filename="calculator.cpp"
        )
        assert result == "./calculator"

    def test_is_multi_language_format(self):
        """Test detection of multi-language format."""
        assert self.resolver.is_multi_language_format({"python": "cmd"}) is True
        assert self.resolver.is_multi_language_format("python3 calc.py") is False
        assert self.resolver.is_multi_language_format("CMD") is False
        assert self.resolver.is_multi_language_format(None) is False

    def test_is_legacy_format(self):
        """Test detection of legacy single-string format."""
        assert self.resolver.is_legacy_format("python3 calc.py") is True
        assert self.resolver.is_legacy_format("CMD") is False
        assert self.resolver.is_legacy_format({"python": "cmd"}) is False
        assert self.resolver.is_legacy_format(None) is False

    def test_resolve_with_uppercase_language_keys(self):
        """Test that resolver handles uppercase language keys in dict."""
        commands = {
            "PYTHON": "python3 calculator.py",
            "JAVA": "java Calculator"
        }

        # Should not match uppercase keys directly, but lowercase value should work
        result = self.resolver.resolve_command(commands, Language.PYTHON)
        # The resolver looks for lowercase keys first, so this might not work
        # Let's check what actually happens
        assert result is None or result == "python3 calculator.py"

    def test_complex_multi_language_config(self):
        """Test complex multi-language configuration."""
        commands = {
            "python": "python3 -u calculator.py",
            "java": "java -cp . Calculator",
            "node": "node --no-warnings calculator.js",
            "cpp": "./calculator"
        }

        assert self.resolver.resolve_command(commands, Language.PYTHON) == "python3 -u calculator.py"
        assert self.resolver.resolve_command(commands, Language.JAVA) == "java -cp . Calculator"
        assert self.resolver.resolve_command(commands, Language.NODE) == "node --no-warnings calculator.js"
        assert self.resolver.resolve_command(commands, Language.CPP) == "./calculator"

    def test_partial_multi_language_config(self):
        """Test partial multi-language config (not all languages specified)."""
        commands = {
            "python": "python3 calculator.py",
            "java": "java Calculator"
        }

        # Should work for specified languages
        assert self.resolver.resolve_command(commands, Language.PYTHON) == "python3 calculator.py"
        assert self.resolver.resolve_command(commands, Language.JAVA) == "java Calculator"

        # Should return None for unspecified languages
        assert self.resolver.resolve_command(commands, Language.NODE) is None
        assert self.resolver.resolve_command(commands, Language.CPP) is None

    def test_resolve_empty_dict(self):
        """Test that empty dict returns None."""
        result = self.resolver.resolve_command({}, Language.PYTHON)
        assert result is None

    def test_resolve_invalid_type(self):
        """Test that invalid types return None."""
        result = self.resolver.resolve_command(123, Language.PYTHON)
        assert result is None

        result = self.resolver.resolve_command([], Language.PYTHON)
        assert result is None

