"""Validated catalog for registered AI/autonomy assets.

Individual registry records are useful, but the serious prototype needs a layer
that can validate how models, systems, use cases, deployments, evidence bundles,
mission references, scenarios, and telemetry sources fit together. This module
adds that cross-reference boundary without assuming any external database or
official agency registry.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypeVar

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.registry import (
    RegisteredDeployment,
    RegisteredModel,
    RegisteredSystem,
    RegisteredUseCase,
    RegistryLifecycleState,
)

RegistryRecordT = TypeVar("RegistryRecordT")


def _index_by_id(
    records: Iterable[RegistryRecordT],
    id_getter: str,
) -> dict[str, RegistryRecordT]:
    """Index records by ID and reject duplicates."""

    indexed: dict[str, RegistryRecordT] = {}
    for record in records:
        record_id = getattr(record, id_getter)
        if record_id in indexed:
            raise ContractValueError(f"Duplicate registry ID {record_id!r} in {id_getter}.")
        indexed[record_id] = record
    return indexed


class RegistryReferenceType(RuntimeStrEnum):
    """Kinds of registry references the catalog can report."""

    MODEL = "model"
    SYSTEM = "system"
    USE_CASE = "use_case"
    DEPLOYMENT = "deployment"
    ASSURANCE_CASE = "assurance_case"
    EVIDENCE_BUNDLE = "evidence_bundle"
    MISSION_THREAD = "mission_thread"
    MISSION_NEED = "mission_need"
    REQUIREMENT = "requirement"
    SCENARIO = "scenario"
    TELEMETRY_SOURCE = "telemetry_source"


class RegistryFindingSeverity(RuntimeStrEnum):
    """Severity for registry catalog validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_acceptance(self) -> bool:
        """Return whether this finding blocks registry acceptance."""

        return self is RegistryFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class RegistryValidationFinding:
    """One cross-reference or readiness issue found in the registry catalog."""

    finding_id: str
    severity: RegistryFindingSeverity
    message: str
    subject_id: str
    subject_type: RegistryReferenceType
    reference_id: str | None = None
    reference_type: RegistryReferenceType | None = None

    def __post_init__(self) -> None:
        """Validate finding fields so reports are machine-checkable."""

        if not self.finding_id.strip():
            raise ContractValueError("Registry validation finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Registry validation finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Registry validation finding {self.finding_id!r} needs a message."
            )
        if not self.subject_id.strip():
            raise ContractValueError(
                f"Registry validation finding {self.finding_id!r} needs a subject ID."
            )
        if self.reference_id is not None and not self.reference_id.strip():
            raise ContractValueError(
                f"Registry validation finding {self.finding_id!r} has a blank reference ID."
            )
        if (self.reference_id is None) != (self.reference_type is None):
            raise ContractValueError(
                f"Registry validation finding {self.finding_id!r} must pair reference ID "
                "and reference type."
            )


