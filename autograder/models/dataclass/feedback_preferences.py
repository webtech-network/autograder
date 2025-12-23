from typing import List, Dict
from dataclasses import dataclass, field
from autograder.context import request_context


@dataclass
class LearningResource:
    """Represents a single online resource linked to specific test names."""
    url: str
    description: str
    linked_tests: List[str]

    def __repr__(self) -> str:
        return f"LearningResource(url='{self.url}', tests={self.linked_tests})"


@dataclass
class GeneralPreferences:
    """Preferences applicable to both Default and AI reporters."""
    report_title: str = "Relatório de Avaliação"
    show_score: bool = True
    show_passed_tests: bool = False
    add_report_summary: bool = True
    online_content: List[LearningResource] = field(default_factory=list)


@dataclass
class AiReporterPreferences:
    """Preferences specific to the AI Reporter."""
    provide_solutions: str = "hint"
    feedback_tone: str = "encouraging but direct"
    feedback_persona: str = "Code Buddy"
    assignment_context: str = ""
    extra_orientations: str = ""
    submission_files_to_read: List[str] = field(default_factory=list)


def _default_category_headers() -> Dict[str, str]:
    """Factory function for default category headers."""
    return {
        "base": "✅ Requisitos Essenciais",
        "bonus": "⭐ Pontos Extras",
        "penalty": "❌ Pontos a Melhorar"
    }


@dataclass
class DefaultReporterPreferences:
    """Preferences specific to the Default (template-based) Reporter."""
    category_headers: Dict[str, str] = field(default_factory=_default_category_headers)


@dataclass
class FeedbackPreferences:
    """
    A unified model to store all feedback preferences, including the new
    test-linked learning resources and legacy AI configurations.
    """
    general: GeneralPreferences = field(default_factory=GeneralPreferences)
    ai: AiReporterPreferences = field(default_factory=AiReporterPreferences)
    default: DefaultReporterPreferences = field(default_factory=DefaultReporterPreferences)

    @classmethod
    def from_dict(cls) -> 'FeedbackPreferences':
        """
        Creates a FeedbackPreferences object from a dictionary, with defaults.
        """
        request = request_context.get_request()
        config_dict = request.assignment_config.feedback

        # --- Parse General Preferences, including the new online_content ---
        general_prefs_data = config_dict.get('general', {}).copy()
        online_content_data = general_prefs_data.pop('online_content', [])

        # Create LearningResource objects
        online_resources = [LearningResource(**res) for res in online_content_data]
        general_prefs_data['online_content'] = online_resources
        
        general = GeneralPreferences(**general_prefs_data)

        # --- Parse AI and Default Preferences ---
        ai_prefs_data = config_dict.get('ai', {})
        default_prefs_data = config_dict.get('default', {})

        ai = AiReporterPreferences(**ai_prefs_data)
        default = DefaultReporterPreferences(**default_prefs_data)

        return cls(general=general, ai=ai, default=default)


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
        # Note: For standalone testing, you'd need to mock request_context
        # For now, creating directly for demonstration
        preferences = FeedbackPreferences(
            general=GeneralPreferences(
                report_title="Relatório Final - Desafio Web",
                add_report_summary=True,
                online_content=[
                    LearningResource(
                        url="https://developer.mozilla.org/pt-BR/docs/Web/HTML/Element/img",
                        description="Guia completo sobre a tag <img>.",
                        linked_tests=["check_all_images_have_alt"]
                    )
                ]
            ),
            ai=AiReporterPreferences(
                assignment_context="Este é um desafio focado em HTML semântico e CSS responsivo.",
                feedback_persona="Professor Sênior"
            ),
            default=DefaultReporterPreferences(
                category_headers={
                    "base": "✔️ Requisitos Obrigatórios",
                    "penalty": "🚨 Pontos de Atenção"
                }
            )
        )

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