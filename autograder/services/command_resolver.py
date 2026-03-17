"""Service for resolving language-specific program commands."""

import logging
from typing import Dict, Optional, Any
from sandbox_manager.models.sandbox_models import Language


class CommandResolver:
    """
    Resolves program commands based on submission language.

    Supports dict-based multi-language format and CMD placeholder.
    """

    # Default command patterns for each language
    DEFAULT_COMMANDS = {
        Language.PYTHON: "python3 {filename}",
        Language.JAVA: "java {classname}",
        Language.NODE: "node {filename}",
        Language.CPP: "./{executable}",
        Language.C: "./{executable}"
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
            program_command: Either a dict (multi-language), or special "CMD" placeholder value
            language: The submission's language
            fallback_filename: Optional filename to use for default command generation

        Returns:
            Resolved command string, or None if no command should be used

        Examples:
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

        self.logger.error(
            "Invalid program_command format: %s. Only dict or 'CMD' placeholder are supported.",
            type(program_command)
        )
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
            "No command defined for language '%s' in multi-language config. Available: %s",
            language.value,
            list(commands.keys())
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
        command = None
        if language == Language.PYTHON:
            command = f"python3 {fallback_filename}" if fallback_filename else "python3 main.py"
        elif language == Language.JAVA:
            # Java requires class name without .java extension
            if fallback_filename and fallback_filename.endswith('.java'):
                classname = fallback_filename[:-5]  # Remove .java
                command = f"java {classname}"
            else:
                command = "java Main"
        elif language == Language.NODE:
            command = f"node {fallback_filename}" if fallback_filename else "node index.js"
        elif language == Language.CPP:
            # C++ executables are typically compiled to a specific name
            if fallback_filename and fallback_filename.endswith('.cpp'):
                executable = fallback_filename[:-4]  # Remove .cpp
                command = f"./{executable}"
            else:
                command = "./a.out"
        elif language == Language.C:
            # C executables follow the same pattern as C++
            if fallback_filename and fallback_filename.endswith('.c'):
                executable = fallback_filename[:-2]  # Remove .c
                command = f"./{executable}"
            else:
                command = "./a.out"
        else:
            self.logger.error("Cannot auto-resolve command for language: %s", language)

        return command

    def is_multi_language_format(self, program_command: Any) -> bool:
        """Check if program_command uses multi-language dict format."""
        return isinstance(program_command, dict)

