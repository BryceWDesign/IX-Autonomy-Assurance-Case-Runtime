from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.export_package import (
    ExportArtifactKind,
    ExportArtifactReference,
    ExportPackageAudience,
    ExportPackageFormat,
    ExportPackageManifest,
    ExportPackageStatus,
    ExportRedactionRule,
)
from ix_autonomy_assurance_case_runtime.export_package_validation import (
    ExportPackageValidationFinding,
    ExportPackageValidationFindingSeverity,
    ExportPackageValidationFindingSource,
    ExportPackageValidator,
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


def _redaction_rule(
    *,
    rule_id: str = "redact-operator-ids",
    target_artifact_kinds: tuple[ExportArtifactKind, ...] = (ExportArtifactKind.RUN_LEDGER,),
) -> ExportRedactionRule:
    return ExportRedactionRule(
        rule_id=rule_id,
        target_artifact_kinds=target_artifact_kinds,
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
    provenance_manifest_ids: tuple[str, ...] = ("manifest-export-001",),
    disclaimer: str | None = None,
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
        provenance_manifest_ids=provenance_manifest_ids,
        notes=("Local prototype export package.",),
        disclaimer=disclaimer
        or (
            "Local prototype export package only; not an official certification, "
            "authority-to-operate decision, deployment approval, or agency acceptance package."
        ),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-runtime-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="export-package",
                source="unit-test",
                payload={"bundle_id": bundle_id},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    if hashed:
        return bundle.with_computed_hashes()
    return bundle


def _bundles(*, unhashed: str | None = None) -> tuple[EvidenceBundle, ...]:
    bundle_ids = (
        "ev-export-manifest-001",
        "ev-run-ledger-001",
        "ev-redaction-001",
    )
    return tuple(_bundle(bundle_id, hashed=bundle_id != unhashed) for bundle_id in bundle_ids)


def _validator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
    provenance_manifest_ids: tuple[str, ...] = (
        "manifest-export-001",
        "manifest-run-ledger-001",
    ),
) -> ExportPackageValidator:
    return ExportPackageValidator(
        evidence_bundles=_bundles() if evidence_bundles is None else evidence_bundles,
        provenance_manifest_ids=provenance_manifest_ids,
    )


def test_export_package_validator_accepts_grounded_export_manifest() -> None:
    report = _validator().validate(_manifest())

    assert report.is_export_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 5
    assert report.summary() == (
        "export-package-validation: export-case-runtime-001 "
        "(1 artifact(s), 1 redaction rule(s), 3 evidence bundle(s), "
        "2 provenance manifest(s), 0 blocker(s), 5 warning(s))"
    )


def test_export_package_validator_blocks_non_exportable_status() -> None:
    report = _validator().validate(
        _manifest(
            status=ExportPackageStatus.READY_FOR_REVIEW,
            audience=ExportPackageAudience.LOCAL_REVIEW,
            redaction_rules=(),
        )
    )

    assert not report.is_export_ready()
    assert any(
        finding.finding_id == "package-export-case-runtime-001-status-not-exportable"
        for finding in report.findings
    )


def test_export_package_validator_blocks_sensitive_artifact_without_matching_redaction() -> None:
    sensitive_artifact = _artifact(contains_sensitive_fields=True)
    report = _validator().validate(
        _manifest(
            artifacts=(sensitive_artifact,),
            redaction_rules=(
                _redaction_rule(
                    rule_id="redact-policy-fields",
                    target_artifact_kinds=(ExportArtifactKind.POLICY_PACK,),
                ),
            ),
        )
    )

    assert not report.is_export_ready()
    assert report.findings_for_artifact("artifact-run-ledger-001")[0].source is (
        ExportPackageValidationFindingSource.REDACTION
    )


def test_export_package_validator_blocks_runtime_artifact_without_provenance() -> None:
    report = _validator().validate(
        _manifest(
            artifacts=(
                _artifact(
                    provenance_manifest_ids=(),
                ),
            )
        )
    )

    assert not report.is_export_ready()
    assert any(
        finding.finding_id == "artifact-artifact-run-ledger-001-runtime-no-provenance"
        for finding in report.findings_for_artifact("artifact-run-ledger-001")
    )


def test_export_package_validator_blocks_missing_evidence_bundle() -> None:
    report = _validator(evidence_bundles=()).validate(_manifest())

    assert not report.is_export_ready()
    assert report.findings_for_evidence_bundle("ev-export-manifest-001")[0].source is (
        ExportPackageValidationFindingSource.EVIDENCE
    )


def test_export_package_validator_warns_for_unhashed_evidence_bundle() -> None:
    report = _validator(evidence_bundles=_bundles(unhashed="ev-run-ledger-001")).validate(
        _manifest()
    )

    assert report.is_export_ready()
    assert report.warning_count == 7
    assert report.findings_for_evidence_bundle("ev-run-ledger-001")


def test_export_package_validator_blocks_missing_provenance_manifest() -> None:
    report = _validator(provenance_manifest_ids=("manifest-export-001",)).validate(_manifest())

    assert not report.is_export_ready()
    assert report.findings_for_provenance_manifest("manifest-run-ledger-001")[0].source is (
        ExportPackageValidationFindingSource.PROVENANCE
    )


def test_export_package_validator_blocks_missing_manifest_level_provenance() -> None:
    report = _validator(provenance_manifest_ids=("manifest-run-ledger-001",)).validate(
        _manifest(provenance_manifest_ids=())
    )

    assert not report.is_export_ready()
    assert any(
        finding.finding_id == "package-export-case-runtime-001-no-provenance"
        for finding in report.findings
    )


def test_export_package_validator_blocks_weak_disclaimer() -> None:
    report = _validator().validate(
        _manifest(disclaimer="Export package for review.")
    )

    assert not report.is_export_ready()
    assert any(
        finding.source is ExportPackageValidationFindingSource.DISCLAIMER
        for finding in report.findings
    )


def test_export_package_validator_rejects_duplicate_inputs() -> None:
    bundle = _bundle("ev-export-manifest-001")

    with pytest.raises(ContractValueError, match="Duplicate export package evidence"):
        ExportPackageValidator(evidence_bundles=(bundle, bundle))

    with pytest.raises(ContractValueError, match="provenance_manifest_ids"):
        ExportPackageValidator(
            evidence_bundles=(),
            provenance_manifest_ids=("manifest-001", "manifest-001"),
        )


def test_export_package_validation_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ExportPackageValidationFinding(
            finding_id="finding-export-validation-001",
            severity=ExportPackageValidationFindingSeverity.BLOCKER,
            source=ExportPackageValidationFindingSource.PACKAGE,
            message="",
        )

    with pytest.raises(ContractValueError, match="artifact_id must not be blank"):
        ExportPackageValidationFinding(
            finding_id="finding-export-validation-001",
            severity=ExportPackageValidationFindingSeverity.BLOCKER,
            source=ExportPackageValidationFindingSource.ARTIFACT,
            message="Bad artifact.",
            artifact_id="",
        )
