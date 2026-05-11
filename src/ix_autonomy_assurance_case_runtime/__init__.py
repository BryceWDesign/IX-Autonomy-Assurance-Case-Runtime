"""Public package interface for IX-Autonomy-Assurance-Case-Runtime."""

from __future__ import annotations

from ix_autonomy_assurance_case_runtime._version import __version__
from ix_autonomy_assurance_case_runtime.assurance_case import (
    AssuranceCase,
    AssuranceCaseValidationReport,
    AssuranceClaim,
    AssuranceModelError,
    Assumption,
    Control,
    EvidenceLink,
    Hazard,
    Mitigation,
    VerificationCriterion,
)
from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    AutonomyDecisionType,
    ContractDefinition,
    ContractValueError,
    EvidenceStatus,
    HazardSeverity,
    ReviewDisposition,
    RuntimeAuthorityState,
    VerificationResult,
    build_contract_catalog,
)
from ix_autonomy_assurance_case_runtime.project import (
    PROJECT_NAME,
    ProjectIdentity,
    get_project_identity,
)

__all__ = [
    "PROJECT_NAME",
    "AssuranceCase",
    "AssuranceCaseStatus",
    "AssuranceCaseValidationReport",
    "AssuranceClaim",
    "AssuranceModelError",
    "Assumption",
    "AutonomyDecisionType",
    "ContractDefinition",
    "ContractValueError",
    "Control",
    "EvidenceLink",
    "EvidenceStatus",
    "Hazard",
    "HazardSeverity",
    "Mitigation",
    "ProjectIdentity",
    "ReviewDisposition",
    "RuntimeAuthorityState",
    "VerificationCriterion",
    "VerificationResult",
    "__version__",
    "build_contract_catalog",
    "get_project_identity",
]
