"""
Autograder Package Initialization

This module initializes core services at application startup.
"""

from autograder.services.template_library_service import TemplateLibraryService

# Initialize the singleton TemplateLibraryService at module import
# This ensures all templates are loaded once at application startup
_template_service = TemplateLibraryService.get_instance()

__all__ = ['TemplateLibraryService']

