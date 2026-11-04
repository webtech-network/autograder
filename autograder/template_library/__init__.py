"""The built-in template registry: the only one.

Identifiers are the values accepted in a definition's ``templates`` list.
Instances are created once and shared: evaluators are stateless. Trusted
callers add or override templates per call with ``templates={identifier:
instance}``; that never changes this registry.
"""
from types import MappingProxyType
from typing import Mapping

from autograder.models.abstract.template import Template
from autograder.template_library.api_testing import ApiTestingTemplate
from autograder.template_library.input_output import InputOutputTemplate
from autograder.template_library.static_analysis import StaticAnalysisTemplate
from autograder.template_library.web_dev.template import WebDevTemplate

BUILTIN_TEMPLATES: Mapping[str, Template] = MappingProxyType({
    "webdev": WebDevTemplate(),
    "api": ApiTestingTemplate(),
    "input_output": InputOutputTemplate(),
    "static_analysis": StaticAnalysisTemplate(),
})

__all__ = ["BUILTIN_TEMPLATES"]
