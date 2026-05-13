"""Claim guardrails for bounded prototype and assurance statements.

The runtime can generate many useful local reports, but those reports must not be
allowed to imply certification, operational deployment readiness, authority to
operate, procurement acceptance, agency endorsement, or field suitability.

This module provides deterministic claim-scope records and validators so exports,
reports, dossiers, and public summaries can be checked before publication. The
guardrails are intentionally conservative: a claim can be useful and still be
blocked if it overstates what the local prototype evidence can prove.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.assurance_dossier import AssuranceDossier
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable guardrail identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank claim text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


class ClaimScope(RuntimeStrEnum):
    """Declared scope of a claim."""

    LOCAL_PROTOTYPE = "local-prototype"
    EVALUATION_ARTIFACT = "evaluation-artifact"
    ENGINEERING_DEMONSTRATION = "engineering-demonstration"
    OPERATIONAL_SYSTEM = "operational-system"
    CERTIFICATION = "certification"
    AUTHORITY_TO_OPERATE = "authority-to-operate"
    PROCUREMENT_ACCEPTANCE = "procurement-acceptance"
    AGENCY_ENDORSEMENT = "agency-endorsement"

    def is_allowed_for_local_prototype(self) -> bool:
        """Return whether this scope is allowed for local prototype statements."""

        return self in {
            ClaimScope.LOCAL_PROTOTYPE,
            ClaimScope.EVALUATION_ARTIFACT,
            ClaimScope.ENGINEERING_DEMONSTRATION,
        }


class ClaimReviewDecision(RuntimeStrEnum):
    """Decision emitted by the claim guardrail validator."""

    ACCEPT = "accept"
    REVISE = "revise"
    BLOCK = "block"

    def is_publishable(self) -> bool:
        """Return whether a claim can be published without revision."""

        return self is ClaimReviewDecision.ACCEPT

    def blocks_publication(self) -> bool:
        """Return whether a claim must not be published."""

        return self is ClaimReviewDecision.BLOCK


class ClaimGuardrailFindingSeverity(RuntimeStrEnum):
    """Severity for claim guardrail findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_publication(self) -> bool:
        """Return whether this finding blocks claim publication."""

        return self is ClaimGuardrailFindingSeverity.BLOCKER


class ClaimGuardrailFindingKind(RuntimeStrEnum):
    """Kind of guardrail finding."""

    SCOPE_ALIGNMENT = "scope-alignment"
    PROHIBITED_CLAIM = "prohibited-claim"
    EVIDENCE_ALIGNMENT = "evidence-alignment"
    REQUIRED_DISCLAIMER = "required-disclaimer"
    TRACEABILITY = "traceability"
    READINESS = "readiness"


class ClaimEvidenceReferenceKind(RuntimeStrEnum):
    """Supported evidence reference types for claim review."""

    DOSSIER = "dossier"
    EXPORT_PACKAGE = "export-package"
    READINESS_REPORT = "readiness-report"
    LEDGER = "ledger"
    HUMAN_REVIEW = "human-review"
    PROVENANCE = "provenance"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class ClaimEvidenceReference:
    """Evidence artifact cited by a bounded claim."""

    reference_id: str
    kind: ClaimEvidenceReferenceKind
    summary: str
    artifact_uri: str | None = None

    def __post_init__(self) -> None:
        """Validate evidence reference fields."""

        _require_identifier(self.reference_id, "claim evidence reference_id")
        _require_text(self.summary, "claim evidence summary")
        if self.artifact_uri is not None:
            _require_text(self.artifact_uri, "claim evidence artifact_uri")


@dataclass(frozen=True, slots=True)
class BoundedClaim:
    """Claim proposed for a report, export, dossier, or public summary."""

    claim_id: str
    text: str
    scope: ClaimScope
    requested_claim_level: PrototypeClaimLevel
    evidence_references: tuple[ClaimEvidenceReference, ...]
    required_disclaimers: tuple[str, ...] = ()
    prohibited_terms: tuple[str, ...] = (
        "certified",
        "certification",
        "authority to operate",
        "ato",
        "deployment ready",
        "operationally ready",
        "field ready",
        "procurement ready",
        "procurement accepted",
        "agency approved",
        "agency accepted",
        "official endorsement",
        "endorsed by",
        "approved by",
        "accepted by",
    )

    def __post_init__(self) -> None:
        """Validate bounded claim fields."""

        _require_identifier(self.claim_id, "claim_id")
        _require_text(self.text, "claim text")
        for disclaimer in self.required_disclaimers:
            _require_text(disclaimer, "required disclaimer")
        for term in self.prohibited_terms:
            _require_text(term, "prohibited term")
        reference_ids = [reference.reference_id for reference in self.evidence_references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ContractValueError(
                f"Claim {self.claim_id!r} has duplicate evidence references."
            )

    def normalized_text(self) -> str:
        """Return normalized lowercase claim text for deterministic scanning."""

        return " ".join(self.text.lower().split())

    def cited_reference_ids(self) -> tuple[str, ...]:
        """Return cited evidence reference IDs."""

        return tuple(reference.reference_id for reference in self.evidence_references)

    def cites_reference_kind(self, kind: ClaimEvidenceReferenceKind) -> bool:
        """Return whether the claim cites an evidence reference of the requested kind."""

        return any(reference.kind is kind for reference in self.evidence_references)


@dataclass(frozen=True, slots=True)
class ClaimGuardrailFinding:
    """One claim-guardrail finding."""

    finding_id: str
    severity: ClaimGuardrailFindingSeverity
    kind: ClaimGuardrailFindingKind
    message: str
    claim_id: str
    evidence_reference_id: str | None = None
    prohibited_term: str | None = None

    def __post_init__(self) -> None:
        """Validate claim guardrail finding fields."""

        _require_identifier(self.finding_id, "claim guardrail finding_id")
        _require_identifier(self.claim_id, "claim guardrail claim_id")
        _require_text(self.message, "claim guardrail finding message")
        if self.evidence_reference_id is not None:
            _require_identifier(
                self.evidence_reference_id,
                "claim guardrail evidence_reference_id",
            )
        if self.prohibited_term is not None:
            _require_text(self.prohibited_term, "claim guardrail prohibited_term")


@dataclass(frozen=True, slots=True)
class ClaimGuardrailReport:
    """Guardrail review report for one bounded claim."""

    claim_id: str
    decision: ClaimReviewDecision
    findings: tuple[ClaimGuardrailFinding, ...]
    readiness_report: PrototypeReadinessReport | None = None

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(1 for finding in self.findings if finding.severity.blocks_publication())

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ClaimGuardrailFindingSeverity.WARNING
        )

    def is_publishable(self) -> bool:
        """Return whether the claim can be published as written."""

        return self.decision.is_publishable()

    def findings_by_kind(
        self,
        kind: ClaimGuardrailFindingKind,
    ) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings of a specific kind."""

        return tuple(finding for finding in self.findings if finding.kind is kind)

    def summary(self) -> str:
        """Return deterministic claim guardrail summary."""

        return (
            f"claim-guardrail: {self.claim_id} {self.decision.value} "
            f"({self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


@dataclass(frozen=True, slots=True)
class ClaimGuardrailBatchReport:
    """Batch guardrail review report for multiple claims."""

    reports: tuple[ClaimGuardrailReport, ...]

    def __post_init__(self) -> None:
        """Validate duplicate claim report IDs."""

        claim_ids = [report.claim_id for report in self.reports]
        if len(claim_ids) != len(set(claim_ids)):
            raise ContractValueError("Duplicate claim IDs in claim guardrail batch report.")

    @property
    def blocker_count(self) -> int:
        """Return total blocker count."""

        return sum(report.blocker_count for report in self.reports)

    @property
    def warning_count(self) -> int:
        """Return total warning count."""

        return sum(report.warning_count for report in self.reports)

    def is_publishable(self) -> bool:
        """Return whether all claims can be published as written."""

        return all(report.is_publishable() for report in self.reports)

    def blocked_claim_ids(self) -> tuple[str, ...]:
        """Return claim IDs blocked by guardrails."""

        return tuple(
            report.claim_id
            for report in self.reports
            if report.decision.blocks_publication()
        )

    def summary(self) -> str:
        """Return deterministic batch summary."""

        return (
            f"claim-guardrail-batch: {len(self.reports)} claim(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


class ClaimGuardrailValidator:
    """Validate bounded claims against local prototype guardrails."""

    def __init__(
        self,
        *,
        readiness_gate: PrototypeReadinessGate | None = None,
        required_local_disclaimer: str = (
            "local prototype only; not certification, authority to operate, deployment "
            "readiness, procurement acceptance, agency acceptance, or official endorsement"
        ),
    ) -> None:
        """Create a claim guardrail validator."""

        self._readiness_gate = readiness_gate or PrototypeReadinessGate()
        self._required_local_disclaimer = required_local_disclaimer

    def review_claim(
        self,
        claim: BoundedClaim,
        *,
        completed_capability_ids: Iterable[str],
    ) -> ClaimGuardrailReport:
        """Review one claim against local prototype guardrails."""

        readiness_report = self._readiness_gate.evaluate(
            completed_capability_ids=completed_capability_ids,
            requested_claim_level=claim.requested_claim_level,
        )
        findings = (
            self._scope_findings(claim)
            + self._prohibited_term_findings(claim)
            + self._disclaimer_findings(claim)
            + self._evidence_findings(claim)
            + self._readiness_findings(claim, readiness_report)
        )
        return ClaimGuardrailReport(
            claim_id=claim.claim_id,
            decision=_decide_claim(findings),
            findings=findings,
            readiness_report=readiness_report,
        )

    def review_claims(
        self,
        claims: Iterable[BoundedClaim],
        *,
        completed_capability_ids: Iterable[str],
    ) -> ClaimGuardrailBatchReport:
        """Review a batch of claims against local prototype guardrails."""

        completed_tuple = tuple(completed_capability_ids)
        return ClaimGuardrailBatchReport(
            reports=tuple(
                self.review_claim(
                    claim,
                    completed_capability_ids=completed_tuple,
                )
                for claim in claims
            )
        )

    def bounded_claim_from_dossier(
        self,
        dossier: AssuranceDossier,
        *,
        claim_id: str,
        claim_text: str,
        requested_claim_level: PrototypeClaimLevel = PrototypeClaimLevel.SERIOUS_PROTOTYPE,
    ) -> BoundedClaim:
        """Build a local-prototype claim from an assurance dossier."""

        return BoundedClaim(
            claim_id=claim_id,
            text=claim_text,
            scope=ClaimScope.LOCAL_PROTOTYPE,
            requested_claim_level=requested_claim_level,
            evidence_references=(
                ClaimEvidenceReference(
                    reference_id=dossier.dossier_id,
                    kind=ClaimEvidenceReferenceKind.DOSSIER,
                    summary=dossier.summary(),
                ),
            ),
            required_disclaimers=(self._required_local_disclaimer,),
        )

    @staticmethod
    def _scope_findings(claim: BoundedClaim) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings for claim scope."""

        if claim.scope.is_allowed_for_local_prototype():
            return ()
        return (
            ClaimGuardrailFinding(
                finding_id=f"claim-{claim.claim_id}-scope-blocked",
                severity=ClaimGuardrailFindingSeverity.BLOCKER,
                kind=ClaimGuardrailFindingKind.SCOPE_ALIGNMENT,
                message=(
                    "Claim scope exceeds local prototype/evaluation artifact boundaries and "
                    "cannot be published as a local prototype claim."
                ),
                claim_id=claim.claim_id,
            ),
        )

    @staticmethod
    def _prohibited_term_findings(claim: BoundedClaim) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings for prohibited claim language."""

        normalized = claim.normalized_text()
        findings: list[ClaimGuardrailFinding] = []
        for prohibited_term in claim.prohibited_terms:
            normalized_term = " ".join(prohibited_term.lower().split())
            if normalized_term in normalized:
                findings.append(
                    ClaimGuardrailFinding(
                        finding_id=f"claim-{claim.claim_id}-prohibited-{_slug(normalized_term)}",
                        severity=ClaimGuardrailFindingSeverity.BLOCKER,
                        kind=ClaimGuardrailFindingKind.PROHIBITED_CLAIM,
                        message=(
                            "Claim uses language that could imply certification, authority, "
                            "deployment readiness, procurement acceptance, agency acceptance, "
                            "or official endorsement."
                        ),
                        claim_id=claim.claim_id,
                        prohibited_term=prohibited_term,
                    )
                )
        return tuple(findings)

    def _disclaimer_findings(self, claim: BoundedClaim) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings for required local disclaimers."""

        normalized = claim.normalized_text()
        required = tuple(claim.required_disclaimers) or (self._required_local_disclaimer,)
        findings: list[ClaimGuardrailFinding] = []
        for disclaimer in required:
            normalized_disclaimer = " ".join(disclaimer.lower().split())
            if normalized_disclaimer not in normalized:
                findings.append(
                    ClaimGuardrailFinding(
                        finding_id=(
                            f"claim-{claim.claim_id}-missing-disclaimer-"
                            f"{_slug(normalized_disclaimer)[:48]}"
                        ),
                        severity=ClaimGuardrailFindingSeverity.WARNING,
                        kind=ClaimGuardrailFindingKind.REQUIRED_DISCLAIMER,
                        message=(
                            "Claim should carry the local-prototype disclaimer to avoid "
                            "overstating readiness or authority."
                        ),
                        claim_id=claim.claim_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _evidence_findings(claim: BoundedClaim) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings for evidence reference posture."""

        findings: list[ClaimGuardrailFinding] = []
        if not claim.evidence_references:
            findings.append(
                ClaimGuardrailFinding(
                    finding_id=f"claim-{claim.claim_id}-no-evidence",
                    severity=ClaimGuardrailFindingSeverity.BLOCKER,
                    kind=ClaimGuardrailFindingKind.EVIDENCE_ALIGNMENT,
                    message="Claim must cite at least one evidence reference.",
                    claim_id=claim.claim_id,
                )
            )
            return tuple(findings)

        if not claim.cites_reference_kind(ClaimEvidenceReferenceKind.DOSSIER) and not (
            claim.cites_reference_kind(ClaimEvidenceReferenceKind.READINESS_REPORT)
        ):
            findings.append(
                ClaimGuardrailFinding(
                    finding_id=f"claim-{claim.claim_id}-missing-readiness-evidence",
                    severity=ClaimGuardrailFindingSeverity.WARNING,
                    kind=ClaimGuardrailFindingKind.EVIDENCE_ALIGNMENT,
                    message=(
                        "Claim should cite a dossier or readiness report so maturity posture "
                        "is reviewable."
                    ),
                    claim_id=claim.claim_id,
                )
            )

        for evidence_reference in claim.evidence_references:
            if evidence_reference.kind is ClaimEvidenceReferenceKind.OTHER:
                findings.append(
                    ClaimGuardrailFinding(
                        finding_id=f"claim-{claim.claim_id}-other-evidence-{evidence_reference.reference_id}",
                        severity=ClaimGuardrailFindingSeverity.WARNING,
                        kind=ClaimGuardrailFindingKind.TRACEABILITY,
                        message=(
                            "Generic evidence references are allowed but weaker than typed "
                            "dossier, export, ledger, review, provenance, or readiness evidence."
                        ),
                        claim_id=claim.claim_id,
                        evidence_reference_id=evidence_reference.reference_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _readiness_findings(
        claim: BoundedClaim,
        readiness_report: PrototypeReadinessReport,
    ) -> tuple[ClaimGuardrailFinding, ...]:
        """Return findings from prototype readiness gate state."""

        if readiness_report.decision is PrototypeReadinessDecision.READY:
            return ()
        severity = (
            ClaimGuardrailFindingSeverity.BLOCKER
            if readiness_report.decision is PrototypeReadinessDecision.BLOCKED
            else ClaimGuardrailFindingSeverity.WARNING
        )
        return (
            ClaimGuardrailFinding(
                finding_id=f"claim-{claim.claim_id}-readiness-{readiness_report.decision.value}",
                severity=severity,
                kind=ClaimGuardrailFindingKind.READINESS,
                message=(
                    "Claim requested a prototype maturity level that is not fully supported "
                    "by completed capability evidence."
                ),
                claim_id=claim.claim_id,
            ),
        )


def _decide_claim(findings: tuple[ClaimGuardrailFinding, ...]) -> ClaimReviewDecision:
    """Return claim review decision from guardrail findings."""

    if any(finding.severity.blocks_publication() for finding in findings):
        return ClaimReviewDecision.BLOCK
    if any(
        finding.severity is ClaimGuardrailFindingSeverity.WARNING
        for finding in findings
    ):
        return ClaimReviewDecision.REVISE
    return ClaimReviewDecision.ACCEPT


def _slug(value: str) -> str:
    """Return a deterministic lowercase slug for finding IDs."""

    cleaned = "".join(character if character.isalnum() else "-" for character in value.lower())
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-") or "term"
