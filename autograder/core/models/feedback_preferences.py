from typing import List, Dict, Any


class FeedbackPreferences:
    """
    A unified model to store all feedback preferences, including the new
    test-linked learning resources and legacy AI configurations.
    """

    class LearningResource:
        """Represents a single online resource linked to specific test names."""
        def __init__(self, url: str, description: str, linked_tests: List[str]):
            self.url = url
            self.description = description
            self.linked_tests = linked_tests

        def __repr__(self):
            return f"LearningResource(url='{self.url}', tests={self.linked_tests})"

    class GeneralPreferences:
        """Preferences applicable to both Default and AI reporters."""

        def __init__(self,
                     report_title: str = "Relatório de Avaliação",
                     show_score: bool = True,
                     show_passed_tests: bool = False,
                     add_report_summary: bool = True,
                     online_content: List['FeedbackPreferences.LearningResource'] = None):
            self.report_title = report_title
            self.show_score = show_score
            self.show_passed_tests = show_passed_tests
            self.add_report_summary = add_report_summary
            self.online_content = online_content if online_content is not None else []

    class AiReporterPreferences:
        """Preferences specific to the AI Reporter."""

        def __init__(self,
                     provide_solutions: str = "hint",
                     feedback_tone: str = "encouraging but direct",
                     feedback_persona: str = "Code Buddy",
                     assignment_context: str = "",
                     extra_orientations: str = "",
                     submission_files_to_read: List[str] = None):
            self.provide_solutions = provide_solutions
            self.feedback_tone = feedback_tone
            self.feedback_persona = feedback_persona
            self.assignment_context = assignment_context
            self.extra_orientations = extra_orientations
            self.submission_files_to_read = submission_files_to_read if submission_files_to_read is not None else []

    class DefaultReporterPreferences:
        """Preferences specific to the Default (template-based) Reporter."""

        def __init__(self, category_headers: Dict[str, str] = None):
            if category_headers is None:
                self.category_headers = {
                    "base": "✅ Requisitos Essenciais",
                    "bonus": "⭐ Pontos Extras",
                    "penalty": "❌ Pontos a Melhorar"
                }
            else:
                self.category_headers = category_headers

    def __init__(self):
        self.general = self.GeneralPreferences()
        self.ai = self.AiReporterPreferences()
        self.default = self.DefaultReporterPreferences()

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'FeedbackPreferences':
        """
        Creates a FeedbackPreferences object from a dictionary, with defaults.
        """
        prefs = cls()

        # --- Parse General Preferences, including the new online_content ---
        general_prefs_data = config_dict.get('general', {})
        online_content_data = general_prefs_data.pop('online_content', [])

        prefs.general = cls.GeneralPreferences(**general_prefs_data)
        prefs.general.online_content = [
            cls.LearningResource(**res) for res in online_content_data
        ]

        # --- Parse AI and Default Preferences ---
        ai_prefs_data = config_dict.get('ai', {})
        default_prefs_data = config_dict.get('default', {})

        prefs.ai = cls.AiReporterPreferences(**ai_prefs_data)
        prefs.default = cls.DefaultReporterPreferences(**default_prefs_data)

        return prefs