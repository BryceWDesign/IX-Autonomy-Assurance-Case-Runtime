"""Assurance dossier and trace-closure domain records.

The serious prototype target needs a compact dossier layer that ties mission
need, requirements, scenarios, hazards, controls, runtime evidence, human review,
and export packages into reviewable trace threads. These records describe that
closure surface without claiming certification, deployment approval, authority to
operate, official endorsement, or agency acceptance.

This module is local prototype infrastructure only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable assurance-dossier identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank assurance-dossier text."""

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


class AssuranceDossierStatus(RuntimeStrEnum):
    """Lifecycle status for an assurance dossier."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    TRACE_CLOSED = "trace_closed"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"

    def can_support_trace_closure(self) -> bool:
        """Return whether the dossier status can support trace-closure claims."""

        return self in {
            AssuranceDossierStatus.TRACE_CLOSED,
            AssuranceDossierStatus.EXPORTED,
        }

    def is_terminal(self) -> bool:
        """Return whether the dossier status is terminal."""

        return self in {
            AssuranceDossierStatus.EXPORTED,
            AssuranceDossierStatus.SUPERSEDED,
        }


class DossierTraceClosureStatus(RuntimeStrEnum):
    """Closure status for one mission-thread trace."""

    CLOSED = "closed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    NOT_ASSESSED = "not_assessed"

    def supports_acceptance(self) -> bool:
        """Return whether this trace closure status supports dossier acceptance."""

        return self is DossierTraceClosureStatus.CLOSED

    def blocks_acceptance(self) -> bool:
        """Return whether this trace closure status blocks dossier acceptance."""

        return self in {
            DossierTraceClosureStatus.BLOCKED,
            DossierTraceClosureStatus.NOT_ASSESSED,
        }


class DossierArtifactKind(RuntimeStrEnum):
    """Artifact kinds referenced by an assurance dossier."""

    MISSION_NEED = "mission_need"
    REQUIREMENT = "requirement"
    SCENARIO = "scenario"
    HAZARD = "hazard"
    CONTROL = "control"
    TELEMETRY_REPLAY = "telemetry_replay"
    SCENARIO_CAMPAIGN = "scenario_campaign"
    MONITORING_TRAIL = "monitoring_trail"
    REVIEW_WORKFLOW = "review_workflow"
    RUN_LEDGER = "run_ledger"
    EVIDENCE_BUNDLE = "evidence_bundle"
    PROVENANCE_MANIFEST = "provenance_manifest"
    EXPORT_PACKAGE = "export_package"
    READINESS_ROLLUP = "readiness_rollup"

    def is_runtime_artifact(self) -> bool:
        """Return whether this artifact kind describes runtime behavior."""

        return self in {
            DossierArtifactKind.TELEMETRY_REPLAY,
            DossierArtifactKind.SCENARIO_CAMPAIGN,
            DossierArtifactKind.MONITORING_TRAIL,
            DossierArtifactKind.RUN_LEDGER,
        }

    def is_closure_artifact(self) -> bool:
        """Return whether this artifact kind supports final closure packaging."""

        return self in {
            DossierArtifactKind.REVIEW_WORKFLOW,
            DossierArtifactKind.EVIDENCE_BUNDLE,
            DossierArtifactKind.PROVENANCE_MANIFEST,
            DossierArtifactKind.EXPORT_PACKAGE,
            DossierArtifactKind.READINESS_ROLLUP,
        }


@dataclass(frozen=True, slots=True)
class DossierArtifactReference:
    """One artifact reference inside an assurance dossier."""

    artifact_id: str
    kind: DossierArtifactKind
    title: str
    source_record_id: str
    evidence_bundle_ids: tuple[str, ...]
    provenance_manifest_ids: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate dossier artifact references."""

        object.__setattr__(
            self,
            "artifact_id",
            _require_identifier(self.artifact_id, "artifact_id"),
        )
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(
            self,
            "source_record_id",
            _require_identifier(self.source_record_id, "source_record_id"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "provenance_manifest_ids",
            _normalize_identifier_tuple(
                self.provenance_manifest_ids,
                "provenance_manifest_ids",
            ),
        )
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        if not self.evidence_bundle_ids and self.kind is not DossierArtifactKind.PROVENANCE_MANIFEST:
            raise ContractValueError(
                "dossier artifacts require evidence_bundle_ids unless they are provenance manifests."
            )

    def is_provenance_backed(self) -> bool:
        """Return whether this artifact has provenance manifest references."""

        return bool(self.provenance_manifest_ids)


@dataclass(frozen=True, slots=True)
class DossierEvidenceReference:
    """Evidence reference used by a dossier trace thread."""

    reference_id: str
    evidence_bundle_id: str
    supports_artifact_ids: tuple[str, ...]
    supports_requirement_ids: tuple[str, ...]
    supports_hazard_ids: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = "Evidence supports dossier trace closure."

    def __post_init__(self) -> None:
        """Validate dossier evidence references."""

        object.__setattr__(
            self,
            "reference_id",
            _require_identifier(self.reference_id, "reference_id"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_id",
            _require_identifier(self.evidence_bundle_id, "evidence_bundle_id"),
        )
        object.__setattr__(
            self,
            "supports_artifact_ids",
            _normalize_identifier_tuple(self.supports_artifact_ids, "supports_artifact_ids"),
        )
        object.__setattr__(
            self,
            "supports_requirement_ids",
            _normalize_identifier_tuple(
                self.supports_requirement_ids,
                "supports_requirement_ids",
            ),
        )
        object.__setattr__(
            self,
            "supports_hazard_ids",
            _normalize_identifier_tuple(self.supports_hazard_ids, "supports_hazard_ids"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        if not self.supports_artifact_ids:
            raise ContractValueError("dossier evidence references require supports_artifact_ids.")
        if not self.supports_requirement_ids:
            raise ContractValueError("dossier evidence references require supports_requirement_ids.")


@dataclass(frozen=True, slots=True)
class DossierTraceThread:
    """Closed trace thread from mission need to reviewable evidence."""

    trace_thread_id: str
    mission_need_id: str
    closure_status: DossierTraceClosureStatus
    requirement_ids: tuple[str, ...]
    scenario_ids: tuple[str, ...]
    hazard_ids: tuple[str, ...]
    control_ids: tuple[str, ...]
    evidence_reference_ids: tuple[str, ...]
    review_workflow_ids: tuple[str, ...]
    export_package_ids: tuple[str, ...] = field(default_factory=tuple)
    rationale: str = "Trace thread links mission need to evidence-backed review."

    def __post_init__(self) -> None:
        """Validate dossier trace thread fields."""

        object.__setattr__(
            self,
            "trace_thread_id",
            _require_identifier(self.trace_thread_id, "trace_thread_id"),
        )
        object.__setattr__(
            self,
            "mission_need_id",
            _require_identifier(self.mission_need_id, "mission_need_id"),
        )
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_identifier_tuple(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(
            self,
            "scenario_ids",
            _normalize_identifier_tuple(self.scenario_ids, "scenario_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        object.__setattr__(
            self,
            "control_ids",
            _normalize_identifier_tuple(self.control_ids, "control_ids"),
        )
        object.__setattr__(
            self,
            "evidence_reference_ids",
            _normalize_identifier_tuple(
                self.evidence_reference_ids,
                "evidence_reference_ids",
            ),
        )
        object.__setattr__(
            self,
            "review_workflow_ids",
            _normalize_identifier_tuple(self.review_workflow_ids, "review_workflow_ids"),
        )
        object.__setattr__(
            self,
            "export_package_ids",
            _normalize_identifier_tuple(self.export_package_ids, "export_package_ids"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        if not self.requirement_ids:
            raise ContractValueError("dossier trace threads require requirement_ids.")
        if not self.scenario_ids:
            raise ContractValueError("dossier trace threads require scenario_ids.")
        if not self.hazard_ids:
            raise ContractValueError("dossier trace threads require hazard_ids.")
        if not self.control_ids:
            raise ContractValueError("dossier trace threads require control_ids.")
        if not self.evidence_reference_ids:
            raise ContractValueError("dossier trace threads require evidence_reference_ids.")
        if not self.review_workflow_ids:
            raise ContractValueError("dossier trace threads require review_workflow_ids.")
        if self.closure_status.supports_acceptance() and not self.export_package_ids:
            raise ContractValueError("closed dossier trace threads require export_package_ids.")

    def is_closed(self) -> bool:
        """Return whether the trace thread is closed."""

        return self.closure_status.supports_acceptance()

    def blocks_acceptance(self) -> bool:
        """Return whether this trace thread blocks dossier acceptance."""

        return self.closure_status.blocks_acceptance()


@dataclass(frozen=True, slots=True)
class AssuranceDossierManifest:
    """Reviewable manifest tying assurance traces into one dossier."""

    dossier_id: str
    case_id: str
    title: str
    status: AssuranceDossierStatus
    created_at_utc: str
    trace_threads: tuple[DossierTraceThread, ...]
    artifacts: tuple[DossierArtifactReference, ...]
    evidence_references: tuple[DossierEvidenceReference, ...]
    producer: str = "ix-assurance-dossier-builder"
    notes: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = (
        "Local prototype assurance dossier only; not an official certification, "
        "authority-to-operate decision, deployment approval, or agency acceptance."
    )

    def __post_init__(self) -> None:
        """Validate assurance dossier manifest fields."""

        object.__setattr__(
            self,
            "dossier_id",
            _require_identifier(self.dossier_id, "dossier_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        _parse_utc_timestamp(self.created_at_utc, "created_at_utc")
        object.__setattr__(self, "producer", _require_text(self.producer, "producer"))
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        object.__setattr__(self, "disclaimer", _require_text(self.disclaimer, "disclaimer"))
        if not self.trace_threads:
            raise ContractValueError("assurance dossier manifests require trace_threads.")
        if not self.artifacts:
            raise ContractValueError("assurance dossier manifests require artifacts.")
        if not self.evidence_references:
            raise ContractValueError("assurance dossier manifests require evidence_references.")
        _reject_duplicate_ids(
            tuple(thread.trace_thread_id for thread in self.trace_threads),
            "dossier trace thread IDs",
        )
        _reject_duplicate_ids(
            tuple(artifact.artifact_id for artifact in self.artifacts),
            "dossier artifact IDs",
        )
        _reject_duplicate_ids(
            tuple(reference.reference_id for reference in self.evidence_references),
            "dossier evidence reference IDs",
        )
        if self.status.can_support_trace_closure() and self.open_trace_thread_ids():
            raise ContractValueError(
                "trace-closed assurance dossiers cannot contain open trace threads."
            )

    def trace_thread_ids(self) -> tuple[str, ...]:
        """Return trace thread IDs in manifest order."""

        return tuple(thread.trace_thread_id for thread in self.trace_threads)

    def open_trace_thread_ids(self) -> tuple[str, ...]:
        """Return trace thread IDs that are not closed."""

        return tuple(thread.trace_thread_id for thread in self.trace_threads if not thread.is_closed())

    def blocking_trace_thread_ids(self) -> tuple[str, ...]:
        """Return trace thread IDs that explicitly block acceptance."""

        return tuple(
            thread.trace_thread_id for thread in self.trace_threads if thread.blocks_acceptance()
        )

    def artifact_ids(self) -> tuple[str, ...]:
        """Return artifact IDs in manifest order."""

        return tuple(artifact.artifact_id for artifact in self.artifacts)

    def runtime_artifact_ids(self) -> tuple[str, ...]:
        """Return runtime artifact IDs in manifest order."""

        return tuple(
            artifact.artifact_id for artifact in self.artifacts if artifact.kind.is_runtime_artifact()
        )

    def closure_artifact_ids(self) -> tuple[str, ...]:
        """Return closure artifact IDs in manifest order."""

        return tuple(
            artifact.artifact_id for artifact in self.artifacts if artifact.kind.is_closure_artifact()
        )

    def required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs referenced by the dossier."""

        bundle_ids: list[str] = []
        for artifact in self.artifacts:
            bundle_ids.extend(artifact.evidence_bundle_ids)
        for reference in self.evidence_references:
            bundle_ids.append(reference.evidence_bundle_id)
        return tuple(dict.fromkeys(bundle_ids))

    def required_provenance_manifest_ids(self) -> tuple[str, ...]:
        """Return unique provenance manifest IDs referenced by dossier artifacts."""

        manifest_ids: list[str] = []
        for artifact in self.artifacts:
            manifest_ids.extend(artifact.provenance_manifest_ids)
        return tuple(dict.fromkeys(manifest_ids))

    def export_package_ids(self) -> tuple[str, ...]:
        """Return unique export package IDs referenced by trace threads."""

        package_ids: list[str] = []
        for thread in self.trace_threads:
            package_ids.extend(thread.export_package_ids)
        return tuple(dict.fromkeys(package_ids))

    def is_trace_closed(self) -> bool:
        """Return whether the dossier has closed every trace thread."""

        return self.status.can_support_trace_closure() and not self.open_trace_thread_ids()


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier tuples."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
