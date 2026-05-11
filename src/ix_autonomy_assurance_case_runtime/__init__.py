"""Public package interface for IX-Autonomy-Assurance-Case-Runtime."""

from __future__ import annotations

from ix_autonomy_assurance_case_runtime._version import __version__
from ix_autonomy_assurance_case_runtime.project import (
    PROJECT_NAME,
    ProjectIdentity,
    get_project_identity,
)

__all__ = [
    "PROJECT_NAME",
    "ProjectIdentity",
    "__version__",
    "get_project_identity",
]
