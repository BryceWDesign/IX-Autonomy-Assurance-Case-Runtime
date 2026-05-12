"""Evidence coverage validation for the local registry catalog.

Registry records can name evidence bundle IDs, but registry readiness requires a
separate check that those referenced bundles actually exist, have valid integrity,
and are tied to the right subject. This module adds that evidence-coverage layer
without adding signatures or external trust claims yet.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.registry import RegistryLifecycleState
from ix_autonomy_assurance_case_runtime.registry_catalog import (
    RegistryCatalog,
    RegistryReferenceType,
)


class RegistryEvidenceFindingSeverity(RuntimeStrEnum):
    """Severity for registry evidence coverage findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_acceptance(self) -> bool:
        """Return whether this finding blocks registry evidence acceptance."""

        return self is RegistryEvidenceFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class RegistryEvidenceReference:
    """One evidence bundle reference declared by a registry subject."""

    subject_id: str
    subject_type: RegistryReferenceType
    bundle_id: str
    expected_case_id: str | None = None
    expected_scenario_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate reference records."""

        if not self.subject_id.strip():
            raise ContractValueError("Registry evidence subject_id must not be blank.")
        if self.subject_id != self.subject_id.strip():
            raise ContractValueError(
                "Registry evidence subject_id must not contain edge whitespace."
            )
        if not self.bundle_id.strip():
            raise ContractValueError("Registry evidence bundle_id must not be blank.")
        if self.bundle_id != self.bundle_id.strip():
            raise ContractValueError(
                "Registry evidence bundle_id must not contain edge whitespace."
            )
        if self.expected_case_id is not None and not self.expected_case_id.strip():
            raise ContractValueError("Registry evidence expected_case_id must not be blank.")
        for scenario_id in self.expected_scenario_ids:
            if not scenario_id.strip():
                raise ContractValueError(
                    "Registry evidence expected_scenario_ids must not contain blanks."
                )
        if len(self.expected_scenario_ids) != len(set(self.expected_scenario_ids)):
            raise ContractValueError(
                "Registry evidence expected_scenario_ids must not contain duplicates."
            )


@dataclass(frozen=True, slots=True)
class RegistryEvidenceFinding:
    """One evidence coverage issue found for registry-linked evidence."""

    finding_id: str
    severity: RegistryEvidenceFindingSeverity
    message: str
    subject_id: str
    subject_type: RegistryReferenceType
    bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate finding records so they can be exported later."""

        if not self.finding_id.strip():
            raise ContractValueError("Registry evidence finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Registry evidence finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Registry evidence finding {self.finding_id!r} needs a message."
            )
        if not self.subject_id.strip():
            raise ContractValueError(
                f"Registry evidence finding {self.finding_id!r} needs a subject ID."
            )
        if self.bundle_id is not None and not self.bundle_id.strip():
            raise ContractValueError(
                f"Registry evidence finding {self.finding_id!r} has a blank bundle ID."
            )