@dataclass(frozen=True, slots=True)
class RegistryValidationReport:
    """Validation summary for a registry catalog."""

    model_count: int
    system_count: int
    use_case_count: int
    deployment_count: int
    findings: tuple[RegistryValidationFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return the number of blocker findings."""

        return sum(1 for finding in self.findings if finding.severity.blocks_acceptance())

    @property
    def warning_count(self) -> int:
        """Return the number of warning findings."""

        return sum(
            1 for finding in self.findings if finding.severity is RegistryFindingSeverity.WARNING
        )

    def is_acceptance_ready(self) -> bool:
        """Return whether the catalog has no registry blockers."""

        return self.blocker_count == 0

    def findings_for_subject(self, subject_id: str) -> tuple[RegistryValidationFinding, ...]:
        """Return findings attached to a specific registry subject."""

        return tuple(finding for finding in self.findings if finding.subject_id == subject_id)

    def summary(self) -> str:
        """Return a concise deterministic validation summary."""

        return (
            "registry: "
            f"{self.model_count} model(s), {self.system_count} system(s), "
            f"{self.use_case_count} use case(s), {self.deployment_count} deployment(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


@dataclass(frozen=True, slots=True)
class RegistryCatalog:
    """Local catalog of registered AI/autonomy assets under assurance review."""

    models: tuple[RegisteredModel, ...] = ()
    systems: tuple[RegisteredSystem, ...] = ()
    use_cases: tuple[RegisteredUseCase, ...] = ()
    deployments: tuple[RegisteredDeployment, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate IDs at construction time."""

        _index_by_id(self.models, "model_id")
        _index_by_id(self.systems, "system_id")
        _index_by_id(self.use_cases, "use_case_id")
        _index_by_id(self.deployments, "deployment_id")

    @property
    def model_ids(self) -> tuple[str, ...]:
        """Return registered model IDs in catalog order."""

        return tuple(model.model_id for model in self.models)

    @property
    def system_ids(self) -> tuple[str, ...]:
        """Return registered system IDs in catalog order."""

        return tuple(system.system_id for system in self.systems)

    @property
    def use_case_ids(self) -> tuple[str, ...]:
        """Return registered use-case IDs in catalog order."""

        return tuple(use_case.use_case_id for use_case in self.use_cases)

    @property
    def deployment_ids(self) -> tuple[str, ...]:
        """Return registered deployment IDs in catalog order."""

        return tuple(deployment.deployment_id for deployment in self.deployments)

    def model_by_id(self, model_id: str) -> RegisteredModel | None:
        """Return a registered model by ID, if present."""

        return _index_by_id(self.models, "model_id").get(model_id)

    def system_by_id(self, system_id: str) -> RegisteredSystem | None:
        """Return a registered system by ID, if present."""

        return _index_by_id(self.systems, "system_id").get(system_id)

    def use_case_by_id(self, use_case_id: str) -> RegisteredUseCase | None:
        """Return a registered use case by ID, if present."""

        return _index_by_id(self.use_cases, "use_case_id").get(use_case_id)

    def deployment_by_id(self, deployment_id: str) -> RegisteredDeployment | None:
        """Return a registered deployment by ID, if present."""

        return _index_by_id(self.deployments, "deployment_id").get(deployment_id)

    def approved_use_cases_for_system(self, system_id: str) -> tuple[RegisteredUseCase, ...]:
        """Return approved use cases tied to a system."""

        return tuple(
            use_case
            for use_case in self.use_cases
            if use_case.system_id == system_id
            and use_case.lifecycle_state is RegistryLifecycleState.APPROVED
        )

    def validate(self) -> RegistryValidationReport:
        """Validate registry cross-references and acceptance readiness."""

        model_by_id = _index_by_id(self.models, "model_id")
        system_by_id = _index_by_id(self.systems, "system_id")
        use_cases_by_system = self._index_use_cases_by_system()
        findings: list[RegistryValidationFinding] = []

        findings.extend(self._validate_system_model_references(model_by_id))
        findings.extend(self._validate_use_case_system_references(system_by_id))
        findings.extend(
            self._validate_deployment_system_references(
                system_by_id=system_by_id,
                use_cases_by_system=use_cases_by_system,
            )
        )
        findings.extend(self._validate_empty_catalog_warning())

        return RegistryValidationReport(
            model_count=len(self.models),
            system_count=len(self.systems),
            use_case_count=len(self.use_cases),
            deployment_count=len(self.deployments),
            findings=tuple(findings),
        )

    def _index_use_cases_by_system(self) -> dict[str, tuple[RegisteredUseCase, ...]]:
        """Index use cases by system ID."""

        grouped: dict[str, list[RegisteredUseCase]] = {}
        for use_case in self.use_cases:
            grouped.setdefault(use_case.system_id, []).append(use_case)
        return {system_id: tuple(records) for system_id, records in grouped.items()}

    def _validate_system_model_references(
        self,
        model_by_id: dict[str, RegisteredModel],
    ) -> tuple[RegistryValidationFinding, ...]:
        """Validate system-to-model references."""

        findings: list[RegistryValidationFinding] = []
        for system in self.systems:
            if not system.model_ids:
                findings.append(
                    RegistryValidationFinding(
                        finding_id=f"system-{system.system_id}-has-no-models",
                        severity=RegistryFindingSeverity.WARNING,
                        message=(
                            "Registered system has no model/component references; this is "
                            "allowed for non-model systems but limits model registry claims."
                        ),
                        subject_id=system.system_id,
                        subject_type=RegistryReferenceType.SYSTEM,
                    )
                )
            for model_id in system.model_ids:
                model = model_by_id.get(model_id)
                if model is None:
                    findings.append(
                        RegistryValidationFinding(
                            finding_id=f"system-{system.system_id}-missing-model-{model_id}",
                            severity=RegistryFindingSeverity.BLOCKER,
                            message="Registered system references a missing model.",
                            subject_id=system.system_id,
                            subject_type=RegistryReferenceType.SYSTEM,
                            reference_id=model_id,
                            reference_type=RegistryReferenceType.MODEL,
                        )
                    )
                    continue
                if (
                    system.lifecycle_state is RegistryLifecycleState.APPROVED
                    and model.lifecycle_state is not RegistryLifecycleState.APPROVED
                ):
                    findings.append(
                        RegistryValidationFinding(
                            finding_id=(
                                f"approved-system-{system.system_id}-uses-unapproved-model-"
                                f"{model_id}"
                            ),
                            severity=RegistryFindingSeverity.BLOCKER,
                            message="Approved systems must not depend on unapproved models.",
                            subject_id=system.system_id,
                            subject_type=RegistryReferenceType.SYSTEM,
                            reference_id=model_id,
                            reference_type=RegistryReferenceType.MODEL,
                        )
                    )
        return tuple(findings)

    def _validate_use_case_system_references(
        self,
        system_by_id: dict[str, RegisteredSystem],
    ) -> tuple[RegistryValidationFinding, ...]:
        """Validate use-case-to-system references."""

        findings: list[RegistryValidationFinding] = []
        for use_case in self.use_cases:
            system = system_by_id.get(use_case.system_id)
            if system is None:
                findings.append(
                    RegistryValidationFinding(
                        finding_id=f"use-case-{use_case.use_case_id}-missing-system",
                        severity=RegistryFindingSeverity.BLOCKER,
                        message="Registered use case references a missing system.",
                        subject_id=use_case.use_case_id,
                        subject_type=RegistryReferenceType.USE_CASE,
                        reference_id=use_case.system_id,
                        reference_type=RegistryReferenceType.SYSTEM,
                    )
                )
                continue
            if (
                use_case.lifecycle_state is RegistryLifecycleState.APPROVED
                and system.lifecycle_state is not RegistryLifecycleState.APPROVED
            ):
                findings.append(
                    RegistryValidationFinding(
                        finding_id=(
                            f"approved-use-case-{use_case.use_case_id}-"
                            "uses-unapproved-system"
                        ),
                        severity=RegistryFindingSeverity.BLOCKER,
                        message="Approved use cases must reference approved systems.",
                        subject_id=use_case.use_case_id,
                        subject_type=RegistryReferenceType.USE_CASE,
                        reference_id=system.system_id,
                        reference_type=RegistryReferenceType.SYSTEM,
                    )
                )
        return tuple(findings)

    def _validate_deployment_system_references(
        self,
        system_by_id: dict[str, RegisteredSystem],
        use_cases_by_system: dict[str, tuple[RegisteredUseCase, ...]],
    ) -> tuple[RegistryValidationFinding, ...]:
        """Validate deployment-to-system and live-operation references."""

        findings: list[RegistryValidationFinding] = []
        for deployment in self.deployments:
            system = system_by_id.get(deployment.system_id)
            if system is None:
                findings.append(
                    RegistryValidationFinding(
                        finding_id=f"deployment-{deployment.deployment_id}-missing-system",
                        severity=RegistryFindingSeverity.BLOCKER,
                        message="Registered deployment references a missing system.",
                        subject_id=deployment.deployment_id,
                        subject_type=RegistryReferenceType.DEPLOYMENT,
                        reference_id=deployment.system_id,
                        reference_type=RegistryReferenceType.SYSTEM,
                    )
                )
                continue
            if (
                deployment.lifecycle_state is RegistryLifecycleState.APPROVED
                and system.lifecycle_state is not RegistryLifecycleState.APPROVED
            ):
                findings.append(
                    RegistryValidationFinding(
                        finding_id=(
                            f"approved-deployment-{deployment.deployment_id}-"
                            "uses-unapproved-system"
                        ),
                        severity=RegistryFindingSeverity.BLOCKER,
                        message="Approved deployments must reference approved systems.",
                        subject_id=deployment.deployment_id,
                        subject_type=RegistryReferenceType.DEPLOYMENT,
                        reference_id=system.system_id,
                        reference_type=RegistryReferenceType.SYSTEM,
                    )
                )
            approved_use_cases = tuple(
                use_case
                for use_case in use_cases_by_system.get(system.system_id, ())
                if use_case.lifecycle_state is RegistryLifecycleState.APPROVED
            )
            if deployment.approved_for_live_operation and not approved_use_cases:
                findings.append(
                    RegistryValidationFinding(
                        finding_id=(
                            f"live-deployment-{deployment.deployment_id}-"
                            "has-no-approved-use-case"
                        ),
                        severity=RegistryFindingSeverity.BLOCKER,
                        message=(
                            "Live-operation deployment needs at least one approved use case "
                            "for its registered system."
                        ),
                        subject_id=deployment.deployment_id,
                        subject_type=RegistryReferenceType.DEPLOYMENT,
                        reference_id=system.system_id,
                        reference_type=RegistryReferenceType.SYSTEM,
                    )
                )
        return tuple(findings)

    def _validate_empty_catalog_warning(self) -> tuple[RegistryValidationFinding, ...]:
        """Warn when the catalog has no registry records at all."""

        if self.models or self.systems or self.use_cases or self.deployments:
            return ()
        return (
            RegistryValidationFinding(
                finding_id="registry-catalog-empty",
                severity=RegistryFindingSeverity.WARNING,
                message="Registry catalog has no records and cannot support inventory claims.",
                subject_id="registry-catalog",
                subject_type=RegistryReferenceType.SYSTEM,
            ),
        )
