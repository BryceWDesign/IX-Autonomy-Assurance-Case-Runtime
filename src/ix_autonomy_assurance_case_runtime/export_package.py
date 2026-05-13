"""Export package manifest domain records.

The serious prototype target needs audit-ready export packaging before it can
credibly present evidence outside the runtime. These records describe export
artifacts, evidence references, provenance manifest references, redaction rules,
package format, audience, and lifecycle posture.

This module is local prototype infrastructure only. It does not claim official
submission readiness, certification, authority to operate, deployment approval,
agency acceptance, or legal records-management compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable export-package identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank export-package text."""

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


class ExportPackageStatus(RuntimeStrEnum):
    """Lifecycle state for an export package manifest."""

    DRAFT = "draft"
    READY_FOR_REVIEW = "ready_for_review"
    READY_TO_EXPORT = "ready_to_export"
    EXPORTED = "exported"
    SUPERSEDED = "superseded"

    def can_be_exported(self) -> bool:
        """Return whether the package status can support export emission."""

        return self in {
            ExportPackageStatus.READY_TO_EXPORT,
            ExportPackageStatus.EXPORTED,
        }

    def is_terminal(self) -> bool:
        """Return whether the package status is terminal."""

        return self in {
            ExportPackageStatus.EXPORTED,
            ExportPackageStatus.SUPERSEDED,
        }


class ExportPackageFormat(RuntimeStrEnum):
    """Supported export package output formats."""

    JSON = "json"
    JSONL = "jsonl"
    MARKDOWN = "markdown"
    ZIP_MANIFEST = "zip_manifest"

    def is_machine_readable(self) -> bool:
        """Return whether the format is machine-readable."""

        return self in {
            ExportPackageFormat.JSON,
            ExportPackageFormat.JSONL,
            ExportPackageFormat.ZIP_MANIFEST,
        }


class ExportPackageAudience(RuntimeStrEnum):
    """Intended audience for an export package."""

    LOCAL_REVIEW = "local_review"
    OPEN_SOURCE_REVIEW = "open_source_review"
    TECHNICAL_DUE_DILIGENCE = "technical_due_diligence"
    FEDERAL_EVALUATION = "federal_evaluation"
    INTERNAL_ASSURANCE = "internal_assurance"

    def requires_redaction_review(self) -> bool:
        """Return whether this audience requires explicit redaction posture."""

        return self in {
            ExportPackageAudience.OPEN_SOURCE_REVIEW,
            ExportPackageAudience.TECHNICAL_DUE_DILIGENCE,
            ExportPackageAudience.FEDERAL_EVALUATION,
        }


class ExportArtifactKind(RuntimeStrEnum):
    """Artifact category included in an export package."""

    ASSURANCE_CASE = "assurance_case"
    TRACEABILITY_GRAPH = "traceability_graph"
    REQUIREMENT_SET = "requirement_set"
    HAZARD_REGISTER = "hazard_register"
    POLICY_PACK = "policy_pack"
    REGISTRY_CATALOG = "registry_catalog"
    FRAMEWORK_CROSSWALK = "framework_crosswalk"
    PROVENANCE_MANIFEST = "provenance_manifest"
    TELEMETRY_REPLAY = "telemetry_replay"
    SCENARIO_CAMPAIGN = "scenario_campaign"
    MONITORING_TRAIL = "monitoring_trail"
    REVIEW_WORKFLOW = "review_workflow"
    RUN_LEDGER = "run_ledger"
    EVIDENCE_BUNDLE = "evidence_bundle"
    READINESS_REPORT = "readiness_report"
    REPOSITORY_METADATA = "repository_metadata"

    def requires_evidence_reference(self) -> bool:
        """Return whether this artifact kind should be evidence-backed."""

        return self not in {
            ExportArtifactKind.PROVENANCE_MANIFEST,
            ExportArtifactKind.REPOSITORY_METADATA,
        }

    def is_runtime_artifact(self) -> bool:
        """Return whether this artifact kind describes runtime behavior."""

        return self in {
            ExportArtifactKind.TELEMETRY_REPLAY,
            ExportArtifactKind.SCENARIO_CAMPAIGN,
            ExportArtifactKind.MONITORING_TRAIL,
            ExportArtifactKind.RUN_LEDGER,
        }


@dataclass(frozen=True, slots=True)
class ExportArtifactReference:
    """One artifact reference inside an export package manifest."""

    artifact_id: str
    kind: ExportArtifactKind
    title: str
    source_record_id: str
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    provenance_manifest_ids: tuple[str, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = field(default_factory=tuple)
    required: bool = True
    contains_sensitive_fields: bool = False

    def __post_init__(self) -> None:
        """Validate export artifact reference fields."""

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
        object.__setattr__(self, "tags", _normalize_text_tuple(self.tags, "tags"))
        if self.required and self.kind.requires_evidence_reference() and not self.evidence_bundle_ids:
            raise ContractValueError(
                "required export artifacts of this kind require evidence_bundle_ids."
            )

    def is_provenance_backed(self) -> bool:
        """Return whether this artifact has provenance manifest references."""

        return bool(self.provenance_manifest_ids)

    def needs_redaction_review(self) -> bool:
        """Return whether this artifact requires redaction review."""

        return self.contains_sensitive_fields


@dataclass(frozen=True, slots=True)
class ExportRedactionRule:
    """Redaction rule that must be applied or reviewed before export."""

    rule_id: str
    target_artifact_kinds: tuple[ExportArtifactKind, ...]
    field_path: str
    rationale: str
    replacement_text: str = "[REDACTED]"
    required: bool = True
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate export redaction rule fields."""

        object.__setattr__(
            self,
            "rule_id",
            _require_identifier(self.rule_id, "rule_id"),
        )
        object.__setattr__(self, "field_path", _require_text(self.field_path, "field_path"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "replacement_text",
            _require_text(self.replacement_text, "replacement_text"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        if not self.target_artifact_kinds:
            raise ContractValueError("redaction rules require target_artifact_kinds.")
        if len(self.target_artifact_kinds) != len(set(self.target_artifact_kinds)):
            raise ContractValueError("redaction rules must not duplicate target_artifact_kinds.")
        if self.required and not self.evidence_bundle_ids:
            raise ContractValueError("required redaction rules require evidence_bundle_ids.")


@dataclass(frozen=True, slots=True)
class ExportPackageManifest:
    """Manifest for a reviewable evidence-backed export package."""

    package_id: str
    case_id: str
    title: str
    status: ExportPackageStatus
    package_format: ExportPackageFormat
    audience: ExportPackageAudience
    created_at_utc: str
    artifacts: tuple[ExportArtifactReference, ...]
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    redaction_rules: tuple[ExportRedactionRule, ...] = field(default_factory=tuple)
    provenance_manifest_ids: tuple[str, ...] = field(default_factory=tuple)
    producer: str = "ix-export-package-builder"
    notes: tuple[str, ...] = field(default_factory=tuple)
    disclaimer: str = (
        "Local prototype export package only; not an official certification, "
        "authority-to-operate decision, deployment approval, or agency acceptance package."
    )

    def __post_init__(self) -> None:
        """Validate export package manifest fields."""

        object.__setattr__(
            self,
            "package_id",
            _require_identifier(self.package_id, "package_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        _parse_utc_timestamp(self.created_at_utc, "created_at_utc")
        object.__setattr__(self, "producer", _require_text(self.producer, "producer"))
        object.__setattr__(self, "disclaimer", _require_text(self.disclaimer, "disclaimer"))
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
        if not self.artifacts:
            raise ContractValueError("export package manifests require artifacts.")
        _reject_duplicate_ids(
            tuple(artifact.artifact_id for artifact in self.artifacts),
            "export artifact IDs",
        )
        _reject_duplicate_ids(
            tuple(rule.rule_id for rule in self.redaction_rules),
            "export redaction rule IDs",
        )
        if self.audience.requires_redaction_review() and not self.redaction_rules:
            raise ContractValueError(
                "external-review export audiences require redaction_rules."
            )
        if self.status.can_be_exported() and not self.package_format.is_machine_readable():
            raise ContractValueError(
                "export-ready packages require a machine-readable package_format."
            )

    def artifact_ids(self) -> tuple[str, ...]:
        """Return artifact IDs in package order."""

        return tuple(artifact.artifact_id for artifact in self.artifacts)

    def artifact_ids_by_kind(self, kind: ExportArtifactKind) -> tuple[str, ...]:
        """Return artifact IDs matching an artifact kind."""

        return tuple(
            artifact.artifact_id for artifact in self.artifacts if artifact.kind is kind
        )

    def runtime_artifact_ids(self) -> tuple[str, ...]:
        """Return artifact IDs that describe runtime behavior."""

        return tuple(
            artifact.artifact_id
            for artifact in self.artifacts
            if artifact.kind.is_runtime_artifact()
        )

    def sensitive_artifact_ids(self) -> tuple[str, ...]:
        """Return artifact IDs requiring redaction review."""

        return tuple(
            artifact.artifact_id for artifact in self.artifacts if artifact.needs_redaction_review()
        )

    def required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs referenced by the export package."""

        bundle_ids: list[str] = list(self.evidence_bundle_ids)
        for artifact in self.artifacts:
            bundle_ids.extend(artifact.evidence_bundle_ids)
        for rule in self.redaction_rules:
            bundle_ids.extend(rule.evidence_bundle_ids)
        return tuple(dict.fromkeys(bundle_ids))

    def required_provenance_manifest_ids(self) -> tuple[str, ...]:
        """Return unique provenance manifest IDs referenced by the package."""

        manifest_ids: list[str] = list(self.provenance_manifest_ids)
        for artifact in self.artifacts:
            manifest_ids.extend(artifact.provenance_manifest_ids)
        return tuple(dict.fromkeys(manifest_ids))

    def is_export_ready(self) -> bool:
        """Return whether the manifest is structurally ready to export."""

        return (
            self.status.can_be_exported()
            and self.package_format.is_machine_readable()
            and bool(self.artifacts)
            and bool(self.required_evidence_bundle_ids())
        )


def _reject_duplicate_ids(values: tuple[str, ...], field_name: str) -> None:
    """Reject duplicate identifier tuples."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
