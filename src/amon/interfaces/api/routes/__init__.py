"""Route adapters for vNext local API."""

from .confirmations import approve_confirmation, list_confirmations, reject_confirmation
from .definitions import create_definition, delete_definition, get_definition, list_definitions, update_definition
from .projects import create_project, delete_project, get_project_summary, list_projects, restore_project, update_project
from .runs import archive_run, cancel_run, create_run, get_run, get_run_events, resume_run
from .uploads import create_upload, delete_upload, get_upload, get_upload_preview, list_uploads, update_upload

__all__ = [
    "approve_confirmation",
    "archive_run",
    "cancel_run",
    "create_definition",
    "create_project",
    "create_run",
    "create_upload",
    "delete_definition",
    "delete_project",
    "delete_upload",
    "get_definition",
    "get_project_summary",
    "get_run",
    "get_run_events",
    "get_upload",
    "get_upload_preview",
    "list_confirmations",
    "list_definitions",
    "list_projects",
    "list_uploads",
    "reject_confirmation",
    "restore_project",
    "resume_run",
    "update_definition",
    "update_project",
    "update_upload",
]
