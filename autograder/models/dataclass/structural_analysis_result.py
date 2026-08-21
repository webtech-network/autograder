from dataclasses import dataclass, field
from typing import Dict, Optional, Set, TYPE_CHECKING

if TYPE_CHECKING:
    from ast_grep_py import SgRoot

@dataclass
class StructuralAnalysisResult:
    """
    Holds the results of structural analysis for a submission.
    
    Attributes:
        roots: A dictionary mapping filenames to their corresponding ast-grep root nodes.
               If a file could not be parsed, the value is None.
        changed_lines: Changed line numbers supplied for each parsed file.
        available: Whether structural analysis infrastructure was available and attempted.
        reason: Optional reason explaining why analysis was unavailable/skipped.
    """
    roots: Dict[str, Optional['SgRoot']]
    available: bool = True
    reason: Optional[str] = None
    changed_lines: Dict[str, Set[int]] = field(default_factory=dict)
