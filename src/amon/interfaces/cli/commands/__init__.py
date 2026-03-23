"""CLI command adapters for vNext workspace."""

from .confirmations import handle_workspace_confirmations
from .definitions import handle_workspace_definitions
from .projects import handle_workspace_projects
from .runs import handle_workspace_runs
from .uploads import handle_workspace_uploads

__all__ = [
    "handle_workspace_confirmations",
    "handle_workspace_definitions",
    "handle_workspace_projects",
    "handle_workspace_runs",
    "handle_workspace_uploads",
]
