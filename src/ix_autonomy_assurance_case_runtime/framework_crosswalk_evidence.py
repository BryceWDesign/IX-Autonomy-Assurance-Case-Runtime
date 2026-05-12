"""Evidence coverage validation for framework crosswalk mappings.

Framework crosswalks are only useful when their alignment claims are backed by
real local evidence. This module validates that mapped controls reference
provided evidence bundles, that referenced bundles pass integrity checks, and
that satisfied mappings include evidence kinds expected by their control
objective. It does not claim official compliance, certification, endorsement, or
authority to operate.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.framework_crosswalk import (
    ControlCoverageStatus,
    ControlMapping,
    ControlObjective,
    FrameworkCrosswalk,
)


class FrameworkEvidenceFindingSeverity(RuntimeStrEnum):
    """Severity for framework evidence coverage findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_alignment(self) -> bool:
        """Return whether this finding blocks evidence-backed alignment."""

        return self is FrameworkEvidenceFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class FrameworkEvidenceReference:
    """One evidence bundle reference declared by a control mapping."""

    control_id: str
    mapping_id: str
    bundle_id: str
    expected_evidence_kinds: tuple[str, ...]
    coverage_status: ControlCoverageStatus

    def __post_init__(self) -> None:
        """Validate framework evidence reference fields."""

        if not self.control_id.strip():
            raise ContractValueError("Framework evidence control_id must not be blank.")
        if self.control_id != self.control_id.strip():
            raise ContractValueError(
                "Framework evidence control_id must not contain edge whitespace."
            )
        if not self.mapping_id.strip():
            raise ContractValueError("Framework evidence mapping_id must not be blank.")
        if self.mapping_id != self.mapping_id.strip():
            raise ContractValueError(
                "Framework evidence mapping_id must not contain edge whitespace."
            )
        if not self.bundle_id.strip():
            raise ContractValueError("Framework evidence bundle_id must not be blank.")
        if self.bundle_id != self.bundle_id.strip():
            raise ContractValueError(
                "Framework evidence bundle_id must not contain edge whitespace."
            )
        for evidence_kind in self.expected_evidence_kinds:
            if not evidence_kind.strip():
                raise ContractValueError(
                    "Framework evidence expected_evidence_kinds must not contain blanks."
                )
        if len(self.expected_evidence_kinds) != len(set(self.expected_evidence_kinds)):
            raise ContractValueError(
                "Framework evidence expected_evidence_kinds must not contain duplicates."
            )


@dataclass(frozen=True, slots=True)
class FrameworkEvidenceFinding:
    """One evidence coverage finding for a framework control mapping."""

    finding_id: str
    severity: FrameworkEvidenceFindingSeverity
    message: str
    control_id: str | None = None
    mapping_id: str | None = None
    bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate evidence coverage finding fields."""

        if not self.finding_id.strip():
            raise ContractValueError("Framework evidence finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Framework evidence finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Framework evidence finding {self.finding_id!r} needs a message."
            )
        if self.control_id is not None and not self.control_id.strip():
            raise ContractValueError(
                f"Framework evidence finding {self.finding_id!r} has a blank control ID."
            )
        if self.mapping_id is not None and not self.mapping_id.strip():
            raise ContractValueError(
                f"Framework evidence finding {self.finding_id!r} has a blank mapping ID."
            )
        if self.bundle_id is not None and not self.bundle_id.strip():
            raise ContractValueError(
                f"Framework evidence finding {self.finding_id!r} has a blank bundle ID."
            )


@dataclass(frozen=True, slots=True)
class FrameworkEvidenceCoverageReport:
    """Evidence coverage report for framework control mappings."""

    referenced_bundle_count: int
    provided_bundle_count: int
    findings: tuple[FrameworkEvidenceFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return blocker count for framework evidence coverage."""

        return sum(1 for finding in self.findings if finding.severity.blocks_alignment())

    @property
    def warning_count(self) -> int:
        """Return warning count for framework evidence coverage."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is FrameworkEvidenceFindingSeverity.WARNING
        )

    def is_coverage_ready(self) -> bool:
        """Return whether framework evidence coverage has no blockers."""

        return self.blocker_count == 0

    def findings_for_control(self, control_id: str) -> tuple[FrameworkEvidenceFinding, ...]:
        """Return evidence findings for a control objective."""

        return tuple(finding for finding in self.findings if finding.control_id == control_id)

    def findings_for_mapping(self, mapping_id: str) -> tuple[FrameworkEvidenceFinding, ...]:
        """Return evidence findings for a control mapping."""

        return tuple(finding for finding in self.findings if finding.mapping_id == mapping_id)

    def summary(self) -> str:
        """Return a deterministic evidence coverage summary."""

        return (
            "framework-evidence: "
            f"{self.referenced_bundle_count} referenced bundle(s), "
            f"{self.provided_bundle_count} provided bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


def collect_framework_evidence_references(
    crosswalk: FrameworkCrosswalk,
) -> tuple[FrameworkEvidenceReference, ...]:
    """Collect evidence bundle references declared by framework control mappings."""

    objective_by_id = {objective.control_id: objective for objective in crosswalk.objectives}
    references: list[FrameworkEvidenceReference] = []
    for mapping in crosswalk.mappings:
        objective = objective_by_id.get(mapping.control_id)
        expected_evidence_kinds = (
            objective.expected_evidence_kinds if objective is not None else ()
        )
        references.extend(
            FrameworkEvidenceReference(
                control_id=mapping.control_id,
                mapping_id=mapping.mapping_id,
                bundle_id=bundle_id,
                expected_evidence_kinds=expected_evidence_kinds,
                coverage_status=mapping.coverage_status,
            )
            for bundle_id in mapping.evidence_bundle_ids
        )
    return tuple(references)


class FrameworkEvidenceValidator:
    """Validate evidence coverage for framework control mappings."""

    def __init__(self, bundles: Iterable[EvidenceBundle]) -> None:
        """Create a validator with available evidence bundles."""

        self._bundle_by_id = self._index_bundles(bundles)

    def validate(self, crosswalk: FrameworkCrosswalk) -> FrameworkEvidenceCoverageReport:
        """Validate framework mapping evidence references and evidence integrity."""

        objective_by_id = {objective.control_id: objective for objective in crosswalk.objectives}
        references = collect_framework_evidence_references(crosswalk)
        findings: list[FrameworkEvidenceFinding] = []

        findings.extend(
            self._validate_mapping_evidence_required(
                objectives=objective_by_id,
                mappings=crosswalk.mappings,
            )
        )
        findings.extend(self._validate_references_exist_and_match_expected_kinds(references))
        findings.extend(self._validate_referenced_bundle_integrity(references))

        return FrameworkEvidenceCoverageReport(
            referenced_bundle_count=len({reference.bundle_id for reference in references}),
            provided_bundle_count=len(self._bundle_by_id),
            findings=tuple(findings),
        )

    @staticmethod
    def _index_bundles(bundles: Iterable[EvidenceBundle]) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(f"Duplicate evidence bundle ID {bundle.bundle_id!r}.")
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_mapping_evidence_required(
        objectives: dict[str, ControlObjective],
        mappings: tuple[ControlMapping, ...],
    ) -> tuple[FrameworkEvidenceFinding, ...]:
        """Validate that mappings include evidence when their status requires it."""

        findings: list[FrameworkEvidenceFinding] = []
        for mapping in mappings:
            objective = objectives.get(mapping.control_id)
            if objective is None:
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-missing-control",
                        severity=FrameworkEvidenceFindingSeverity.BLOCKER,
                        message="Control mapping references a missing control objective.",
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
                continue

            if (
                mapping.coverage_status is ControlCoverageStatus.PARTIAL
                and not mapping.evidence_bundle_ids
            ):
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-partial-without-evidence",
                        severity=FrameworkEvidenceFindingSeverity.WARNING,
                        message=(
                            "Partial framework coverage has no evidence bundle reference; "
                            "the mapping may describe intent but cannot yet support strong review."
                        ),
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
            if (
                mapping.coverage_status is ControlCoverageStatus.SATISFIED
                and objective.expected_evidence_kinds
                and not mapping.evidence_bundle_ids
            ):
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-satisfied-without-evidence",
                        severity=FrameworkEvidenceFindingSeverity.BLOCKER,
                        message="Satisfied framework coverage requires evidence bundle references.",
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
        return tuple(findings)

    def _validate_references_exist_and_match_expected_kinds(
        self,
        references: tuple[FrameworkEvidenceReference, ...],
    ) -> tuple[FrameworkEvidenceFinding, ...]:
        """Validate references against provided bundles and expected evidence kinds."""

        findings: list[FrameworkEvidenceFinding] = []
        for reference in references:
            bundle = self._bundle_by_id.get(reference.bundle_id)
            if bundle is None:
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"mapping-{reference.mapping_id}-missing-evidence-{reference.bundle_id}",
                        severity=FrameworkEvidenceFindingSeverity.BLOCKER,
                        message="Framework mapping references a missing evidence bundle.",
                        control_id=reference.control_id,
                        mapping_id=reference.mapping_id,
                        bundle_id=reference.bundle_id,
                    )
                )
                continue

            missing_kinds = _missing_expected_evidence_kinds(
                bundle=bundle,
                expected_evidence_kinds=reference.expected_evidence_kinds,
            )
            if missing_kinds:
                severity = (
                    FrameworkEvidenceFindingSeverity.BLOCKER
                    if reference.coverage_status is ControlCoverageStatus.SATISFIED
                    else FrameworkEvidenceFindingSeverity.WARNING
                )
                for evidence_kind in missing_kinds:
                    findings.append(
                        FrameworkEvidenceFinding(
                            finding_id=(
                                f"mapping-{reference.mapping_id}-evidence-"
                                f"{reference.bundle_id}-missing-kind-{evidence_kind}"
                            ),
                            severity=severity,
                            message=(
                                f"Evidence bundle does not include expected evidence kind "
                                f"{evidence_kind!r}."
                            ),
                            control_id=reference.control_id,
                            mapping_id=reference.mapping_id,
                            bundle_id=reference.bundle_id,
                        )
                    )
        return tuple(findings)

    def _validate_referenced_bundle_integrity(
        self,
        references: tuple[FrameworkEvidenceReference, ...],
    ) -> tuple[FrameworkEvidenceFinding, ...]:
        """Validate integrity of referenced bundles."""

        reference_by_bundle_id = {reference.bundle_id: reference for reference in references}
        findings: list[FrameworkEvidenceFinding] = []
        for bundle_id in sorted(reference_by_bundle_id):
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                continue
            reference = reference_by_bundle_id[bundle_id]
            validation = bundle.validate_integrity()
            for error in validation.errors:
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=FrameworkEvidenceFindingSeverity.BLOCKER,
                        message=error,
                        control_id=reference.control_id,
                        mapping_id=reference.mapping_id,
                        bundle_id=bundle_id,
                    )
                )
            for warning in validation.warnings:
                findings.append(
                    FrameworkEvidenceFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning",
                        severity=FrameworkEvidenceFindingSeverity.WARNING,
                        message=warning,
                        control_id=reference.control_id,
                        mapping_id=reference.mapping_id,
                        bundle_id=bundle_id,
                    )
                )
        return tuple(findings)


def _missing_expected_evidence_kinds(
    bundle: EvidenceBundle,
    expected_evidence_kinds: tuple[str, ...],
) -> tuple[str, ...]:
    """Return expected evidence kinds not present in a bundle."""

    if not expected_evidence_kinds:
        return ()
    present_kinds = {record.kind for record in bundle.records}
    return tuple(
        evidence_kind
        for evidence_kind in expected_evidence_kinds
        if evidence_kind not in present_kinds
    )
