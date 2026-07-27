"""AI-based feedback reporter — not yet implemented."""


class AiReporter:
    """
    Reporter that generates feedback using an AI model.

    This class is not yet implemented. Instantiating it raises
    NotImplementedError immediately so that misconfigured pipelines
    fail at build time (in ReporterService.__init__) rather than
    silently succeeding and crashing only when generate_report() is called.
    """

    def __init__(self):
        raise NotImplementedError(
            "AiReporter is not yet implemented. "
            "Use feedback_mode='default' or leave feedback_mode unset."
        )

    def generate_report(self, focus, result_tree, preferences=None):
        raise NotImplementedError(
            "AiReporter is not yet implemented. "
            "Use feedback_mode='default' or leave feedback_mode unset."
        )
