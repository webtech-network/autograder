"""Service for resolving language-specific program commands."""

import logging
from typing import Dict, Optional, Any
from sandbox_manager.models.sandbox_models import Language


class CommandResolver:
    """
    Resolves program commands based on submission language.

    Supports both legacy single-command format and new multi-language format.
    """

    # Default command patterns for each language
    DEFAULT_COMMANDS = {
        Language.PYTHON: "python3 {filename}",
        Language.JAVA: "java {classname}",
        Language.NODE: "node {filename}",
        Language.CPP: "./{executable}"
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def resolve_command(
        self,
        program_command: Any,
        language: Language,
        fallback_filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Resolve program command based on language.

        Args:
            program_command: Either a string (legacy), dict (multi-language), or special value
            language: The submission's language
            fallback_filename: Optional filename to use for default command generation

        Returns:
            Resolved command string, or None if no command should be used

        Examples:
            # Legacy format (single command)
            resolve_command("python3 calc.py", Language.PYTHON) -> "python3 calc.py"

            # Multi-language format
            resolve_command({
                "python": "python3 calculator.py",
                "java": "java Calculator",
                "node": "node calculator.js",
                "cpp": "./calculator"
            }, Language.JAVA) -> "java Calculator"

            # Special CMD placeholder
            resolve_command("CMD", Language.PYTHON) -> Auto-resolves based on files
        """
        # Handle None
        if program_command is None:
            return None

        # Handle special "CMD" placeholder for auto-resolution
        if isinstance(program_command, str) and program_command == "CMD":
            return self._auto_resolve_command(language, fallback_filename)

        # Handle dict format (multi-language)
        if isinstance(program_command, dict):
            return self._resolve_from_dict(program_command, language)

        # Handle legacy string format (single command)
        if isinstance(program_command, str):
            self.logger.warning(
                f"Using legacy single-command format: '{program_command}'. "
                f"Consider using multi-language format or 'CMD' placeholder."
            )
            return program_command

        self.logger.error(f"Invalid program_command format: {type(program_command)}")
        return None

    def _resolve_from_dict(self, commands: Dict[str, str], language: Language) -> Optional[str]:
        """Resolve command from multi-language dict."""
        # Try exact language value match (e.g., "python", "java", "node", "cpp")
        lang_value = language.value.lower()
        if lang_value in commands:
            return commands[lang_value]

        # Try language name match (e.g., "PYTHON", "JAVA")
        lang_name = language.name.lower()
        if lang_name in commands:
            return commands[lang_name]

        # No command found for this language
        self.logger.warning(
            f"No command defined for language '{language.value}' in multi-language config. "
            f"Available: {list(commands.keys())}"
        )
        return None

    def _auto_resolve_command(
        self,
        language: Language,
        fallback_filename: Optional[str] = None
    ) -> Optional[str]:
        """
        Auto-resolve command based on language and available files.

        This is used when program_command is "CMD" placeholder.
        """
        if language == Language.PYTHON:
            # Look for common Python entry points
            if fallback_filename:
                return f"python3 {fallback_filename}"
            return "python3 main.py"

        elif language == Language.JAVA:
            # Java requires class name without .java extension
            if fallback_filename and fallback_filename.endswith('.java'):
                classname = fallback_filename[:-5]  # Remove .java
                return f"java {classname}"
            return "java Main"

        elif language == Language.NODE:
            if fallback_filename:
                return f"node {fallback_filename}"
            return "node index.js"

        elif language == Language.CPP:
            # C++ executables are typically compiled to a specific name
            if fallback_filename and fallback_filename.endswith('.cpp'):
                executable = fallback_filename[:-4]  # Remove .cpp
                return f"./{executable}"
            return "./a.out"

        self.logger.error(f"Cannot auto-resolve command for language: {language}")
        return None

    def is_multi_language_format(self, program_command: Any) -> bool:
        """Check if program_command uses multi-language dict format."""
        return isinstance(program_command, dict)

    def is_legacy_format(self, program_command: Any) -> bool:
        """Check if program_command uses legacy single-string format."""
        return isinstance(program_command, str) and program_command != "CMD"

