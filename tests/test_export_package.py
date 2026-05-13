from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.export_package import (
    ExportArtifactKind,
    ExportArtifactReference,
    ExportPackageAudience,
    ExportPackageFormat,
    ExportPackageManifest,
    ExportPackageStatus,
    ExportRedactionRule,
)


def _artifact(
    *,
    artifact_id: str = "artifact-run-ledger-001",
    kind: ExportArtifactKind = ExportArtifactKind.RUN_LEDGER,
    evidence_bundle_ids: tuple[str, ...] = ("ev-run-ledger-001",),
    provenance_manifest_ids: tuple[str, ...] = ("manifest-run-ledger-001",),
    contains_sensitive_fields: bool = False,
) -> ExportArtifactReference:
    return ExportArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        title="Run ledger artifact",
        source_record_id="run-ledger-001",
        evidence_bundle_ids=evidence_bundle_ids,
        provenance_manifest_ids=provenance_manifest_ids,
        tags=("runtime", "ledger"),
        contains_sensitive_fields=contains_sensitive_fields,
    )


def _redaction_rule() -> ExportRedactionRule:
    return ExportRedactionRule(
        rule_id="redact-operator-ids",
        target_artifact_kinds=(
            ExportArtifactKind.RUN_LEDGER,
            ExportArtifactKind.REVIEW_WORKFLOW,
        ),
        field_path="records[*].operator_id",
        rationale="Operator identifiers are not required for open technical review.",
        evidence_bundle_ids=("ev-redaction-001",),
    )


def _manifest(
    *,
    status: ExportPackageStatus = ExportPackageStatus.READY_TO_EXPORT,
    package_format: ExportPackageFormat = ExportPackageFormat.JSON,
    audience: ExportPackageAudience = ExportPackageAudience.FEDERAL_EVALUATION,
    artifacts: tuple[ExportArtifactReference, ...] | None = None,
    redaction_rules: tuple[ExportRedactionRule, ...] | None = None,
) -> ExportPackageManifest:
    return ExportPackageManifest(
        package_id="export-case-runtime-001",
        case_id="case-runtime-001",
        title="Runtime assurance export package",
        status=status,
        package_format=package_format,
        audience=audience,
        created_at_utc="2026-05-12T14:00:00Z",
        artifacts=artifacts if artifacts is not None else (_artifact(),),
        evidence_bundle_ids=("ev-export-manifest-001",),
        redaction_rules=redaction_rules if redaction_rules is not None else (_redaction_rule(),),
        provenance_manifest_ids=("manifest-export-001",),
        notes=("Local prototype export package.",),
    )


def test_export_manifest_tracks_artifacts_evidence_provenance_and_redaction() -> None:
    sensitive_artifact = _artifact(
        artifact_id="artifact-review-workflow-001",
        kind=ExportArtifactKind.REVIEW_WORKFLOW,
        evidence_bundle_ids=("ev-review-workflow-001",),
        provenance_manifest_ids=("manifest-review-workflow-001",),
        contains_sensitive_fields=True,
    )
    manifest = _manifest(artifacts=(_artifact(), sensitive_artifact))

    assert manifest.is_export_ready()
    assert manifest.artifact_ids() == (
        "artifact-run-ledger-001",
        "artifact-review-workflow-001",
    )
    assert manifest.runtime_artifact_ids() == ("artifact-run-ledger-001",)
    assert manifest.sensitive_artifact_ids() == ("artifact-review-workflow-001",)
    assert manifest.artifact_ids_by_kind(ExportArtifactKind.RUN_LEDGER) == (
        "artifact-run-ledger-001",
    )
    assert manifest.required_evidence_bundle_ids() == (
        "ev-export-manifest-001",
        "ev-run-ledger-001",
        "ev-review-workflow-001",
        "ev-redaction-001",
    )
    assert manifest.required_provenance_manifest_ids() == (
        "manifest-export-001",
        "manifest-run-ledger-001",
        "manifest-review-workflow-001",
    )


