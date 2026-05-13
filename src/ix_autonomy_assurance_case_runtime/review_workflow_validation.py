"""Review workflow validation against authority bindings and evidence.

Review workflow records describe findings, signoffs, dissent, and authority scope.
This validator checks that the workflow is grounded in local evidence, that actors
are authorized for the scopes they touch, that accepting signoffs are not hiding
unresolved blockers, and that dissent remains linked to review findings.

The checks are local prototype checks only. They do not claim official approval,
certification, authority to operate, deployment readiness, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.review_workflow import (
    ReviewAuthorityScope,
    ReviewWorkflowRecord,
)


class ReviewWorkflowValidationFindingSeverity(RuntimeStrEnum):
    """Severity for review workflow validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_review_readiness(self) -> bool:
        """Return whether this finding blocks review workflow readiness."""

        return self is ReviewWorkflowValidationFindingSeverity.BLOCKER


class ReviewWorkflowValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced a review workflow validation finding."""

    WORKFLOW = "workflow"
    AUTHORITY = "authority"
    FINDING = "finding"
    SIGNOFF = "signoff"
    DISSENT = "dissent"
    EVIDENCE = "evidence"


@dataclass(frozen=True, slots=True)
class ReviewWorkflowValidationFinding:
    """One review workflow validation finding."""

    finding_id: str
    severity: ReviewWorkflowValidationFindingSeverity
    source: ReviewWorkflowValidationFindingSource
    message: str
    workflow_id: str | None = None
    review_finding_id: str | None = None
    signoff_id: str | None = None
    dissent_id: str | None = None
    actor_id: str | None = None
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate review workflow validation finding fields."""

        _require_identifier(self.finding_id, "review workflow validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Review workflow validation finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("workflow_id", self.workflow_id),
            ("review_finding_id", self.review_finding_id),
            ("signoff_id", self.signoff_id),
            ("dissent_id", self.dissent_id),
            ("actor_id", self.actor_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ReviewWorkflowValidationReport:
    """Validation report for one review workflow."""

    workflow_id: str
    finding_count: int
    signoff_count: int
    dissent_count: int
    evidence_bundle_count: int
    findings: tuple[ReviewWorkflowValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate review workflow validation report counters."""

        _require_identifier(self.workflow_id, "workflow_id")
        for field_name, value in (
            ("finding_count", self.finding_count),
            ("signoff_count", self.signoff_count),
            ("dissent_count", self.dissent_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(
            finding.severity.blocks_review_readiness() for finding in self.findings
        )

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ReviewWorkflowValidationFindingSeverity.WARNING
        )

    def is_review_ready(self) -> bool:
        """Return whether review validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_review_finding(
        self,
        review_finding_id: str,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Return validation findings for a review finding."""

        return tuple(
            finding
            for finding in self.findings
            if finding.review_finding_id == review_finding_id
        )

    def findings_for_signoff(
        self,
        signoff_id: str,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Return validation findings for a signoff."""

        return tuple(finding for finding in self.findings if finding.signoff_id == signoff_id)

    def findings_for_dissent(
        self,
        dissent_id: str,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Return validation findings for a dissent record."""

        return tuple(finding for finding in self.findings if finding.dissent_id == dissent_id)

    def findings_for_actor(self, actor_id: str) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Return validation findings for an actor."""

        return tuple(finding for finding in self.findings if finding.actor_id == actor_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Return validation findings for an evidence bundle."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic review workflow validation summary."""

        return (
            f"review-workflow-validation: {self.workflow_id} "
            f"({self.finding_count} finding(s), {self.signoff_count} signoff(s), "
            f"{self.dissent_count} dissent(s), {self.evidence_bundle_count} "
            f"evidence bundle(s), {self.blocker_count} blocker(s), "
            f"{self.warning_count} warning(s))"
        )


class ReviewWorkflowValidator:
    """Validate review workflow authority, findings, dissent, and evidence."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle] = ()) -> None:
        """Create a review workflow validator."""

        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)

    def validate(self, workflow: ReviewWorkflowRecord) -> ReviewWorkflowValidationReport:
        """Validate one review workflow record."""

        findings = (
            self._validate_workflow_posture(workflow)
            + self._validate_findings(workflow)
            + self._validate_signoffs(workflow)
            + self._validate_dissents(workflow)
            + self._validate_evidence(workflow)
        )
        return ReviewWorkflowValidationReport(
            workflow_id=workflow.workflow_id,
            finding_count=len(workflow.findings),
            signoff_count=len(workflow.signoffs),
            dissent_count=len(workflow.dissents),
            evidence_bundle_count=len(workflow.required_evidence_bundle_ids()),
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
                    f"Duplicate review workflow evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_workflow_posture(
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Validate workflow-level posture."""

        findings: list[ReviewWorkflowValidationFinding] = []
        if not workflow.status.can_accept_signoff() and workflow.signoffs:
            findings.append(
                ReviewWorkflowValidationFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-status-cannot-accept-signoff",
                    severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                    source=ReviewWorkflowValidationFindingSource.WORKFLOW,
                    message="Review workflow status does not permit signoff records.",
                    workflow_id=workflow.workflow_id,
                )
            )
        if not workflow.status.can_support_acceptance():
            findings.append(
                ReviewWorkflowValidationFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-not-completed",
                    severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                    source=ReviewWorkflowValidationFindingSource.WORKFLOW,
                    message="Review workflow must be completed before it supports acceptance.",
                    workflow_id=workflow.workflow_id,
                )
            )
        if not workflow.accepted_signoff_ids():
            findings.append(
                ReviewWorkflowValidationFinding(
                    finding_id=f"workflow-{workflow.workflow_id}-no-accepting-signoff",
                    severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                    source=ReviewWorkflowValidationFindingSource.SIGNOFF,
                    message="Review workflow has no accepting signoff.",
                    workflow_id=workflow.workflow_id,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_findings(
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Validate review finding resolution and authority."""

        findings: list[ReviewWorkflowValidationFinding] = []
        actor_ids = _bound_actor_ids(workflow)
        waiver_actor_ids = _waiver_actor_ids(workflow)
        for finding in workflow.findings:
            if finding.opened_by_actor_id not in actor_ids:
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"finding-{finding.finding_id}-actor-not-bound",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.AUTHORITY,
                        message="Review finding was opened by an actor without workflow binding.",
                        workflow_id=workflow.workflow_id,
                        review_finding_id=finding.finding_id,
                        actor_id=finding.opened_by_actor_id,
                    )
                )
            if not _actor_has_scope(workflow, finding.opened_by_actor_id, finding.scope):
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"finding-{finding.finding_id}-actor-scope-missing",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.AUTHORITY,
                        message=(
                            "Review finding actor does not have authority for the "
                            "finding scope."
                        ),
                        workflow_id=workflow.workflow_id,
                        review_finding_id=finding.finding_id,
                        actor_id=finding.opened_by_actor_id,
                    )
                )
            if finding.is_unresolved_blocker():
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"finding-{finding.finding_id}-unresolved-blocker",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.FINDING,
                        message=(
                            "Unresolved medium, high, or critical review finding "
                            "blocks acceptance."
                        ),
                        workflow_id=workflow.workflow_id,
                        review_finding_id=finding.finding_id,
                    )
                )
            if finding.waiver_id is not None and not waiver_actor_ids:
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"finding-{finding.finding_id}-waiver-without-authority",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.AUTHORITY,
                        message=(
                            "Waived review finding requires at least one workflow "
                            "actor with waiver authority."
                        ),
                        workflow_id=workflow.workflow_id,
                        review_finding_id=finding.finding_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_signoffs(
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Validate signoff authority and conditions."""

        findings: list[ReviewWorkflowValidationFinding] = []
        finding_ids = {finding.finding_id for finding in workflow.findings}
        for signoff in workflow.signoffs:
            if not _actor_can_sign(workflow, signoff.actor.actor_id, signoff.scope):
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"signoff-{signoff.signoff_id}-actor-cannot-sign",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.AUTHORITY,
                        message="Review signoff actor lacks signing authority for the scope.",
                        workflow_id=workflow.workflow_id,
                        signoff_id=signoff.signoff_id,
                        actor_id=signoff.actor.actor_id,
                    )
                )
            for condition_id in signoff.condition_ids:
                if condition_id not in finding_ids:
                    findings.append(
                        ReviewWorkflowValidationFinding(
                            finding_id=f"signoff-{signoff.signoff_id}-condition-{condition_id}-missing",
                            severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                            source=ReviewWorkflowValidationFindingSource.SIGNOFF,
                            message="Conditional signoff references a missing review finding.",
                            workflow_id=workflow.workflow_id,
                            signoff_id=signoff.signoff_id,
                            review_finding_id=condition_id,
                        )
                    )
        return tuple(findings)

    @staticmethod
    def _validate_dissents(
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Validate dissent authority and finding links."""

        findings: list[ReviewWorkflowValidationFinding] = []
        finding_ids = {finding.finding_id for finding in workflow.findings}
        for dissent in workflow.dissents:
            if not _actor_can_record_dissent(workflow, dissent.actor.actor_id, dissent.scope):
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"dissent-{dissent.dissent_id}-actor-cannot-dissent",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.AUTHORITY,
                        message="Dissent actor lacks dissent authority for the scope.",
                        workflow_id=workflow.workflow_id,
                        dissent_id=dissent.dissent_id,
                        actor_id=dissent.actor.actor_id,
                    )
                )
            for related_finding_id in dissent.related_finding_ids:
                if related_finding_id not in finding_ids:
                    findings.append(
                        ReviewWorkflowValidationFinding(
                            finding_id=f"dissent-{dissent.dissent_id}-finding-{related_finding_id}-missing",
                            severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                            source=ReviewWorkflowValidationFindingSource.DISSENT,
                            message="Dissent references a missing review finding.",
                            workflow_id=workflow.workflow_id,
                            dissent_id=dissent.dissent_id,
                            review_finding_id=related_finding_id,
                        )
                    )
            if dissent.blocks_acceptance():
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"dissent-{dissent.dissent_id}-blocks-acceptance",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.DISSENT,
                        message="Blocking dissent prevents review workflow acceptance.",
                        workflow_id=workflow.workflow_id,
                        dissent_id=dissent.dissent_id,
                    )
                )
        return tuple(findings)

    def _validate_evidence(
        self,
        workflow: ReviewWorkflowRecord,
    ) -> tuple[ReviewWorkflowValidationFinding, ...]:
        """Validate referenced evidence bundle existence and integrity."""

        findings: list[ReviewWorkflowValidationFinding] = []
        for bundle_id in workflow.required_evidence_bundle_ids():
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.EVIDENCE,
                        message="Review workflow references a missing evidence bundle.",
                        workflow_id=workflow.workflow_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue
            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=ReviewWorkflowValidationFindingSeverity.BLOCKER,
                        source=ReviewWorkflowValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        workflow_id=workflow.workflow_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    ReviewWorkflowValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=ReviewWorkflowValidationFindingSeverity.WARNING,
                        source=ReviewWorkflowValidationFindingSource.EVIDENCE,
                        message=warning,
                        workflow_id=workflow.workflow_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)


def _bound_actor_ids(workflow: ReviewWorkflowRecord) -> set[str]:
    """Return actor IDs bound to the workflow."""

    return {binding.actor.actor_id for binding in workflow.authority_bindings}


def _waiver_actor_ids(workflow: ReviewWorkflowRecord) -> set[str]:
    """Return actor IDs with waiver authority."""

    return {binding.actor.actor_id for binding in workflow.authority_bindings if binding.can_waive}


def _actor_has_scope(
    workflow: ReviewWorkflowRecord,
    actor_id: str,
    scope: ReviewAuthorityScope,
) -> bool:
    """Return whether an actor has a workflow binding for the scope."""

    return any(
        binding.actor.actor_id == actor_id and binding.covers_scope(scope)
        for binding in workflow.authority_bindings
    )


def _actor_can_sign(
    workflow: ReviewWorkflowRecord,
    actor_id: str,
    scope: ReviewAuthorityScope,
) -> bool:
    """Return whether an actor can sign for a workflow scope."""

    return any(
        binding.actor.actor_id == actor_id
        and binding.can_sign
        and binding.covers_scope(scope)
        for binding in workflow.authority_bindings
    )


def _actor_can_record_dissent(
    workflow: ReviewWorkflowRecord,
    actor_id: str,
    scope: ReviewAuthorityScope,
) -> bool:
    """Return whether an actor can record dissent for a workflow scope."""

    return any(
        binding.actor.actor_id == actor_id
        and binding.can_record_dissent
        and binding.covers_scope(scope)
        for binding in workflow.authority_bindings
    )


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable review workflow validation identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
