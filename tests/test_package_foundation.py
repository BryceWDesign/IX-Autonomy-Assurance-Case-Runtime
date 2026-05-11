from __future__ import annotations

from ix_autonomy_assurance_case_runtime import (
    PROJECT_NAME,
    ProjectIdentity,
    __version__,
    get_project_identity,
)


def test_project_identity_is_canonical() -> None:
    identity = get_project_identity()

    assert isinstance(identity, ProjectIdentity)
    assert identity.repository_name == "IX-Autonomy-Assurance-Case-Runtime"
    assert identity.repository_name == PROJECT_NAME
    assert identity.package_name == "ix-autonomy-assurance-case-runtime"
    assert identity.license_spdx == "Apache-2.0"
    assert identity.python_package == "ix_autonomy_assurance_case_runtime"


def test_project_identity_mission_states_runtime_scope() -> None:
    identity = get_project_identity()

    assert "Trusted Autonomy T&E" in identity.mission
    assert "assurance-case runtime" in identity.mission
    assert "evidence-backed" in identity.mission


def test_package_version_is_initial_alpha_version() -> None:
    assert __version__ == "0.1.0"