def test_export_artifact_requires_evidence_for_required_evidence_backed_kinds() -> None:
    with pytest.raises(ContractValueError, match="required export artifacts"):
        _artifact(evidence_bundle_ids=())

    metadata = _artifact(
        kind=ExportArtifactKind.REPOSITORY_METADATA,
        evidence_bundle_ids=(),
        provenance_manifest_ids=(),
    )

    assert metadata.kind.requires_evidence_reference() is False


def test_export_artifact_rejects_duplicate_references_and_tags() -> None:
    with pytest.raises(ContractValueError, match="duplicate identifiers"):
        _artifact(evidence_bundle_ids=("ev-001", "ev-001"))

    with pytest.raises(ContractValueError, match="duplicate values"):
        _artifact().__class__(
            artifact_id="artifact-duplicate-tags",
            kind=ExportArtifactKind.RUN_LEDGER,
            title="Duplicate tags",
            source_record_id="run-ledger-001",
            evidence_bundle_ids=("ev-run-ledger-001",),
            tags=("runtime", "runtime"),
        )


def test_redaction_rule_requires_target_kinds_and_evidence_when_required() -> None:
    with pytest.raises(ContractValueError, match="target_artifact_kinds"):
        ExportRedactionRule(
            rule_id="redact-empty",
            target_artifact_kinds=(),
            field_path="records[*].operator_id",
            rationale="No targets.",
            evidence_bundle_ids=("ev-redaction-001",),
        )

    with pytest.raises(ContractValueError, match="required redaction rules"):
        ExportRedactionRule(
            rule_id="redact-no-evidence",
            target_artifact_kinds=(ExportArtifactKind.RUN_LEDGER,),
            field_path="records[*].operator_id",
            rationale="No evidence.",
        )


def test_external_audiences_require_redaction_rules() -> None:
    with pytest.raises(ContractValueError, match="external-review export audiences"):
        _manifest(redaction_rules=())

    local_manifest = _manifest(
        audience=ExportPackageAudience.LOCAL_REVIEW,
        redaction_rules=(),
    )

    assert local_manifest.audience.requires_redaction_review() is False


def test_export_ready_manifest_requires_machine_readable_format() -> None:
    with pytest.raises(ContractValueError, match="machine-readable package_format"):
        _manifest(package_format=ExportPackageFormat.MARKDOWN)

    draft_markdown = _manifest(
        status=ExportPackageStatus.DRAFT,
        package_format=ExportPackageFormat.MARKDOWN,
    )

    assert not draft_markdown.is_export_ready()
    assert ExportPackageFormat.MARKDOWN.is_machine_readable() is False


def test_export_manifest_rejects_duplicate_artifacts_and_rules() -> None:
    artifact = _artifact()
    rule = _redaction_rule()

    with pytest.raises(ContractValueError, match="export artifact IDs"):
        _manifest(artifacts=(artifact, artifact))

    with pytest.raises(ContractValueError, match="export redaction rule IDs"):
        _manifest(redaction_rules=(rule, rule))


def test_export_manifest_validates_required_fields() -> None:
    with pytest.raises(ContractValueError, match="package_id must not contain spaces"):
        ExportPackageManifest(
            package_id="export package",
            case_id="case-runtime-001",
            title="Runtime assurance export package",
            status=ExportPackageStatus.DRAFT,
            package_format=ExportPackageFormat.JSON,
            audience=ExportPackageAudience.LOCAL_REVIEW,
            created_at_utc="2026-05-12T14:00:00Z",
            artifacts=(_artifact(),),
        )

    with pytest.raises(ContractValueError, match="must include a timezone"):
        ExportPackageManifest(
            package_id="export-case-runtime-001",
            case_id="case-runtime-001",
            title="Runtime assurance export package",
            status=ExportPackageStatus.DRAFT,
            package_format=ExportPackageFormat.JSON,
            audience=ExportPackageAudience.LOCAL_REVIEW,
            created_at_utc="2026-05-12T14:00:00",
            artifacts=(_artifact(),),
        )
