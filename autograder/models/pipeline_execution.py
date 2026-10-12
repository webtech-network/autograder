"""Return envelope for the supported build_pipeline(...).run(...) facade."""
from dataclasses import dataclass
from autograder.models.contracts.outcome import TerminalOutcome


@dataclass(frozen=True)
class PipelineExecution:
    """A finalized artifact, with no mutable runtime state or resources."""
    outcome: TerminalOutcome
