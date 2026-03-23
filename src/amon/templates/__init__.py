"""Workflow template library for Amon vNext."""

from .instantiate import TemplateInstantiation, instantiate_builtin_template
from .library import BuiltinTemplate, TemplateLibrary

__all__ = [
    "BuiltinTemplate",
    "TemplateInstantiation",
    "TemplateLibrary",
    "instantiate_builtin_template",
]
