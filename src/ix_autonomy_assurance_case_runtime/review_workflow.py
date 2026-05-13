"""Review workflow, signoff, finding, and dissent domain records.

The serious prototype target requires structured human governance records before
the repo can credibly claim audit-ready signoff support. These records capture
reviewer scope, dispositions, unresolved findings, dissent, conditions, and
evidence references without allowing human review to erase safety or evidence
gaps silently.

This module is local prototype infrastructure only. It does not claim official
approval, certification, authority to operate, deployment readiness, or agency
acceptance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.authority import ReviewActor
from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    ReviewDisposition,
    RuntimeStrEnum,
)


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable review-workflow identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank review-workflow text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_identifier_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate identifier tuples and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class ReviewWorkflowStatus(RuntimeStrEnum):
    """Lifecycle state for a structured review workflow."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    SUPERSEDED = "superseded"

    def can_accept_signoff(self) -> bool:
        """Return whether the workflow can accept reviewer signoff records."""

        return self in {
            ReviewWorkflowStatus.READY_FOR_REVIEW,
            ReviewWorkflowStatus.IN_REVIEW,
            ReviewWorkflowStatus.COMPLETED,
        }

    def can_support_acceptance(self) -> bool:
        """Return whether this workflow state can support acceptance."""

        return self is ReviewWorkflowStatus.COMPLETED


class ReviewAuthorityScope(RuntimeStrEnum):
    """Review scope covered by an actor, signoff, finding, or dissent."""

    ASSURANCE_CASE = "assurance_case"
    POLICY = "policy"
    SAFETY_GATE = "safety_gate"
    SCENARIO_CAMPAIGN = "scenario_campaign"
    MONITORING = "monitoring"
    PROVENANCE = "provenance"
    EXPORT_PACKAGE = "export_package"

    def is_runtime_scope(self) -> bool:
        """Return whether the scope is tied to runtime behavior."""

        return self in {
            ReviewAuthorityScope.SAFETY_GATE,
            ReviewAuthorityScope.SCENARIO_CAMPAIGN,
            ReviewAuthorityScope.MONITORING,
        }


class ReviewFindingSeverity(RuntimeStrEnum):
    """Severity for structured human-review findings."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return an ordinal severity rank."""

        ranks = {
            ReviewFindingSeverity.INFO: 0,
            ReviewFindingSeverity.LOW: 1,
            ReviewFindingSeverity.MEDIUM: 2,
            ReviewFindingSeverity.HIGH: 3,
            ReviewFindingSeverity.CRITICAL: 4,
        }
        return ranks[self]

    def blocks_acceptance_when_unresolved(self) -> bool:
        """Return whether an unresolved finding blocks acceptance."""

        return self.rank >= ReviewFindingSeverity.MEDIUM.rank


class ReviewFindingStatus(RuntimeStrEnum):
    """Lifecycle status for a review finding."""

    OPEN = "open"
    MITIGATED = "mitigated"
    WAIVED = "waived"
    ACCEPTED_RISK = "accepted_risk"
    CLOSED = "closed"

    def is_resolved(self) -> bool:
        """Return whether this finding has a bounded resolution state."""

        return self in {
            ReviewFindingStatus.MITIGATED,
            ReviewFindingStatus.WAIVED,
            ReviewFindingStatus.ACCEPTED_RISK,
            ReviewFindingStatus.CLOSED,
        }

    def requires_waiver_reference(self) -> bool:
        """Return whether this status needs an explicit waiver reference."""

        return self is ReviewFindingStatus.WAIVED


class ReviewDissentSeverity(RuntimeStrEnum):
    """Severity for recorded reviewer dissent."""

    CONCERN = "concern"
    OBJECTION = "objection"
    BLOCKING_OBJECTION = "blocking_objection"

    def blocks_acceptance(self) -> bool:
        """Return whether this dissent blocks acceptance."""

        return self is ReviewDissentSeverity.BLOCKING_OBJECTION


