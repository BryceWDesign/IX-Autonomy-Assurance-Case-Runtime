"""Federal evaluation profile readiness decision surface.

Federal evaluation profiles and validation reports only support serious
prototype maturity when they prove required core T&E concern coverage,
satisfied mappings, available capabilities, available artifacts, clean evidence,
and bounded non-official evaluation language.

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
    FederalEvaluationProfile,
    FederalReviewConcern,
)
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile_validation import (
    REQUIRED_CORE_EVALUATION_CONCERNS,
    FederalEvaluationProfileValidator,
    FederalEvaluationValidationFinding,
    FederalEvaluationValidationFindingSeverity,
    FederalEvaluationValidationFindingSource,
    FederalEvaluationValidationReport,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID = "federal-evaluation-profile"


class FederalEvaluationReadinessDecision(RuntimeStrEnum):
    """Decision for whether a federal evaluation profile supports maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the federal evaluation profile layer."""

        return self is FederalEvaluationReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks evaluation-profile maturity progress."""

        return self is FederalEvaluationReadinessDecision.BLOCKED


class FederalEvaluationReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized federal evaluation readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks federal evaluation profile completion."""

        return self is FederalEvaluationReadinessFindingSeverity.BLOCKER


class FederalEvaluationReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a federal evaluation readiness finding."""

    VALIDATION = "validation"
    PROFILE = "profile"
    MAPPING = "mapping"
    CONCERN = "concern"
    CAPABILITY = "capability"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    DISCLAIMER = "disclaimer"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class FederalEvaluationReadinessFinding:
    """One normalized federal evaluation readiness finding."""

    finding_id: str
    severity: FederalEvaluationReadinessFindingSeverity
    source: FederalEvaluationReadinessFindingSource
    message: str
    profile_id: str | None = None
    mapping_id: str | None = None
    concern: FederalReviewConcern | None = None
    capability_id: str | None = None
    artifact_id: str | None = None
    evidence_bundle_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate federal evaluation readiness finding fields."""

        _require_identifier(self.finding_id, "federal evaluation readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Federal evaluation readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("profile_id", self.profile_id),
            ("mapping_id", self.mapping_id),
            ("capability_id", self.capability_id),
            ("artifact_id", self.artifact_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class FederalEvaluationLayerReadinessReport:
    """Combined readiness report for the federal-evaluation-profile layer."""

    decision: FederalEvaluationReadinessDecision
    validation_report: FederalEvaluationValidationReport
    findings: tuple[FederalEvaluationReadinessFinding, ...]
    capability_id: str = FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID

    @property
    def blocker_count(self) -> int:
        """Return normalized blocker count."""

        return sum(finding.severity.blocks_completion() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return normalized warning count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is FederalEvaluationReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether the federal evaluation profile can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with federal profile completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_profile(
        self,
        profile_id: str,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for a profile ID."""

        return tuple(finding for finding in self.findings if finding.profile_id == profile_id)

    def findings_for_mapping(
        self,
        mapping_id: str,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for a mapping ID."""

        return tuple(finding for finding in self.findings if finding.mapping_id == mapping_id)

    def findings_for_concern(
        self,
        concern: FederalReviewConcern,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for a review concern."""

        return tuple(finding for finding in self.findings if finding.concern is concern)

    def findings_for_capability(
        self,
        capability_id: str,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for a capability ID."""

        return tuple(
            finding for finding in self.findings if finding.capability_id == capability_id
        )

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic federal evaluation readiness summary."""

        return (
            f"federal-evaluation-readiness: {self.decision.value} "
            f"({self.validation_report.mapping_count} mapping(s), "
            f"{self.validation_report.concern_count} concern(s), "
            f"{self.validation_report.core_concern_count} core concern(s), "
            f"{self.validation_report.completed_capability_count} completed capability(s), "
            f"{self.validation_report.artifact_count} artifact(s), "
            f"{self.validation_report.evidence_bundle_count} evidence bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class FederalEvaluationLayerReadinessEvaluator:
    """Evaluate whether a federal evaluation profile can count toward maturity."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle] = ()) -> None:
        """Create a federal evaluation profile readiness evaluator."""

        self._validator = FederalEvaluationProfileValidator(evidence_bundles=evidence_bundles)

    def evaluate(
        self,
        profile: FederalEvaluationProfile,
    ) -> FederalEvaluationLayerReadinessReport:
        """Evaluate federal profile validation and readiness as one surface."""

        validation_report = self._validator.validate(profile)
        findings = (
            self._build_readiness_findings(profile)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return FederalEvaluationLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        profile: FederalEvaluationProfile,
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[FederalEvaluationReadinessFinding] = []

        if not profile.can_support_evaluation_package():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-not-evaluation-ready",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.PROFILE,
                    message=(
                        "Federal evaluation profile must support a bounded evaluation "
                        "package before the capability can be counted complete."
                    ),
                    profile_id=profile.profile_id,
                )
            )

        present_concerns = {mapping.concern for mapping in profile.concern_mappings}
        for concern in REQUIRED_CORE_EVALUATION_CONCERNS:
            if concern in present_concerns:
                continue
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-missing-{concern.value}",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.CONCERN,
                    message="Federal evaluation readiness requires all core T&E concerns.",
                    profile_id=profile.profile_id,
                    concern=concern,
                )
            )

        for mapping_id in profile.blocked_mapping_ids():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"mapping-{mapping_id}-blocks-profile",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.MAPPING,
                    message="Federal evaluation concern mapping blocks profile completion.",
                    profile_id=profile.profile_id,
                    mapping_id=mapping_id,
                )
            )

        for capability_id in profile.missing_required_capability_ids():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-capability-{capability_id}-missing",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.CAPABILITY,
                    message="Federal evaluation readiness is missing a required capability.",
                    profile_id=profile.profile_id,
                    capability_id=capability_id,
                )
            )

        for artifact_id in profile.missing_required_artifact_ids():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-artifact-{artifact_id}-missing",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.ARTIFACT,
                    message="Federal evaluation readiness is missing a required artifact.",
                    profile_id=profile.profile_id,
                    artifact_id=artifact_id,
                )
            )

        for bundle_id in profile.missing_required_evidence_bundle_ids():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-evidence-{bundle_id}-missing",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.EVIDENCE,
                    message="Federal evaluation readiness is missing a required evidence bundle.",
                    profile_id=profile.profile_id,
                    evidence_bundle_id=bundle_id,
                )
            )

        if not profile.disclaimer_is_bounded():
            findings.append(
                FederalEvaluationReadinessFinding(
                    finding_id=f"profile-{profile.profile_id}-disclaimer-weak",
                    severity=FederalEvaluationReadinessFindingSeverity.BLOCKER,
                    source=FederalEvaluationReadinessFindingSource.DISCLAIMER,
                    message=(
                        "Federal evaluation readiness requires a bounded non-official "
                        "prototype disclaimer."
                    ),
                    profile_id=profile.profile_id,
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[FederalEvaluationValidationFinding, ...],
    ) -> tuple[FederalEvaluationReadinessFinding, ...]:
        """Normalize federal evaluation validation findings into readiness findings."""

        return tuple(
            FederalEvaluationReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=_map_validation_source(finding.source),
                message=finding.message,
                profile_id=finding.profile_id,
                mapping_id=finding.mapping_id,
                concern=finding.concern,
                capability_id=finding.capability_id,
                artifact_id=finding.artifact_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[FederalEvaluationReadinessFinding, ...],
    ) -> FederalEvaluationReadinessDecision:
        """Return the combined federal evaluation readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return FederalEvaluationReadinessDecision.BLOCKED
        if any(
            finding.severity is FederalEvaluationReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return FederalEvaluationReadinessDecision.LIMITED
        return FederalEvaluationReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: FederalEvaluationValidationFindingSeverity,
) -> FederalEvaluationReadinessFindingSeverity:
    """Map federal evaluation validation severity to readiness severity."""

    if severity is FederalEvaluationValidationFindingSeverity.BLOCKER:
        return FederalEvaluationReadinessFindingSeverity.BLOCKER
    if severity is FederalEvaluationValidationFindingSeverity.WARNING:
        return FederalEvaluationReadinessFindingSeverity.WARNING
    return FederalEvaluationReadinessFindingSeverity.INFO


def _map_validation_source(
    source: FederalEvaluationValidationFindingSource,
) -> FederalEvaluationReadinessFindingSource:
    """Map federal evaluation validation source to readiness source."""

    source_map = {
        FederalEvaluationValidationFindingSource.PROFILE: (
            FederalEvaluationReadinessFindingSource.PROFILE
        ),
        FederalEvaluationValidationFindingSource.MAPPING: (
            FederalEvaluationReadinessFindingSource.MAPPING
        ),
        FederalEvaluationValidationFindingSource.CONCERN: (
            FederalEvaluationReadinessFindingSource.CONCERN
        ),
        FederalEvaluationValidationFindingSource.CAPABILITY: (
            FederalEvaluationReadinessFindingSource.CAPABILITY
        ),
        FederalEvaluationValidationFindingSource.ARTIFACT: (
            FederalEvaluationReadinessFindingSource.ARTIFACT
        ),
        FederalEvaluationValidationFindingSource.EVIDENCE: (
            FederalEvaluationReadinessFindingSource.EVIDENCE
        ),
        FederalEvaluationValidationFindingSource.DISCLAIMER: (
            FederalEvaluationReadinessFindingSource.DISCLAIMER
        ),
    }
    return source_map.get(source, FederalEvaluationReadinessFindingSource.VALIDATION)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable federal evaluation readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
