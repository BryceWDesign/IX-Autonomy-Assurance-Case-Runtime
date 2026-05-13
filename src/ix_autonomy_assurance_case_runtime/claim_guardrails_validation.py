"""Claim guardrail validation against evidence, language, and reviewer posture.

Claim release packages describe what the project may say publicly or inside
review packages. This validator checks whether those statements are bounded,
evidence-backed, reviewed, free of prohibited overclaim language, and clearly
marked as local prototype claims rather than certification, authority-to-operate,
deployment approval, official endorsement, or agency acceptance.

The checks are local prototype checks only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.claim_guardrails import (
    ClaimEvidenceReference,
    ClaimReleasePackage,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle


class ClaimGuardrailValidationFindingSeverity(RuntimeStrEnum):
    """Severity for claim guardrail validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_claim_release(self) -> bool:
        """Return whether this finding blocks claim release."""

        return self is ClaimGuardrailValidationFindingSeverity.BLOCKER


class ClaimGuardrailValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced a claim guardrail validation finding."""

    PACKAGE = "package"
    CLAIM = "claim"
    LANGUAGE = "language"
    EVIDENCE = "evidence"
    REVIEW = "review"
    DISCLAIMER = "disclaimer"


@dataclass(frozen=True, slots=True)
class ClaimGuardrailValidationFinding:
    """One claim guardrail validation finding."""

    finding_id: str
    severity: ClaimGuardrailValidationFindingSeverity
    source: ClaimGuardrailValidationFindingSource
    message: str
    package_id: str | None = None
    claim_id: str | None = None
    evidence_reference_id: str | None = None
    evidence_bundle_id: str | None = None
    rule_id: str | None = None
    capability_id: str | None = None
    artifact_id: str | None = None
    reviewer_id: str | None = None

    def __post_init__(self) -> None:
        """Validate claim guardrail validation finding fields."""

        _require_identifier(self.finding_id, "claim guardrail validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Claim guardrail validation finding {self.finding_id!r} needs a message."
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
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ClaimGuardrailValidationReport:
    """Validation report for one claim release package."""

    package_id: str
    claim_count: int
    evidence_reference_count: int
    prohibited_rule_count: int
    evidence_bundle_count: int
    findings: tuple[ClaimGuardrailValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate claim guardrail validation report counters."""

        _require_identifier(self.package_id, "package_id")
        for field_name, value in (
            ("claim_count", self.claim_count),
            ("evidence_reference_count", self.evidence_reference_count),
            ("prohibited_rule_count", self.prohibited_rule_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(finding.severity.blocks_claim_release() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ClaimGuardrailValidationFindingSeverity.WARNING
        )

    def is_claim_release_ready(self) -> bool:
        """Return whether claim validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_claim(
        self,
        claim_id: str,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Return findings for a claim ID."""

        return tuple(finding for finding in self.findings if finding.claim_id == claim_id)

    def findings_for_evidence_reference(
        self,
        evidence_reference_id: str,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Return findings for an evidence reference ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_reference_id == evidence_reference_id
        )

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_rule(
        self,
        rule_id: str,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Return findings for a prohibited phrase rule ID."""

        return tuple(finding for finding in self.findings if finding.rule_id == rule_id)

    def findings_for_reviewer(
        self,
        reviewer_id: str,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Return findings for a reviewer ID."""

        return tuple(finding for finding in self.findings if finding.reviewer_id == reviewer_id)

    def summary(self) -> str:
        """Return a deterministic claim guardrail validation summary."""

        return (
            f"claim-guardrail-validation: {self.package_id} "
            f"({self.claim_count} claim(s), "
            f"{self.evidence_reference_count} evidence reference(s), "
            f"{self.prohibited_rule_count} prohibited rule(s), "
            f"{self.evidence_bundle_count} evidence bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class ClaimGuardrailValidator:
    """Validate claim release packages against evidence and language guardrails."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        known_capability_ids: Iterable[str] = (),
        known_artifact_ids: Iterable[str] = (),
        reviewer_ids: Iterable[str] = (),
    ) -> None:
        """Create a claim guardrail validator."""

        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)
        self._known_capability_ids = _normalize_identifier_set(
            tuple(known_capability_ids),
            "known_capability_ids",
        )
        self._known_artifact_ids = _normalize_identifier_set(
            tuple(known_artifact_ids),
            "known_artifact_ids",
        )
        self._reviewer_ids = _normalize_identifier_set(tuple(reviewer_ids), "reviewer_ids")

    def validate(self, package: ClaimReleasePackage) -> ClaimGuardrailValidationReport:
        """Validate one claim release package."""

        findings = (
            self._validate_package_posture(package)
            + self._validate_claims(package)
            + self._validate_evidence_references(package)
            + self._validate_evidence(package)
            + self._validate_disclaimer(package)
        )
        return ClaimGuardrailValidationReport(
            package_id=package.package_id,
            claim_count=len(package.claims),
            evidence_reference_count=len(package.evidence_references),
            prohibited_rule_count=len(package.prohibited_phrase_rules),
            evidence_bundle_count=len(package.required_evidence_bundle_ids()),
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
                    f"Duplicate claim guardrail evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_package_posture(
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate package-level release posture."""

        findings: list[ClaimGuardrailValidationFinding] = []
        if not package.review_status.supports_release():
            findings.append(
                ClaimGuardrailValidationFinding(
                    finding_id=f"package-{package.package_id}-review-not-releaseable",
                    severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                    source=ClaimGuardrailValidationFindingSource.REVIEW,
                    message="Claim release package review status does not support release.",
                    package_id=package.package_id,
                )
            )

        if package.audience.requires_strict_language_review() and not package.limitation_claim_ids():
            findings.append(
                ClaimGuardrailValidationFinding(
                    finding_id=f"package-{package.package_id}-missing-limitation-claim",
                    severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                    source=ClaimGuardrailValidationFindingSource.PACKAGE,
                    message=(
                        "Strict-audience claim packages require limitation or "
                        "non-endorsement claims."
                    ),
                    package_id=package.package_id,
                )
            )

        for claim_id in package.blocked_claim_ids():
            findings.append(
                ClaimGuardrailValidationFinding(
                    finding_id=f"claim-{claim_id}-not-releaseable",
                    severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                    source=ClaimGuardrailValidationFindingSource.CLAIM,
                    message="Claim is not structurally releaseable.",
                    package_id=package.package_id,
                    claim_id=claim_id,
                )
            )

        return tuple(findings)

    def _validate_claims(
        self,
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate individual claims against evidence and language guardrails."""

        findings: list[ClaimGuardrailValidationFinding] = []
        evidence_reference_by_id = {
            reference.reference_id: reference for reference in package.evidence_references
        }

        for claim in package.claims:
            for reviewer_id in claim.reviewer_ids:
                if self._reviewer_ids and reviewer_id not in self._reviewer_ids:
                    findings.append(
                        ClaimGuardrailValidationFinding(
                            finding_id=f"claim-{claim.claim_id}-reviewer-{reviewer_id}-unknown",
                            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                            source=ClaimGuardrailValidationFindingSource.REVIEW,
                            message="Claim references a reviewer outside the known reviewer set.",
                            package_id=package.package_id,
                            claim_id=claim.claim_id,
                            reviewer_id=reviewer_id,
                        )
                    )

            for rule in package.prohibited_phrase_rules:
                if not rule.matches(claim.text) or rule.is_allowed_context(claim.text):
                    continue
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"claim-{claim.claim_id}-prohibited-rule-{rule.rule_id}",
                        severity=(
                            ClaimGuardrailValidationFindingSeverity.BLOCKER
                            if rule.blocks_release
                            else ClaimGuardrailValidationFindingSeverity.WARNING
                        ),
                        source=ClaimGuardrailValidationFindingSource.LANGUAGE,
                        message="Claim text matches prohibited overclaim language.",
                        package_id=package.package_id,
                        claim_id=claim.claim_id,
                        rule_id=rule.rule_id,
                    )
                )

            claim_references = tuple(
                evidence_reference_by_id[reference_id]
                for reference_id in claim.evidence_reference_ids
                if reference_id in evidence_reference_by_id
            )
            for reference_id in claim.evidence_reference_ids:
                if reference_id not in evidence_reference_by_id:
                    findings.append(
                        ClaimGuardrailValidationFinding(
                            finding_id=f"claim-{claim.claim_id}-evidence-ref-{reference_id}-missing",
                            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                            source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                            message="Claim references a missing claim evidence reference.",
                            package_id=package.package_id,
                            claim_id=claim.claim_id,
                            evidence_reference_id=reference_id,
                        )
                    )

            findings.extend(
                self._validate_claim_evidence_coverage(
                    package_id=package.package_id,
                    claim_id=claim.claim_id,
                    related_capability_ids=claim.related_capability_ids,
                    related_artifact_ids=claim.related_artifact_ids,
                    claim_references=claim_references,
                )
            )

        return tuple(findings)

    def _validate_claim_evidence_coverage(
        self,
        *,
        package_id: str,
        claim_id: str,
        related_capability_ids: tuple[str, ...],
        related_artifact_ids: tuple[str, ...],
        claim_references: tuple[ClaimEvidenceReference, ...],
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate claim evidence references cover related capabilities and artifacts."""

        findings: list[ClaimGuardrailValidationFinding] = []
        supported_capabilities = {
            capability_id
            for reference in claim_references
            for capability_id in reference.capability_ids
        }
        supported_artifacts = {
            artifact_id for reference in claim_references for artifact_id in reference.artifact_ids
        }

        for capability_id in related_capability_ids:
            if self._known_capability_ids and capability_id not in self._known_capability_ids:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"claim-{claim_id}-capability-{capability_id}-unknown",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim references a capability outside the known capability set.",
                        package_id=package_id,
                        claim_id=claim_id,
                        capability_id=capability_id,
                    )
                )
            if claim_references and capability_id not in supported_capabilities:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"claim-{claim_id}-capability-{capability_id}-unsupported",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim capability is not supported by its evidence references.",
                        package_id=package_id,
                        claim_id=claim_id,
                        capability_id=capability_id,
                    )
                )

        for artifact_id in related_artifact_ids:
            if self._known_artifact_ids and artifact_id not in self._known_artifact_ids:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"claim-{claim_id}-artifact-{artifact_id}-unknown",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim references an artifact outside the known artifact set.",
                        package_id=package_id,
                        claim_id=claim_id,
                        artifact_id=artifact_id,
                    )
                )
            if claim_references and artifact_id not in supported_artifacts:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"claim-{claim_id}-artifact-{artifact_id}-unsupported",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim artifact is not supported by its evidence references.",
                        package_id=package_id,
                        claim_id=claim_id,
                        artifact_id=artifact_id,
                    )
                )

        return tuple(findings)

    def _validate_evidence_references(
        self,
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate evidence references against known capability and artifact sets."""

        findings: list[ClaimGuardrailValidationFinding] = []
        used_reference_ids = set(package.required_evidence_reference_ids())
        for reference in package.evidence_references:
            if reference.reference_id not in used_reference_ids:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"evidence-ref-{reference.reference_id}-unused",
                        severity=ClaimGuardrailValidationFindingSeverity.WARNING,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim evidence reference is not used by any claim.",
                        package_id=package.package_id,
                        evidence_reference_id=reference.reference_id,
                    )
                )

            for capability_id in reference.capability_ids:
                if self._known_capability_ids and capability_id not in self._known_capability_ids:
                    findings.append(
                        ClaimGuardrailValidationFinding(
                            finding_id=(
                                f"evidence-ref-{reference.reference_id}-capability-"
                                f"{capability_id}-unknown"
                            ),
                            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                            source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                            message=(
                                "Claim evidence reference cites a capability outside "
                                "the known capability set."
                            ),
                            package_id=package.package_id,
                            evidence_reference_id=reference.reference_id,
                            capability_id=capability_id,
                        )
                    )

            for artifact_id in reference.artifact_ids:
                if self._known_artifact_ids and artifact_id not in self._known_artifact_ids:
                    findings.append(
                        ClaimGuardrailValidationFinding(
                            finding_id=(
                                f"evidence-ref-{reference.reference_id}-artifact-"
                                f"{artifact_id}-unknown"
                            ),
                            severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                            source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                            message=(
                                "Claim evidence reference cites an artifact outside "
                                "the known artifact set."
                            ),
                            package_id=package.package_id,
                            evidence_reference_id=reference.reference_id,
                            artifact_id=artifact_id,
                        )
                    )

        return tuple(findings)

    def _validate_evidence(
        self,
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate referenced evidence bundle existence and integrity."""

        findings: list[ClaimGuardrailValidationFinding] = []
        for bundle_id in package.required_evidence_bundle_ids():
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="Claim release package references a missing evidence bundle.",
                        package_id=package.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue

            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        package_id=package.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    ClaimGuardrailValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=ClaimGuardrailValidationFindingSeverity.WARNING,
                        source=ClaimGuardrailValidationFindingSource.EVIDENCE,
                        message=warning,
                        package_id=package.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_disclaimer(
        package: ClaimReleasePackage,
    ) -> tuple[ClaimGuardrailValidationFinding, ...]:
        """Validate non-official prototype disclaimer posture."""

        disclaimer_lower = package.disclaimer.lower()
        required_terms = ("prototype", "not", "certification", "agency acceptance")
        missing_terms = tuple(term for term in required_terms if term not in disclaimer_lower)
        if not missing_terms:
            return ()
        return (
            ClaimGuardrailValidationFinding(
                finding_id=f"package-{package.package_id}-disclaimer-weak",
                severity=ClaimGuardrailValidationFindingSeverity.BLOCKER,
                source=ClaimGuardrailValidationFindingSource.DISCLAIMER,
                message=(
                    "Claim release package disclaimer must clearly avoid certification, "
                    "deployment, authority-to-operate, endorsement, or agency acceptance claims."
                ),
                package_id=package.package_id,
            ),
        )


def _normalize_identifier_set(values: tuple[str, ...], field_name: str) -> set[str]:
    """Validate identifier values and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
    return set(normalized)


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable claim guardrail validation identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != normalized:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized
