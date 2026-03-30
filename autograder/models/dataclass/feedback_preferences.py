from typing import List, Dict, Optional
from dataclasses import dataclass, field
from autograder.translations import t


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
    report_title: Optional[str] = None # Will default to t("feedback.report_title") if None
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


def _default_category_headers(locale: str = "en") -> Dict[str, str]:
    """Factory function for default category headers."""
    return {
        "base": t("feedback.category.base", locale=locale),
        "bonus": t("feedback.category.bonus", locale=locale),
        "penalty": t("feedback.category.penalty", locale=locale)
    }


@dataclass
class DefaultReporterPreferences:
    """Preferences specific to the Default (template-based) Reporter."""
    category_headers: Dict[str, str] = field(default_factory=dict) # Should be initialized in FeedbackPreferences


@dataclass
class FeedbackPreferences:
    """
    A unified model to store all feedback preferences, including the new
    test-linked learning resources and legacy AI configurations.
    """
    general: GeneralPreferences = field(default_factory=GeneralPreferences)
    ai: AiReporterPreferences = field(default_factory=AiReporterPreferences)
    default: DefaultReporterPreferences = field(default_factory=DefaultReporterPreferences)
    locale: str = "en"

    def __post_init__(self):
        """Initialize defaults based on locale if not provided."""
        if self.general.report_title is None:
            self.general.report_title = t("feedback.report_title", locale=self.locale)
        
        if not self.default.category_headers:
            self.default.category_headers = _default_category_headers(self.locale)