@dataclass(frozen=True, slots=True)
class ReviewAuthorityBinding:
    """Actor-to-scope binding for a review workflow."""

    binding_id: str
    actor: ReviewActor
    authority_scopes: tuple[ReviewAuthorityScope, ...]
    can_sign: bool = True
    can_waive: bool = False
    can_record_dissent: bool = True

    def __post_init__(self) -> None:
        """Validate review authority binding fields."""

        object.__setattr__(
            self,
            "binding_id",
            _require_identifier(self.binding_id, "binding_id"),
        )
        if not self.authority_scopes:
            raise ContractValueError("review authority bindings require authority_scopes.")
        if len(self.authority_scopes) != len(set(self.authority_scopes)):
            raise ContractValueError(
                "review authority bindings must not duplicate authority_scopes."
            )

    def covers_scope(self, scope: ReviewAuthorityScope) -> bool:
        """Return whether this binding covers a review scope."""

        return scope in self.authority_scopes


@dataclass(frozen=True, slots=True)
class ReviewFinding:
    """Structured finding produced during human review."""

    finding_id: str
    scope: ReviewAuthorityScope
    severity: ReviewFindingSeverity
    status: ReviewFindingStatus
    title: str
    rationale: str
    opened_by_actor_id: str
    opened_at_utc: str
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    source_record_ids: tuple[str, ...] = field(default_factory=tuple)
    waiver_id: str | None = None

    def __post_init__(self) -> None:
        """Validate review finding fields."""

        object.__setattr__(
            self,
            "finding_id",
            _require_identifier(self.finding_id, "finding_id"),
        )
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "opened_by_actor_id",
            _require_identifier(self.opened_by_actor_id, "opened_by_actor_id"),
        )
        _parse_utc_timestamp(self.opened_at_utc, "opened_at_utc")
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_identifier_tuple(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "source_record_ids",
            _normalize_identifier_tuple(self.source_record_ids, "source_record_ids"),
        )
        if self.waiver_id is not None:
            object.__setattr__(
                self,
                "waiver_id",
                _require_identifier(self.waiver_id, "waiver_id"),
            )
        if self.status.requires_waiver_reference() and self.waiver_id is None:
            raise ContractValueError("waived review findings require waiver_id.")
        if self.severity.blocks_acceptance_when_unresolved() and not self.evidence_bundle_ids:
            raise ContractValueError("medium, high, or critical findings require evidence.")
        if self.severity is ReviewFindingSeverity.CRITICAL and not self.hazard_ids:
            raise ContractValueError("critical review findings require hazard_ids.")

    def is_unresolved_blocker(self) -> bool:
        """Return whether this finding blocks acceptance."""

        return (
            self.severity.blocks_acceptance_when_unresolved()
            and not self.status.is_resolved()
        )


