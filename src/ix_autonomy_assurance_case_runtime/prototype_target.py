"""Serious prototype target and maturity model.

This module defines the local open-source maturity target used by the runtime.
It intentionally models prototype maturity only. It does not claim certification,
authority to operate, deployment approval, official endorsement, procurement
acceptance, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum

BASELINE_MATURITY_PERCENT = 40
SERIOUS_PROTOTYPE_TARGET_PERCENT = 80
MAXIMUM_LOCAL_PROTOTYPE_PERCENT = 100


class PrototypeCapabilityArea(RuntimeStrEnum):
    """Capability area for a serious prototype target."""

    GOVERNANCE = "governance"
    REGISTRY = "registry"
    POLICY = "policy"
    FRAMEWORK = "framework"
    PROVENANCE = "provenance"
    TELEMETRY = "telemetry"
    SCENARIO_CAMPAIGN = "scenario_campaign"
    MONITORING = "monitoring"
    REVIEW_WORKFLOW = "review_workflow"
    AUDIT_EXPORT = "audit_export"
    TRACE_CLOSURE = "trace_closure"
    CLAIM_GOVERNANCE = "claim_governance"
    FEDERAL_EVALUATION = "federal_evaluation"
    RUNTIME_EVIDENCE = "runtime_evidence"
    ASSURANCE_ALIGNMENT = "assurance_alignment"
    HUMAN_AUTHORITY = "human_authority"

    def is_runtime_facing(self) -> bool:
        """Return whether this area directly describes runtime behavior."""

        return self in {
            PrototypeCapabilityArea.TELEMETRY,
            PrototypeCapabilityArea.SCENARIO_CAMPAIGN,
            PrototypeCapabilityArea.MONITORING,
            PrototypeCapabilityArea.RUNTIME_EVIDENCE,
        }

    def is_review_facing(self) -> bool:
        """Return whether this area supports review, claims, or evaluation."""

        return self in {
            PrototypeCapabilityArea.REVIEW_WORKFLOW,
            PrototypeCapabilityArea.AUDIT_EXPORT,
            PrototypeCapabilityArea.TRACE_CLOSURE,
            PrototypeCapabilityArea.CLAIM_GOVERNANCE,
            PrototypeCapabilityArea.FEDERAL_EVALUATION,
            PrototypeCapabilityArea.ASSURANCE_ALIGNMENT,
            PrototypeCapabilityArea.HUMAN_AUTHORITY,
        }


@dataclass(frozen=True, slots=True)
class PrototypeCapabilityTarget:
    """One capability target that contributes to local prototype maturity."""

    capability_id: str
    area: PrototypeCapabilityArea
    title: str
    description: str
    maturity_increment_percent: int
    evidence_expectations: tuple[str, ...] = field(default_factory=tuple)
    required_for_serious_prototype: bool = True

    def __post_init__(self) -> None:
        """Validate prototype capability target fields."""

        object.__setattr__(
            self,
            "capability_id",
            _require_identifier(self.capability_id, "capability_id"),
        )
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(
            self,
            "description",
            _require_text(self.description, "description"),
        )
        object.__setattr__(
            self,
            "evidence_expectations",
            _normalize_text_tuple(
                self.evidence_expectations,
                "evidence_expectations",
            ),
        )
        if self.maturity_increment_percent <= 0:
            raise ContractValueError(
                "maturity_increment_percent must be greater than zero."
            )

    @property
    def name(self) -> str:
        """Compatibility alias for title."""

        return self.title

    @property
    def percent_contribution(self) -> int:
        """Compatibility alias for the maturity increment."""

        return self.maturity_increment_percent

    @property
    def maturity_percent(self) -> int:
        """Compatibility alias for the maturity increment."""

        return self.maturity_increment_percent

    def is_completed_by(self, completed_capability_ids: Iterable[str]) -> bool:
        """Return whether this target is completed by the supplied capability IDs."""

        return self.capability_id in set(completed_capability_ids)

    def summary(self) -> str:
        """Return a deterministic capability target summary."""

        return (
            f"{self.capability_id}: {self.title} "
            f"({self.area.value}, +{self.maturity_increment_percent}%)"
        )


@dataclass(frozen=True, slots=True)
class PrototypeMaturityAssessment:
    """Maturity assessment for a set of completed capability IDs."""

    achieved_percent: int
    target_percent: int
    completed_capability_ids: tuple[str, ...]
    target_capability_ids: tuple[str, ...]
    missing_capability_ids: tuple[str, ...]
    unexpected_capability_ids: tuple[str, ...]
    duplicate_capability_ids: tuple[str, ...]
    baseline_percent: int = BASELINE_MATURITY_PERCENT
    maximum_percent: int = MAXIMUM_LOCAL_PROTOTYPE_PERCENT

    def __post_init__(self) -> None:
        """Validate prototype maturity assessment fields."""

        if self.achieved_percent < 0:
            raise ContractValueError("achieved_percent must not be negative.")
        if self.target_percent < 0:
            raise ContractValueError("target_percent must not be negative.")
        if self.baseline_percent < 0:
            raise ContractValueError("baseline_percent must not be negative.")
        if self.maximum_percent <= 0:
            raise ContractValueError("maximum_percent must be greater than zero.")
        object.__setattr__(
            self,
            "completed_capability_ids",
            _normalize_identifier_tuple(
                self.completed_capability_ids,
                "completed_capability_ids",
                reject_duplicates=False,
            ),
        )
        object.__setattr__(
            self,
            "target_capability_ids",
            _normalize_identifier_tuple(
                self.target_capability_ids,
                "target_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "missing_capability_ids",
            _normalize_identifier_tuple(
                self.missing_capability_ids,
                "missing_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "unexpected_capability_ids",
            _normalize_identifier_tuple(
                self.unexpected_capability_ids,
                "unexpected_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "duplicate_capability_ids",
            _normalize_identifier_tuple(
                self.duplicate_capability_ids,
                "duplicate_capability_ids",
            ),
        )

    @property
    def completed_target_count(self) -> int:
        """Return count of completed capability IDs that are in the target model."""

        target_ids = set(self.target_capability_ids)
        return sum(
            1
            for capability_id in dict.fromkeys(self.completed_capability_ids)
            if capability_id in target_ids
        )

    @property
    def target_count(self) -> int:
        """Return the number of capability targets in the model."""

        return len(self.target_capability_ids)

    def target_percent_met(self) -> bool:
        """Return whether achieved percent meets the serious prototype target."""

        return self.achieved_percent >= self.target_percent

    def is_serious_prototype_target_met(self) -> bool:
        """Return whether achieved percent meets the serious prototype target."""

        return self.target_percent_met()

    def completion_ratio(self) -> float:
        """Return completed target ratio as a float."""

        if not self.target_capability_ids:
            return 0.0
        return self.completed_target_count / len(self.target_capability_ids)

    def summary(self) -> str:
        """Return a deterministic maturity assessment summary."""

        return (
            f"prototype-maturity: {self.achieved_percent}% "
            f"({self.completed_target_count}/{self.target_count} target capability(s), "
            f"{len(self.missing_capability_ids)} missing, "
            f"{len(self.unexpected_capability_ids)} unexpected, "
            f"{len(self.duplicate_capability_ids)} duplicate)"
        )


def build_serious_prototype_targets() -> tuple[PrototypeCapabilityTarget, ...]:
    """Return the serious-prototype target capability model.

    The first nine capabilities preserve the original 40% -> 80% serious
    prototype path. The later hardening capabilities extend the local prototype
    posture beyond 80% without claiming official approval or deployment fitness.
    """

    return (
        PrototypeCapabilityTarget(
            capability_id="registry-layer",
            area=PrototypeCapabilityArea.REGISTRY,
            title="Registry layer",
            description=(
                "Registered systems, models, use cases, deployments, lifecycle "
                "state, and risk posture are represented as strict records."
            ),
            maturity_increment_percent=4,
            evidence_expectations=(
                "registered systems",
                "registered use cases",
                "registry evidence coverage",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="policy-pack-engine",
            area=PrototypeCapabilityArea.POLICY,
            title="Policy pack engine",
            description=(
                "Policy packs, rules, waivers, evaluation reports, and waiver "
                "evidence are validated before runtime claims can progress."
            ),
            maturity_increment_percent=4,
            evidence_expectations=(
                "policy rules",
                "policy decisions",
                "waiver evidence",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="framework-crosswalks",
            area=PrototypeCapabilityArea.FRAMEWORK,
            title="Framework crosswalks",
            description=(
                "Framework objectives, control mappings, coverage status, and "
                "supporting evidence are captured as reviewable records."
            ),
            maturity_increment_percent=4,
            evidence_expectations=(
                "control mappings",
                "framework evidence",
                "coverage findings",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="signed-provenance",
            area=PrototypeCapabilityArea.PROVENANCE,
            title="Signed provenance",
            description=(
                "Artifacts, digests, signatures, signer identity, verification "
                "policy, and provenance readiness are represented explicitly."
            ),
            maturity_increment_percent=4,
            evidence_expectations=(
                "artifact digests",
                "signature posture",
                "provenance verification",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="telemetry-adapters",
            area=PrototypeCapabilityArea.TELEMETRY,
            title="Telemetry adapters",
            description=(
                "Telemetry sources, schemas, envelopes, replay records, adapter "
                "normalization, and replay bounds are validated."
            ),
            maturity_increment_percent=5,
            evidence_expectations=(
                "trusted telemetry source posture",
                "schema coverage",
                "replay records",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="scenario-campaign-runner",
            area=PrototypeCapabilityArea.SCENARIO_CAMPAIGN,
            title="Scenario campaign runner",
            description=(
                "Scenario campaigns, acceptance thresholds, stop rules, runner "
                "reports, and campaign readiness are captured."
            ),
            maturity_increment_percent=5,
            evidence_expectations=(
                "scenario campaign catalog",
                "campaign run report",
                "acceptance thresholds",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="monitoring-incidents",
            area=PrototypeCapabilityArea.MONITORING,
            title="Monitoring incidents",
            description=(
                "Monitoring snapshots, drift records, incidents, and revalidation "
                "triggers are linked into readiness decisions."
            ),
            maturity_increment_percent=5,
            evidence_expectations=(
                "monitoring trail",
                "incident records",
                "revalidation triggers",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="review-workflow",
            area=PrototypeCapabilityArea.REVIEW_WORKFLOW,
            title="Review workflow",
            description=(
                "Human review authority, findings, signoffs, dissent, and review "
                "workflow readiness are modeled explicitly."
            ),
            maturity_increment_percent=5,
            evidence_expectations=(
                "review findings",
                "human signoff",
                "dissent preservation",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="audit-report-export",
            area=PrototypeCapabilityArea.AUDIT_EXPORT,
            title="Audit report export",
            description=(
                "Export package manifests, redaction rules, evidence references, "
                "provenance references, and non-official disclaimers are checked."
            ),
            maturity_increment_percent=4,
            evidence_expectations=(
                "export package manifest",
                "redaction rules",
                "machine-readable package",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="assurance-dossier",
            area=PrototypeCapabilityArea.TRACE_CLOSURE,
            title="Assurance dossier",
            description=(
                "Mission threads are closed across requirement, scenario, hazard, "
                "control, evidence, human review, export package, and provenance links."
            ),
            maturity_increment_percent=8,
            evidence_expectations=(
                "closed trace threads",
                "runtime artifacts",
                "closure artifacts",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="claim-guardrails",
            area=PrototypeCapabilityArea.CLAIM_GOVERNANCE,
            title="Claim guardrails",
            description=(
                "Public and review-package claims are bounded, evidence-backed, "
                "language-checked, and kept away from certification or agency claims."
            ),
            maturity_increment_percent=6,
            evidence_expectations=(
                "claim evidence references",
                "prohibited phrase rules",
                "non-endorsement claims",
            ),
        ),
        PrototypeCapabilityTarget(
            capability_id="federal-evaluation-profile",
            area=PrototypeCapabilityArea.FEDERAL_EVALUATION,
            title="Federal evaluation profile",
            description=(
                "Local capability, artifact, and evidence records are mapped to "
                "federal/IC/DoD-style review concerns without claiming acceptance."
            ),
            maturity_increment_percent=6,
            evidence_expectations=(
                "core T&E concern coverage",
                "evaluation mappings",
                "bounded disclaimer",
            ),
        ),
    )


def serious_prototype_capability_ids() -> tuple[str, ...]:
    """Return all capability IDs in the serious prototype target model."""

    return tuple(target.capability_id for target in build_serious_prototype_targets())


def assess_serious_prototype_maturity(
    completed_capability_ids: Iterable[str],
) -> PrototypeMaturityAssessment:
    """Assess local prototype maturity from completed capability IDs."""

    completed = tuple(_require_identifier(value, "completed_capability_ids") for value in completed_capability_ids)
    target_by_id = {
        target.capability_id: target for target in build_serious_prototype_targets()
    }
    target_ids = tuple(target_by_id)
    unique_completed = tuple(dict.fromkeys(completed))
    duplicate_ids = _duplicate_identifiers(completed)
    unexpected_ids = tuple(
        capability_id for capability_id in unique_completed if capability_id not in target_by_id
    )
    missing_ids = tuple(
        capability_id for capability_id in target_ids if capability_id not in unique_completed
    )
    achieved_percent = BASELINE_MATURITY_PERCENT + sum(
        target_by_id[capability_id].maturity_increment_percent
        for capability_id in unique_completed
        if capability_id in target_by_id
    )
    achieved_percent = min(achieved_percent, MAXIMUM_LOCAL_PROTOTYPE_PERCENT)

    return PrototypeMaturityAssessment(
        achieved_percent=achieved_percent,
        target_percent=SERIOUS_PROTOTYPE_TARGET_PERCENT,
        completed_capability_ids=completed,
        target_capability_ids=target_ids,
        missing_capability_ids=missing_ids,
        unexpected_capability_ids=unexpected_ids,
        duplicate_capability_ids=duplicate_ids,
    )


def _duplicate_identifiers(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return duplicate identifiers in first-duplicate order."""

    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return tuple(duplicates)


def _normalize_identifier_tuple(
    values: tuple[str, ...],
    field_name: str,
    *,
    reject_duplicates: bool = True,
) -> tuple[str, ...]:
    """Validate identifier tuples and optionally reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if reject_duplicates and len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable prototype target identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank prototype target text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized
