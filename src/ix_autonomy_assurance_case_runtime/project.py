"""Project identity primitives.

This module intentionally contains only stable project metadata. It gives the
package a typed, importable foundation before the assurance-case runtime modules
are introduced in later commits.
"""

from __future__ import annotations

from dataclasses import dataclass

PROJECT_NAME = "IX-Autonomy-Assurance-Case-Runtime"


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    """Stable identity fields for the assurance-case runtime package."""

    repository_name: str
    package_name: str
    mission: str
    license_spdx: str
    python_package: str


def get_project_identity() -> ProjectIdentity:
    """Return the public identity of the project.

    The values here are intentionally deterministic so tests, package metadata,
    and future generated reports can agree on the same canonical project name.
    """

    return ProjectIdentity(
        repository_name=PROJECT_NAME,
        package_name="ix-autonomy-assurance-case-runtime",
        mission=(
            "Provide a Trusted Autonomy T&E assurance-case runtime for "
            "evidence-backed AI/autonomous system evaluation."
        ),
        license_spdx="Apache-2.0",
        python_package="ix_autonomy_assurance_case_runtime",
    )
