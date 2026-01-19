from typing import List, Dict
from dataclasses import dataclass, field


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


