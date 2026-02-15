from dataclasses import dataclass


@dataclass
class ParamDescription:
    """
    Represents the description of a test function parameter.
    
    Attributes:
        name: The parameter name (e.g., 'html_content', 'tag')
        description: A human-readable description of what the parameter represents
        type: The type of the parameter (e.g., 'string', 'integer', 'list of strings', 'boolean')
    """
    name: str
    description: str
    type: str
