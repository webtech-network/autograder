from dataclasses import dataclass
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ast_grep_py import SgRoot

@dataclass
class StructuralAnalysisResult:
    """
    Holds the results of structural analysis for a submission.
    
    Attributes:
        roots: A dictionary mapping filenames to their corresponding ast-grep root nodes.
               If a file could not be parsed, the value is None.
    """
    roots: Dict[str, Optional['SgRoot']]
