from typing import List, Dict, Any
from autograder.context import request_context

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
    def from_dict(cls) -> 'FeedbackPreferences':
        """
        Creates a FeedbackPreferences object from a dictionary, with defaults.
        """
        request = request_context.get_request()
        config_dict = request.assignment_config.feedback
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

if __name__ == '__main__':
    feedback_config = {
        "general": {
            "report_title": "Relatório Final - Desafio Web",
            "add_report_summary": True,
            "online_content": [
                {
                    "url": "https://developer.mozilla.org/pt-BR/docs/Web/HTML/Element/img",
                    "description": "Guia completo sobre a tag <img>.",
                    "linked_tests": ["check_all_images_have_alt"]
                }
            ]
        },
        "ai": {
            "assignment_context": "Este é um desafio focado em HTML semântico e CSS responsivo.",
            "feedback_persona": "Professor Sênior"
        },
        "default": {
            "category_headers": {
                "base": "✔️ Requisitos Obrigatórios",
                "penalty": "🚨 Pontos de Atenção"
            }
        }
    }

    # ===============================================================
    # 2. CREATE THE PREFERENCES OBJECT FROM THE DICTIONARY
    # ===============================================================
    # The .from_dict() method will parse the dictionary and fill in any missing
    # values with the defaults defined in the class.
    try:
        preferences = FeedbackPreferences.from_dict(feedback_config)

        # ===============================================================
        # 3. VERIFY THE PARSED VALUES
        # ===============================================================
        print("--- FeedbackPreferences object created successfully ---\n")

        # --- Verify General Preferences ---
        print("✅ General Preferences:")
        print(f"  - Report Title: '{preferences.general.report_title}' (Loaded from config)")
        print(f"  - Show Score: {preferences.general.show_score} (Using default value)")
        print(f"  - Online Content Items: {len(preferences.general.online_content)} (Loaded from config)")
        print(f"    - First item URL: {preferences.general.online_content[0].url}")
        print(f"    - Linked to tests: {preferences.general.online_content[0].linked_tests}")

        # --- Verify AI Preferences ---
        print("\n🤖 AI Reporter Preferences:")
        print(f"  - Feedback Persona: '{preferences.ai.feedback_persona}' (Loaded from config)")
        print(f"  - Feedback Tone: '{preferences.ai.feedback_tone}' (Using default value)")
        print(f"  - Assignment Context: '{preferences.ai.assignment_context}' (Loaded from config)")

        # --- Verify Default Reporter Preferences ---
        print("\n📝 Default Reporter Preferences:")
        print(f"  - Base Header: '{preferences.default.category_headers['base']}' (Loaded from config)")
        # 'bonus' was not in the config, so it should use the default from the class
        print(f"  - Bonus Header: '{preferences.default.category_headers['bonus']}' (Using default value)")

    except Exception as e:
        print(f"An error occurred: {e}")