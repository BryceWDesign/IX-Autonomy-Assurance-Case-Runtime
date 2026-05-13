"""Claim guardrail readiness decision surface.

Claim release packages and validation reports only support serious prototype
maturity when they prove bounded language, clean evidence, reviewer posture,
strict non-endorsement language, and clear avoidance of certification,
authority-to-operate, deployment approval, official endorsement, or agency
acceptance claims.

The checks are local prototype checks only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.claim_guardrails import ClaimReleasePackage
from ix_autonomy_assurance_case_runtime.claim_guardrails_validation import (
    ClaimGuardrailValidationFinding,
    ClaimGuardrailValidationFindingSeverity,
    ClaimGuardrailValidationFindingSource,
    ClaimGuardrailValidationReport,
    ClaimGuardrailValidator,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

CLAIM_GUARDRAIL_CAPABILITY_ID = "claim-guardrails"


class ClaimGuardrailReadinessDecision(RuntimeStrEnum):
    """Decision for whether claim guardrails can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the claim guardrail layer."""

        return self is ClaimGuardrailReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks claim-governance maturity progress."""

        return self is ClaimGuardrailReadinessDecision.BLOCKED


class ClaimGuardrailReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized claim guardrail readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks claim guardrail completion."""

        return self is ClaimGuardrailReadinessFindingSeverity.BLOCKER


class ClaimGuardrailReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a claim guardrail readiness finding."""

    VALIDATION = "validation"
    PACKAGE = "package"
    CLAIM = "claim"
    LANGUAGE = "language"
    EVIDENCE = "evidence"
    REVIEW = "review"
    DISCLAIMER = "disclaimer"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class ClaimGuardrailReadinessFinding:
    """One normalized claim guardrail readiness finding."""

    finding_id: str
    severity: ClaimGuardrailReadinessFindingSeverity
    source: ClaimGuardrailReadinessFindingSource
    message: str
    package_id: str | None = None
    claim_id: str | None = None
    evidence_reference_id: str | None = None
    evidence_bundle_id: str | None = None
    rule_id: str | None = None
    capability_id: str | None = None
    artifact_id: str | None = None
    reviewer_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate claim guardrail readiness finding fields."""

        _require_identifier(self.finding_id, "claim guardrail readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Claim guardrail readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("package_id", self.package_id),
            ("claim_id", self.claim_id),
            ("evidence_reference_id", self.evidence_reference_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("rule_id", self.rule_id),
            ("capability_id", self.capability_id),
            ("artifact_id", self.artifact_id),
            ("reviewer_id", self.reviewer_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ClaimGuardrailLayerReadinessReport:
    """Combined readiness report for the claim-guardrails layer."""

    decision: ClaimGuardrailReadinessDecision
    validation_report: ClaimGuardrailValidationReport
    findings: tuple[ClaimGuardrailReadinessFinding, ...]
    capability_id: str = CLAIM_GUARDRAIL_CAPABILITY_ID

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
            if finding.severity is ClaimGuardrailReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether claim guardrails can count as complete."""

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
        """Evaluate prototype claim readiness with claim guardrail completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_package(
        self,
        package_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for a package ID."""

        return tuple(finding for finding in self.findings if finding.package_id == package_id)

    def findings_for_claim(
        self,
        claim_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for a claim ID."""

        return tuple(finding for finding in self.findings if finding.claim_id == claim_id)

    def findings_for_evidence_reference(
        self,
        evidence_reference_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for an evidence reference ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_reference_id == evidence_reference_id
        )

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_rule(
        self,
        rule_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for a prohibited phrase rule ID."""

        return tuple(finding for finding in self.findings if finding.rule_id == rule_id)

    def findings_for_reviewer(
        self,
        reviewer_id: str,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Return findings for a reviewer ID."""

        return tuple(finding for finding in self.findings if finding.reviewer_id == reviewer_id)

    def summary(self) -> str:
        """Return a deterministic claim guardrail readiness summary."""

        return (
            f"claim-guardrail-readiness: {self.decision.value} "
            f"({self.validation_report.claim_count} claim(s), "
            f"{self.validation_report.evidence_reference_count} evidence reference(s), "
            f"{self.validation_report.prohibited_rule_count} prohibited rule(s), "
            f"{self.validation_report.evidence_bundle_count} evidence bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class ClaimGuardrailLayerReadinessEvaluator:
    """Evaluate whether claim guardrails can count toward prototype maturity."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        known_capability_ids: Iterable[str] = (),
        known_artifact_ids: Iterable[str] = (),
        reviewer_ids: Iterable[str] = (),
    ) -> None:
        """Create a claim guardrail readiness evaluator."""

        self._validator = ClaimGuardrailValidator(
            evidence_bundles=evidence_bundles,
            known_capability_ids=known_capability_ids,
            known_artifact_ids=known_artifact_ids,
            reviewer_ids=reviewer_ids,
        )

    def evaluate(
        self,
        package: ClaimReleasePackage,
    ) -> ClaimGuardrailLayerReadinessReport:
        """Evaluate claim guardrail validation and readiness as one surface."""

        validation_report = self._validator.validate(package)
        findings = (
            self._build_readiness_findings(package)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return ClaimGuardrailLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[ClaimGuardrailReadinessFinding] = []
        if not package.can_release():
            findings.append(
                ClaimGuardrailReadinessFinding(
                    finding_id=f"package-{package.package_id}-not-release-ready",
                    severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
                    source=ClaimGuardrailReadinessFindingSource.PACKAGE,
                    message=(
                        "Claim release package must be release-ready before the "
                        "claim-guardrails capability can be counted complete."
                    ),
                    package_id=package.package_id,
                )
            )

        if not package.review_status.supports_release():
            findings.append(
                ClaimGuardrailReadinessFinding(
                    finding_id=f"package-{package.package_id}-review-not-releaseable",
                    severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
                    source=ClaimGuardrailReadinessFindingSource.REVIEW,
                    message="Claim release package review status does not support release.",
                    package_id=package.package_id,
                )
            )

        if package.audience.requires_strict_language_review() and not package.limitation_claim_ids():
            findings.append(
                ClaimGuardrailReadinessFinding(
                    finding_id=f"package-{package.package_id}-missing-limitation-claim",
                    severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
                    source=ClaimGuardrailReadinessFindingSource.PACKAGE,
                    message=(
                        "Strict-audience claim packages require limitation or "
                        "non-endorsement claim statements."
                    ),
                    package_id=package.package_id,
                )
            )

        for claim_id in package.blocked_claim_ids():
            findings.append(
                ClaimGuardrailReadinessFinding(
                    finding_id=f"claim-{claim_id}-not-releaseable",
                    severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
                    source=ClaimGuardrailReadinessFindingSource.CLAIM,
                    message="Claim is not releaseable and blocks capability completion.",
                    package_id=package.package_id,
                    claim_id=claim_id,
                )
            )

        for claim in package.claims:
            for rule in package.prohibited_phrase_rules:
                if not rule.matches(claim.text) or rule.is_allowed_context(claim.text):
                    continue
                findings.append(
                    ClaimGuardrailReadinessFinding(
                        finding_id=f"claim-{claim.claim_id}-prohibited-rule-{rule.rule_id}",
                        severity=(
                            ClaimGuardrailReadinessFindingSeverity.BLOCKER
                            if rule.blocks_release
                            else ClaimGuardrailReadinessFindingSeverity.WARNING
                        ),
                        source=ClaimGuardrailReadinessFindingSource.LANGUAGE,
                        message="Claim text matches prohibited overclaim language.",
                        package_id=package.package_id,
                        claim_id=claim.claim_id,
                        rule_id=rule.rule_id,
                    )
                )

        if not package.required_evidence_reference_ids():
            findings.append(
                ClaimGuardrailReadinessFinding(
                    finding_id=f"package-{package.package_id}-no-claim-evidence-references",
                    severity=ClaimGuardrailReadinessFindingSeverity.BLOCKER,
                    source=ClaimGuardrailReadinessFindingSource.EVIDENCE,
                    message="Claim guardrail readiness requires claim evidence references.",
                    package_id=package.package_id,
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[ClaimGuardrailValidationFinding, ...],
    ) -> tuple[ClaimGuardrailReadinessFinding, ...]:
        """Normalize claim guardrail validation findings into readiness findings."""

        return tuple(
            ClaimGuardrailReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=_map_validation_source(finding.source),
                message=finding.message,
                package_id=finding.package_id,
                claim_id=finding.claim_id,
                evidence_reference_id=finding.evidence_reference_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                rule_id=finding.rule_id,
                capability_id=finding.capability_id,
                artifact_id=finding.artifact_id,
                reviewer_id=finding.reviewer_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[ClaimGuardrailReadinessFinding, ...],
    ) -> ClaimGuardrailReadinessDecision:
        """Return the combined claim guardrail readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return ClaimGuardrailReadinessDecision.BLOCKED
        if any(
            finding.severity is ClaimGuardrailReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return ClaimGuardrailReadinessDecision.LIMITED
        return ClaimGuardrailReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: ClaimGuardrailValidationFindingSeverity,
) -> ClaimGuardrailReadinessFindingSeverity:
    """Map claim guardrail validation severity to readiness severity."""

    if severity is ClaimGuardrailValidationFindingSeverity.BLOCKER:
        return ClaimGuardrailReadinessFindingSeverity.BLOCKER
    if severity is ClaimGuardrailValidationFindingSeverity.WARNING:
        return ClaimGuardrailReadinessFindingSeverity.WARNING
    return ClaimGuardrailReadinessFindingSeverity.INFO


def _map_validation_source(
    source: ClaimGuardrailValidationFindingSource,
) -> ClaimGuardrailReadinessFindingSource:
    """Map claim guardrail validation source to readiness source."""

    source_map = {
        ClaimGuardrailValidationFindingSource.PACKAGE: (
            ClaimGuardrailReadinessFindingSource.PACKAGE
        ),
        ClaimGuardrailValidationFindingSource.CLAIM: (
            ClaimGuardrailReadinessFindingSource.CLAIM
        ),
        ClaimGuardrailValidationFindingSource.LANGUAGE: (
            ClaimGuardrailReadinessFindingSource.LANGUAGE
        ),
        ClaimGuardrailValidationFindingSource.EVIDENCE: (
            ClaimGuardrailReadinessFindingSource.EVIDENCE
        ),
        ClaimGuardrailValidationFindingSource.REVIEW: (
            ClaimGuardrailReadinessFindingSource.REVIEW
        ),
        ClaimGuardrailValidationFindingSource.DISCLAIMER: (
            ClaimGuardrailReadinessFindingSource.DISCLAIMER
        ),
    }
    return source_map.get(source, ClaimGuardrailReadinessFindingSource.VALIDATION)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable claim guardrail readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
