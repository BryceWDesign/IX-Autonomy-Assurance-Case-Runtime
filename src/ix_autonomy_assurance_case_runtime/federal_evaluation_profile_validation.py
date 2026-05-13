"""Federal evaluation profile validation.

Federal evaluation profiles map local prototype capabilities, artifacts, and
evidence bundles to reviewer concerns that are recognizable in federal, IC, DoD,
trusted-autonomy, T&E, and assurance-case contexts. This validator checks whether
the profile covers required core concerns, is evidence-backed, and avoids
official acceptance claims.

The checks are local prototype checks only. They do not claim certification,
authority to operate, deployment approval, official endorsement, procurement
acceptance, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile import (
    EvaluationAlignmentStatus,
    FederalEvaluationProfile,
    FederalReviewConcern,
)

REQUIRED_CORE_EVALUATION_CONCERNS: tuple[FederalReviewConcern, ...] = (
    FederalReviewConcern.MISSION_TRACEABILITY,
    FederalReviewConcern.REQUIREMENT_TO_EVIDENCE,
    FederalReviewConcern.HAZARD_CONTROL_CLOSURE,
    FederalReviewConcern.BOUNDED_RUNTIME_ACTION,
    FederalReviewConcern.TELEMETRY_REPLAYABILITY,
)


class FederalEvaluationValidationFindingSeverity(RuntimeStrEnum):
    """Severity for federal evaluation profile validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_evaluation_readiness(self) -> bool:
        """Return whether this finding blocks evaluation readiness."""

        return self is FederalEvaluationValidationFindingSeverity.BLOCKER


class FederalEvaluationValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced a federal evaluation validation finding."""

    PROFILE = "profile"
    MAPPING = "mapping"
    CONCERN = "concern"
    CAPABILITY = "capability"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    DISCLAIMER = "disclaimer"


@dataclass(frozen=True, slots=True)
class FederalEvaluationValidationFinding:
    """One federal evaluation profile validation finding."""

    finding_id: str
    severity: FederalEvaluationValidationFindingSeverity
    source: FederalEvaluationValidationFindingSource
    message: str
    profile_id: str | None = None
    mapping_id: str | None = None
    concern: FederalReviewConcern | None = None
    capability_id: str | None = None
    artifact_id: str | None = None
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate federal evaluation validation finding fields."""

        _require_identifier(self.finding_id, "federal evaluation validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Federal evaluation validation finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("profile_id", self.profile_id),
            ("mapping_id", self.mapping_id),
            ("capability_id", self.capability_id),
            ("artifact_id", self.artifact_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class FederalEvaluationValidationReport:
    """Validation report for one federal evaluation profile."""

    profile_id: str
    mapping_count: int
    concern_count: int
    core_concern_count: int
    completed_capability_count: int
    artifact_count: int
    evidence_bundle_count: int
    findings: tuple[FederalEvaluationValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate federal evaluation validation report counters."""

        _require_identifier(self.profile_id, "profile_id")
        for field_name, value in (
            ("mapping_count", self.mapping_count),
            ("concern_count", self.concern_count),
            ("core_concern_count", self.core_concern_count),
            ("completed_capability_count", self.completed_capability_count),
            ("artifact_count", self.artifact_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(
            finding.severity.blocks_evaluation_readiness() for finding in self.findings
        )

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is FederalEvaluationValidationFindingSeverity.WARNING
        )

    def is_evaluation_ready(self) -> bool:
        """Return whether federal evaluation profile validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_mapping(
        self,
        mapping_id: str,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Return findings for a mapping ID."""

        return tuple(finding for finding in self.findings if finding.mapping_id == mapping_id)

    def findings_for_concern(
        self,
        concern: FederalReviewConcern,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Return findings for a review concern."""

        return tuple(finding for finding in self.findings if finding.concern is concern)

    def findings_for_capability(
        self,
        capability_id: str,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Return findings for a capability ID."""

        return tuple(
            finding for finding in self.findings if finding.capability_id == capability_id
        )

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic federal evaluation validation summary."""

        return (
            f"federal-evaluation-validation: {self.profile_id} "
            f"({self.mapping_count} mapping(s), {self.concern_count} concern(s), "
            f"{self.core_concern_count} core concern(s), "
            f"{self.completed_capability_count} completed capability(s), "
            f"{self.artifact_count} artifact(s), "
            f"{self.evidence_bundle_count} evidence bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class FederalEvaluationProfileValidator:
    """Validate federal-style evaluation profiles."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle] = ()) -> None:
        """Create a federal evaluation profile validator."""

        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)

    def validate(
        self,
        profile: FederalEvaluationProfile,
    ) -> FederalEvaluationValidationReport:
        """Validate one federal evaluation profile."""

        findings = (
            self._validate_required_concerns(profile)
            + self._validate_mappings(profile)
            + self._validate_evidence(profile)
            + self._validate_disclaimer(profile)
        )
        return FederalEvaluationValidationReport(
            profile_id=profile.profile_id,
            mapping_count=len(profile.concern_mappings),
            concern_count=len(profile.concern_values()),
            core_concern_count=len(profile.core_t_and_e_concern_values()),
            completed_capability_count=len(profile.completed_capability_ids),
            artifact_count=len(profile.available_artifact_ids),
            evidence_bundle_count=len(profile.available_evidence_bundle_ids),
            findings=findings,
        )

    @staticmethod
    def _index_evidence_bundles(
        bundles: Iterable[EvidenceBundle],
    ) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(
                    f"Duplicate federal evaluation evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_required_concerns(
        profile: FederalEvaluationProfile,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Validate required core federal/T&E concern coverage."""

        findings: list[FederalEvaluationValidationFinding] = []
        present_concerns = {mapping.concern for mapping in profile.concern_mappings}
        for concern in REQUIRED_CORE_EVALUATION_CONCERNS:
            if concern in present_concerns:
                continue
            findings.append(
                FederalEvaluationValidationFinding(
                    finding_id=f"profile-{profile.profile_id}-missing-{concern.value}",
                    severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                    source=FederalEvaluationValidationFindingSource.CONCERN,
                    message=(
                        "Federal evaluation profile is missing a required core "
                        "test/evaluation concern."
                    ),
                    profile_id=profile.profile_id,
                    concern=concern,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_mappings(
        profile: FederalEvaluationProfile,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Validate concern mapping satisfaction and required references."""

        findings: list[FederalEvaluationValidationFinding] = []
        for mapping in profile.concern_mappings:
            if mapping.status.blocks_acceptance():
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-status-blocks",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.MAPPING,
                        message="Federal evaluation concern mapping status blocks acceptance.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                    )
                )
            elif mapping.status is EvaluationAlignmentStatus.PARTIAL:
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-status-partial",
                        severity=FederalEvaluationValidationFindingSeverity.WARNING,
                        source=FederalEvaluationValidationFindingSource.MAPPING,
                        message="Federal evaluation concern mapping is only partially aligned.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                    )
                )

            for capability_id in mapping.missing_capability_ids(
                profile.completed_capability_ids
            ):
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=(
                            f"mapping-{mapping.mapping_id}-capability-"
                            f"{capability_id}-missing"
                        ),
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.CAPABILITY,
                        message="Required capability is missing from the profile rollup.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                        capability_id=capability_id,
                    )
                )

            for artifact_id in mapping.missing_artifact_ids(profile.available_artifact_ids):
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-artifact-{artifact_id}-missing",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.ARTIFACT,
                        message="Required artifact is missing from the profile package.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                        artifact_id=artifact_id,
                    )
                )

            for bundle_id in mapping.missing_evidence_bundle_ids(
                profile.available_evidence_bundle_ids
            ):
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-evidence-{bundle_id}-missing",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.EVIDENCE,
                        message="Required evidence bundle is missing from the profile package.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                        evidence_bundle_id=bundle_id,
                    )
                )

            if (
                mapping.concern.is_core_t_and_e_concern()
                and not mapping.evidence_bundle_ids
            ):
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-core-no-evidence",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.EVIDENCE,
                        message="Core T&E concern mappings require evidence bundle links.",
                        profile_id=profile.profile_id,
                        mapping_id=mapping.mapping_id,
                        concern=mapping.concern,
                    )
                )

        return tuple(findings)

    def _validate_evidence(
        self,
        profile: FederalEvaluationProfile,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Validate available evidence bundle existence and integrity."""

        findings: list[FederalEvaluationValidationFinding] = []
        for bundle_id in profile.available_evidence_bundle_ids:
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.EVIDENCE,
                        message="Federal evaluation profile references a missing evidence bundle.",
                        profile_id=profile.profile_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue

            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                        source=FederalEvaluationValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        profile_id=profile.profile_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    FederalEvaluationValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=FederalEvaluationValidationFindingSeverity.WARNING,
                        source=FederalEvaluationValidationFindingSource.EVIDENCE,
                        message=warning,
                        profile_id=profile.profile_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_disclaimer(
        profile: FederalEvaluationProfile,
    ) -> tuple[FederalEvaluationValidationFinding, ...]:
        """Validate non-official evaluation profile disclaimer posture."""

        if profile.disclaimer_is_bounded():
            return ()
        return (
            FederalEvaluationValidationFinding(
                finding_id=f"profile-{profile.profile_id}-disclaimer-weak",
                severity=FederalEvaluationValidationFindingSeverity.BLOCKER,
                source=FederalEvaluationValidationFindingSource.DISCLAIMER,
                message=(
                    "Federal evaluation profile disclaimer must clearly avoid "
                    "certification, authority-to-operate, deployment, endorsement, "
                    "procurement acceptance, or agency acceptance claims."
                ),
                profile_id=profile.profile_id,
            ),
        )


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable federal evaluation validation identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != normalized:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized
