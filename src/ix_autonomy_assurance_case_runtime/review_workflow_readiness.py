"""Review workflow readiness decision surface.

Review workflow records and validation reports only support prototype maturity
when they prove completed human review, accepting signoff, bounded findings,
preserved dissent, and clean evidence integrity. This module turns those checks
into the capability gate for the ``review-workflow`` target.

The checks are local prototype checks only. They do not claim official approval,
certification, authority to operate, deployment readiness, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.review_workflow import ReviewWorkflowRecord
from ix_autonomy_assurance_case_runtime.review_workflow_validation import (
    ReviewWorkflowValidationFinding,
    ReviewWorkflowValidationFindingSeverity,
    ReviewWorkflowValidationReport,
    ReviewWorkflowValidator,
)

REVIEW_WORKFLOW_CAPABILITY_ID = "review-workflow"


class ReviewWorkflowReadinessDecision(RuntimeStrEnum):
    """Decision for whether review workflow can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the review-workflow capability."""

        return self is ReviewWorkflowReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks review-based maturity progress."""

        return self is ReviewWorkflowReadinessDecision.BLOCKED


class ReviewWorkflowReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized review workflow readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks review workflow completion."""

        return self is ReviewWorkflowReadinessFindingSeverity.BLOCKER


class ReviewWorkflowReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a review workflow readiness finding."""

    VALIDATION = "validation"
    WORKFLOW = "workflow"
    FINDING = "finding"
    SIGNOFF = "signoff"
    DISSENT = "dissent"
    EVIDENCE = "evidence"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class ReviewWorkflowReadinessFinding:
    """One normalized review workflow readiness finding."""

    finding_id: str
    severity: ReviewWorkflowReadinessFindingSeverity
    source: ReviewWorkflowReadinessFindingSource
    message: str
    workflow_id: str | None = None
    review_finding_id: str | None = None
    signoff_id: str | None = None
    dissent_id: str | None = None
    actor_id: str | None = None
    evidence_bundle_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate review workflow readiness finding fields."""

        _require_identifier(self.finding_id, "review workflow readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Review workflow readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("workflow_id", self.workflow_id),
            ("review_finding_id", self.review_finding_id),
            ("signoff_id", self.signoff_id),
            ("dissent_id", self.dissent_id),
            ("actor_id", self.actor_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ReviewWorkflowLayerReadinessReport:
    """Combined readiness report for the review-workflow capability layer."""

    decision: ReviewWorkflowReadinessDecision
    validation_report: ReviewWorkflowValidationReport
    findings: tuple[ReviewWorkflowReadinessFinding, ...]
    capability_id: str = REVIEW_WORKFLOW_CAPABILITY_ID

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
            if finding.severity is ReviewWorkflowReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether review workflow can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this readiness report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with review workflow completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_workflow(
        self,
        workflow_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for a workflow ID."""

        return tuple(finding for finding in self.findings if finding.workflow_id == workflow_id)

    def findings_for_review_finding(
        self,
        review_finding_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for a review finding ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.review_finding_id == review_finding_id
        )

    def findings_for_signoff(
        self,
        signoff_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for a signoff ID."""

        return tuple(finding for finding in self.findings if finding.signoff_id == signoff_id)

    def findings_for_dissent(
        self,
        dissent_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for a dissent ID."""

        return tuple(finding for finding in self.findings if finding.dissent_id == dissent_id)

    def findings_for_actor(
        self,
        actor_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for an actor ID."""

        return tuple(finding for finding in self.findings if finding.actor_id == actor_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic review workflow readiness summary."""

        return (
            f"review-workflow-readiness: {self.decision.value} "
            f"({self.validation_report.finding_count} finding(s), "
            f"{self.validation_report.signoff_count} signoff(s), "
            f"{self.validation_report.dissent_count} dissent(s), "
            f"{self.validation_report.evidence_bundle_count} evidence bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class ReviewWorkflowLayerReadinessEvaluator:
    """Evaluate whether review workflow can count toward prototype maturity."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle] = ()) -> None:
        """Create a review workflow readiness evaluator."""

        self._validator = ReviewWorkflowValidator(evidence_bundles=evidence_bundles)

    def evaluate(self, workflow: ReviewWorkflowRecord) -> ReviewWorkflowLayerReadinessReport:
        """Evaluate review workflow validation and readiness as one surface."""

        validation_report = self._validator.validate(workflow)
        findings = (
            self._build_readiness_findings(workflow)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return ReviewWorkflowLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[ReviewWorkflowReadinessFinding] = []

        if not workflow.status.can_support_acceptance():
            findings.append(
                ReviewWorkflowReadinessFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-not-acceptance-ready",
                    severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
                    source=ReviewWorkflowReadinessFindingSource.WORKFLOW,
                    message=(
                        "Review workflow must be completed before the review-workflow "
                        "capability can be counted complete."
                    ),
                    workflow_id=workflow.workflow_id,
                )
            )

        if not workflow.accepted_signoff_ids():
            findings.append(
                ReviewWorkflowReadinessFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-no-accepting-signoff",
                    severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
                    source=ReviewWorkflowReadinessFindingSource.SIGNOFF,
                    message=(
                        "Review workflow readiness requires at least one accepting "
                        "human signoff."
                    ),
                    workflow_id=workflow.workflow_id,
                )
            )

        for review_finding_id in workflow.unresolved_finding_ids():
            findings.append(
                ReviewWorkflowReadinessFinding(
                    finding_id=f"finding-{review_finding_id}-unresolved-blocker",
                    severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
                    source=ReviewWorkflowReadinessFindingSource.FINDING,
                    message=(
                        "Unresolved medium, high, or critical review finding blocks "
                        "review-workflow capability completion."
                    ),
                    workflow_id=workflow.workflow_id,
                    review_finding_id=review_finding_id,
                )
            )

        for dissent_id in workflow.blocking_dissent_ids():
            findings.append(
                ReviewWorkflowReadinessFinding(
                    finding_id=f"dissent-{dissent_id}-blocking",
                    severity=ReviewWorkflowReadinessFindingSeverity.BLOCKER,
                    source=ReviewWorkflowReadinessFindingSource.DISSENT,
                    message=(
                        "Blocking dissent must remain visible and prevents review-workflow "
                        "capability completion."
                    ),
                    workflow_id=workflow.workflow_id,
                    dissent_id=dissent_id,
                )
            )

        if not workflow.dissent_ids():
            findings.append(
                ReviewWorkflowReadinessFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-no-dissent-history",
                    severity=ReviewWorkflowReadinessFindingSeverity.INFO,
                    source=ReviewWorkflowReadinessFindingSource.READINESS,
                    message=(
                        "Review workflow has no dissent records. This is acceptable when no "
                        "dissent exists, but the export layer must preserve dissent if present."
                    ),
                    workflow_id=workflow.workflow_id,
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[ReviewWorkflowValidationFinding, ...],
    ) -> tuple[ReviewWorkflowReadinessFinding, ...]:
        """Normalize review workflow validation findings into readiness findings."""

        return tuple(
            ReviewWorkflowReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=_map_validation_source(finding),
                message=finding.message,
                workflow_id=finding.workflow_id,
                review_finding_id=finding.review_finding_id,
                signoff_id=finding.signoff_id,
                dissent_id=finding.dissent_id,
                actor_id=finding.actor_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[ReviewWorkflowReadinessFinding, ...],
    ) -> ReviewWorkflowReadinessDecision:
        """Return the combined review workflow readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return ReviewWorkflowReadinessDecision.BLOCKED
        if any(
            finding.severity is ReviewWorkflowReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return ReviewWorkflowReadinessDecision.LIMITED
        return ReviewWorkflowReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: ReviewWorkflowValidationFindingSeverity,
) -> ReviewWorkflowReadinessFindingSeverity:
    """Map review workflow validation severity to readiness severity."""

    if severity is ReviewWorkflowValidationFindingSeverity.BLOCKER:
        return ReviewWorkflowReadinessFindingSeverity.BLOCKER
    if severity is ReviewWorkflowValidationFindingSeverity.WARNING:
        return ReviewWorkflowReadinessFindingSeverity.WARNING
    return ReviewWorkflowReadinessFindingSeverity.INFO


def _map_validation_source(
    finding: ReviewWorkflowValidationFinding,
) -> ReviewWorkflowReadinessFindingSource:
    """Map validation finding content to a readiness source."""

    if finding.review_finding_id is not None:
        return ReviewWorkflowReadinessFindingSource.FINDING
    if finding.signoff_id is not None:
        return ReviewWorkflowReadinessFindingSource.SIGNOFF
    if finding.dissent_id is not None:
        return ReviewWorkflowReadinessFindingSource.DISSENT
    if finding.evidence_bundle_id is not None:
        return ReviewWorkflowReadinessFindingSource.EVIDENCE
    return ReviewWorkflowReadinessFindingSource.VALIDATION


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable review workflow readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