@dataclass(frozen=True, slots=True)
class RegistryEvidenceCoverageReport:
    """Evidence coverage summary for a registry catalog."""

    referenced_bundle_count: int
    provided_bundle_count: int
    findings: tuple[RegistryEvidenceFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return the number of evidence coverage blockers."""

        return sum(1 for finding in self.findings if finding.severity.blocks_acceptance())

    @property
    def warning_count(self) -> int:
        """Return the number of evidence coverage warnings."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is RegistryEvidenceFindingSeverity.WARNING
        )

    def is_coverage_ready(self) -> bool:
        """Return whether registry evidence coverage has no blockers."""

        return self.blocker_count == 0

    def findings_for_subject(self, subject_id: str) -> tuple[RegistryEvidenceFinding, ...]:
        """Return evidence findings for a registry subject."""

        return tuple(finding for finding in self.findings if finding.subject_id == subject_id)

    def summary(self) -> str:
        """Return a deterministic evidence coverage summary."""

        return (
            "registry-evidence: "
            f"{self.referenced_bundle_count} referenced bundle(s), "
            f"{self.provided_bundle_count} provided bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


def collect_registry_evidence_references(
    catalog: RegistryCatalog,
) -> tuple[RegistryEvidenceReference, ...]:
    """Collect all evidence bundle references declared by registry records."""

    references: list[RegistryEvidenceReference] = []

    for model in catalog.models:
        references.extend(
            RegistryEvidenceReference(
                subject_id=model.model_id,
                subject_type=RegistryReferenceType.MODEL,
                bundle_id=bundle_id,
            )
            for bundle_id in model.evidence_bundle_ids
        )

    for use_case in catalog.use_cases:
        references.extend(
            RegistryEvidenceReference(
                subject_id=use_case.use_case_id,
                subject_type=RegistryReferenceType.USE_CASE,
                bundle_id=bundle_id,
            )
            for bundle_id in use_case.evidence_bundle_ids
        )

    for deployment in catalog.deployments:
        references.extend(
            RegistryEvidenceReference(
                subject_id=deployment.deployment_id,
                subject_type=RegistryReferenceType.DEPLOYMENT,
                bundle_id=bundle_id,
                expected_scenario_ids=deployment.scenario_ids,
            )
            for bundle_id in deployment.evidence_bundle_ids
        )

    return tuple(references)


class RegistryEvidenceValidator:
    """Validate evidence coverage for registry-linked evidence bundles."""

    def __init__(self, bundles: Iterable[EvidenceBundle]) -> None:
        """Create a validator with provided evidence bundles."""

        self._bundle_by_id = self._index_bundles(bundles)

    def validate(self, catalog: RegistryCatalog) -> RegistryEvidenceCoverageReport:
        """Validate evidence references declared by a registry catalog."""

        references = collect_registry_evidence_references(catalog)
        findings: list[RegistryEvidenceFinding] = []
        findings.extend(self._validate_references_exist(references))
        findings.extend(self._validate_provided_bundle_integrity(catalog))
        findings.extend(self._validate_approved_records_reference_evidence(catalog))

        return RegistryEvidenceCoverageReport(
            referenced_bundle_count=len({reference.bundle_id for reference in references}),
            provided_bundle_count=len(self._bundle_by_id),
            findings=tuple(findings),
        )

    @staticmethod
    def _index_bundles(bundles: Iterable[EvidenceBundle]) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate bundle IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(f"Duplicate evidence bundle ID {bundle.bundle_id!r}.")
            indexed[bundle.bundle_id] = bundle
        return indexed

    def _validate_references_exist(
        self,
        references: tuple[RegistryEvidenceReference, ...],
    ) -> tuple[RegistryEvidenceFinding, ...]:
        """Validate declared references against provided bundles."""

        findings: list[RegistryEvidenceFinding] = []
        for reference in references:
            bundle = self._bundle_by_id.get(reference.bundle_id)
            if bundle is None:
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=(
                            f"{reference.subject_type.value}-{reference.subject_id}-"
                            f"missing-evidence-{reference.bundle_id}"
                        ),
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message="Registry subject references a missing evidence bundle.",
                        subject_id=reference.subject_id,
                        subject_type=reference.subject_type,
                        bundle_id=reference.bundle_id,
                    )
                )
                continue
            if (
                reference.expected_case_id is not None
                and bundle.case_id != reference.expected_case_id
            ):
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=(
                            f"{reference.subject_type.value}-{reference.subject_id}-"
                            f"case-mismatch-{reference.bundle_id}"
                        ),
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message="Evidence bundle case ID does not match registry expectation.",
                        subject_id=reference.subject_id,
                        subject_type=reference.subject_type,
                        bundle_id=reference.bundle_id,
                    )
                )
            if (
                reference.expected_scenario_ids
                and bundle.scenario_id not in reference.expected_scenario_ids
            ):
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=(
                            f"{reference.subject_type.value}-{reference.subject_id}-"
                            f"scenario-mismatch-{reference.bundle_id}"
                        ),
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message=(
                            "Evidence bundle scenario ID does not match a declared deployment "
                            "scenario."
                        ),
                        subject_id=reference.subject_id,
                        subject_type=reference.subject_type,
                        bundle_id=reference.bundle_id,
                    )
                )
        return tuple(findings)

    def _validate_provided_bundle_integrity(
        self,
        catalog: RegistryCatalog,
    ) -> tuple[RegistryEvidenceFinding, ...]:
        """Validate integrity for every provided bundle that the catalog references."""

        referenced = collect_registry_evidence_references(catalog)
        referenced_ids = {reference.bundle_id for reference in referenced}
        subject_by_bundle_id = {reference.bundle_id: reference for reference in referenced}
        findings: list[RegistryEvidenceFinding] = []
        for bundle_id in sorted(referenced_ids):
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                continue
            validation = bundle.validate_integrity()
            reference = subject_by_bundle_id[bundle_id]
            for error in validation.errors:
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message=error,
                        subject_id=reference.subject_id,
                        subject_type=reference.subject_type,
                        bundle_id=bundle_id,
                    )
                )
            for warning in validation.warnings:
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning",
                        severity=RegistryEvidenceFindingSeverity.WARNING,
                        message=warning,
                        subject_id=reference.subject_id,
                        subject_type=reference.subject_type,
                        bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_approved_records_reference_evidence(
        catalog: RegistryCatalog,
    ) -> tuple[RegistryEvidenceFinding, ...]:
        """Validate that approved registry records still expose evidence references."""

        findings: list[RegistryEvidenceFinding] = []
        for model in catalog.models:
            if (
                model.lifecycle_state is RegistryLifecycleState.APPROVED
                and not model.evidence_bundle_ids
            ):
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=f"approved-model-{model.model_id}-has-no-evidence",
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message="Approved model has no evidence bundle references.",
                        subject_id=model.model_id,
                        subject_type=RegistryReferenceType.MODEL,
                    )
                )
        for use_case in catalog.use_cases:
            if (
                use_case.lifecycle_state is RegistryLifecycleState.APPROVED
                and not use_case.evidence_bundle_ids
            ):
                findings.append(
                    RegistryEvidenceFinding(
                        finding_id=f"approved-use-case-{use_case.use_case_id}-has-no-evidence",
                        severity=RegistryEvidenceFindingSeverity.BLOCKER,
                        message="Approved use case has no evidence bundle references.",
                        subject_id=use_case.use_case_id,
                        subject_type=RegistryReferenceType.USE_CASE,
                    )
                )
        return tuple(findings)