@dataclass(frozen=True, slots=True)
class ReviewSignoffRecord:
    """Human signoff, rejection, escalation, or evidence request."""

    signoff_id: str
    workflow_id: str
    actor: ReviewActor
    scope: ReviewAuthorityScope
    disposition: ReviewDisposition
    rationale: str
    signed_at_utc: str
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    condition_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate review signoff fields."""

        object.__setattr__(
            self,
            "signoff_id",
            _require_identifier(self.signoff_id, "signoff_id"),
        )
        object.__setattr__(
            self,
            "workflow_id",
            _require_identifier(self.workflow_id, "workflow_id"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        _parse_utc_timestamp(self.signed_at_utc, "signed_at_utc")
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "condition_ids",
            _normalize_identifier_tuple(self.condition_ids, "condition_ids"),
        )
        if self.disposition.allows_acceptance() and not self.evidence_bundle_ids:
            raise ContractValueError("accepting review signoffs require evidence_bundle_ids.")
        if (
            self.disposition is ReviewDisposition.APPROVED_WITH_CONDITIONS
            and not self.condition_ids
        ):
            raise ContractValueError(
                "approved_with_conditions signoffs require condition_ids."
            )

    def supports_acceptance(self) -> bool:
        """Return whether this signoff supports acceptance."""

        return self.disposition.allows_acceptance()


@dataclass(frozen=True, slots=True)
class ReviewDissentRecord:
    """Recorded dissent that must survive audit/export surfaces."""

    dissent_id: str
    workflow_id: str
    actor: ReviewActor
    scope: ReviewAuthorityScope
    severity: ReviewDissentSeverity
    rationale: str
    recorded_at_utc: str
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    related_finding_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate dissent record fields."""

        object.__setattr__(
            self,
            "dissent_id",
            _require_identifier(self.dissent_id, "dissent_id"),
        )
        object.__setattr__(
            self,
            "workflow_id",
            _require_identifier(self.workflow_id, "workflow_id"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        _parse_utc_timestamp(self.recorded_at_utc, "recorded_at_utc")
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "related_finding_ids",
            _normalize_identifier_tuple(self.related_finding_ids, "related_finding_ids"),
        )
        if self.severity.blocks_acceptance() and not self.related_finding_ids:
            raise ContractValueError("blocking dissent requires related_finding_ids.")

    def blocks_acceptance(self) -> bool:
        """Return whether this dissent blocks acceptance."""

        return self.severity.blocks_acceptance()


@dataclass(frozen=True, slots=True)
class ReviewWorkflowRecord:
    """Aggregate review workflow record for audit-ready signoff."""

    workflow_id: str
    case_id: str
    title: str
    status: ReviewWorkflowStatus
    authority_bindings: tuple[ReviewAuthorityBinding, ...]
    findings: tuple[ReviewFinding, ...] = field(default_factory=tuple)
    signoffs: tuple[ReviewSignoffRecord, ...] = field(default_factory=tuple)
    dissents: tuple[ReviewDissentRecord, ...] = field(default_factory=tuple)
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    system_id: str | None = None
    deployment_id: str | None = None

    def __post_init__(self) -> None:
        """Validate aggregate review workflow records."""

        object.__setattr__(
            self,
            "workflow_id",
            _require_identifier(self.workflow_id, "workflow_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        if self.system_id is not None:
            object.__setattr__(self, "system_id", _require_identifier(self.system_id, "system_id"))
        if self.deployment_id is not None:
            object.__setattr__(
                self,
                "deployment_id",
                _require_identifier(self.deployment_id, "deployment_id"),
            )
        if not self.authority_bindings:
            raise ContractValueError("review workflows require authority_bindings.")
        _reject_duplicate_ids(
            tuple(binding.binding_id for binding in self.authority_bindings),
            "review authority binding IDs",
        )
        _reject_duplicate_ids(
            tuple(finding.finding_id for finding in self.findings),
            "review finding IDs",
        )
        _reject_duplicate_ids(
            tuple(signoff.signoff_id for signoff in self.signoffs),
            "review signoff IDs",
        )
        _reject_duplicate_ids(
            tuple(dissent.dissent_id for dissent in self.dissents),
            "review dissent IDs",
        )
        for signoff in self.signoffs:
            if signoff.workflow_id != self.workflow_id:
                raise ContractValueError("review signoff workflow_id must match workflow_id.")
        for dissent in self.dissents:
            if dissent.workflow_id != self.workflow_id:
                raise ContractValueError("review dissent workflow_id must match workflow_id.")

    def unresolved_finding_ids(self) -> tuple[str, ...]:
        """Return unresolved blocker finding IDs."""

        return tuple(
            finding.finding_id for finding in self.findings if finding.is_unresolved_blocker()
        )

    def dissent_ids(self) -> tuple[str, ...]:
        """Return dissent IDs in workflow order."""

        return tuple(dissent.dissent_id for dissent in self.dissents)

    def blocking_dissent_ids(self) -> tuple[str, ...]:
        """Return blocking dissent IDs."""

        return tuple(
            dissent.dissent_id for dissent in self.dissents if dissent.blocks_acceptance()
        )

    def accepted_signoff_ids(self) -> tuple[str, ...]:
        """Return signoff IDs that support acceptance."""

        return tuple(
            signoff.signoff_id
            for signoff in self.signoffs
            if signoff.supports_acceptance()
        )

    def required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs referenced by the workflow."""

        bundle_ids: list[str] = list(self.evidence_bundle_ids)
        for finding in self.findings:
            bundle_ids.extend(finding.evidence_bundle_ids)
        for signoff in self.signoffs:
            bundle_ids.extend(signoff.evidence_bundle_ids)
        for dissent in self.dissents:
            bundle_ids.extend(dissent.evidence_bundle_ids)
        return tuple(dict.fromkeys(bundle_ids))

    def can_support_acceptance(self) -> bool:
        """Return whether the workflow can support acceptance."""

        return (
            self.status.can_support_acceptance()
            and bool(self.accepted_signoff_ids())
            and not self.unresolved_finding_ids()
            and not self.blocking_dissent_ids()
        )


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier tuples."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
