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
from ix_autonomy_assurance_case_runtime.export_package_readiness import (
    EXPORT_PACKAGE_CAPABILITY_ID,
    ExportPackageLayerReadinessEvaluator,
    ExportPackageReadinessDecision,
    ExportPackageReadinessFinding,
    ExportPackageReadinessFindingSeverity,
    ExportPackageReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
)


def _artifact(
    *,
    artifact_id: str,
    kind: ExportArtifactKind,
    evidence_bundle_ids: tuple[str, ...],
    provenance_manifest_ids: tuple[str, ...],
    contains_sensitive_fields: bool = False,
) -> ExportArtifactReference:
    return ExportArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        title=f"{kind.value} artifact",
        source_record_id=f"source-{artifact_id}",
        evidence_bundle_ids=evidence_bundle_ids,
        provenance_manifest_ids=provenance_manifest_ids,
        tags=("export", kind.value),
        contains_sensitive_fields=contains_sensitive_fields,
    )


def _required_artifacts() -> tuple[ExportArtifactReference, ...]:
    return (
        _artifact(
            artifact_id="artifact-assurance-case-001",
            kind=ExportArtifactKind.ASSURANCE_CASE,
            evidence_bundle_ids=("ev-assurance-case-001",),
            provenance_manifest_ids=("manifest-assurance-case-001",),
        ),
        _artifact(
            artifact_id="artifact-traceability-001",
            kind=ExportArtifactKind.TRACEABILITY_GRAPH,
            evidence_bundle_ids=("ev-traceability-001",),
            provenance_manifest_ids=("manifest-traceability-001",),
        ),
        _artifact(
            artifact_id="artifact-evidence-bundle-001",
            kind=ExportArtifactKind.EVIDENCE_BUNDLE,
            evidence_bundle_ids=("ev-evidence-bundle-001",),
            provenance_manifest_ids=("manifest-evidence-bundle-001",),
        ),
        _artifact(
            artifact_id="artifact-readiness-report-001",
            kind=ExportArtifactKind.READINESS_REPORT,
            evidence_bundle_ids=("ev-readiness-report-001",),
            provenance_manifest_ids=("manifest-readiness-report-001",),
        ),
        _artifact(
            artifact_id="artifact-review-workflow-001",
            kind=ExportArtifactKind.REVIEW_WORKFLOW,
            evidence_bundle_ids=("ev-review-workflow-001",),
            provenance_manifest_ids=("manifest-review-workflow-001",),
            contains_sensitive_fields=True,
        ),
        _artifact(
            artifact_id="artifact-run-ledger-001",
            kind=ExportArtifactKind.RUN_LEDGER,
            evidence_bundle_ids=("ev-run-ledger-001",),
            provenance_manifest_ids=("manifest-run-ledger-001",),
        ),
    )


def _minimal_runtime_artifact() -> ExportArtifactReference:
    return _artifact(
        artifact_id="artifact-run-ledger-001",
        kind=ExportArtifactKind.RUN_LEDGER,
        evidence_bundle_ids=("ev-run-ledger-001",),
        provenance_manifest_ids=("manifest-run-ledger-001",),
    )


def _redaction_rule() -> ExportRedactionRule:
    return ExportRedactionRule(
        rule_id="redact-review-fields",
        target_artifact_kinds=(ExportArtifactKind.REVIEW_WORKFLOW,),
        field_path="review.actor.display_name",
        rationale="Reviewer display details are not required for external package review.",
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
        artifacts=artifacts if artifacts is not None else _required_artifacts(),
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


def _all_evidence_bundle_ids() -> tuple[str, ...]:
    return (
        "ev-export-manifest-001",
        "ev-assurance-case-001",
        "ev-traceability-001",
        "ev-evidence-bundle-001",
        "ev-readiness-report-001",
        "ev-review-workflow-001",
        "ev-run-ledger-001",
        "ev-redaction-001",
    )


def _bundles(*, unhashed: str | None = None) -> tuple[EvidenceBundle, ...]:
    return tuple(
        _bundle(bundle_id, hashed=bundle_id != unhashed)
        for bundle_id in _all_evidence_bundle_ids()
    )


def _all_provenance_manifest_ids() -> tuple[str, ...]:
    return (
        "manifest-export-001",
        "manifest-assurance-case-001",
        "manifest-traceability-001",
        "manifest-evidence-bundle-001",
        "manifest-readiness-report-001",
        "manifest-review-workflow-001",
        "manifest-run-ledger-001",
    )


def _evaluator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
    provenance_manifest_ids: tuple[str, ...] = _all_provenance_manifest_ids(),
) -> ExportPackageLayerReadinessEvaluator:
    return ExportPackageLayerReadinessEvaluator(
        evidence_bundles=_bundles() if evidence_bundles is None else evidence_bundles,
        provenance_manifest_ids=provenance_manifest_ids,
    )


def test_export_package_readiness_completes_clean_export_manifest() -> None:
    report = _evaluator().evaluate(_manifest())

    assert report.decision is ExportPackageReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (EXPORT_PACKAGE_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "export-package-readiness: complete "
        "(6 artifact(s), 1 redaction rule(s), 8 evidence bundle(s), "
        "7 provenance manifest(s), 0 blocker(s), 0 warning(s), "
        "capability=audit-report-export)"
    )


def test_export_package_readiness_feeds_prototype_claim_gate() -> None:
    report = _evaluator().evaluate(_manifest())

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=(
            "registry-layer",
            "policy-pack-engine",
            "framework-crosswalks",
            "signed-provenance",
            "telemetry-adapters",
            "scenario-campaign-runner",
            "monitoring-incidents",
            "review-workflow",
        ),
    )

    assert EXPORT_PACKAGE_CAPABILITY_ID in prototype_report.completed_capability_ids


def test_export_package_readiness_limited_when_validation_has_warnings() -> None:
    manifest = _manifest(
        artifacts=(_minimal_runtime_artifact(),),
        redaction_rules=(_redaction_rule(),),
    )
    report = _evaluator(
        evidence_bundles=(
            _bundle("ev-export-manifest-001"),
            _bundle("ev-run-ledger-001"),
            _bundle("ev-redaction-001"),
        ),
        provenance_manifest_ids=("manifest-export-001", "manifest-run-ledger-001"),
    ).evaluate(manifest)

    assert report.decision is ExportPackageReadinessDecision.LIMITED
    assert report.warning_count == 5
    assert not report.is_complete()


def test_export_package_readiness_blocks_non_export_ready_manifest() -> None:
    report = _evaluator().evaluate(
        _manifest(
            status=ExportPackageStatus.READY_FOR_REVIEW,
            audience=ExportPackageAudience.LOCAL_REVIEW,
            redaction_rules=(),
        )
    )

    assert report.decision is ExportPackageReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "package-export-case-runtime-001-not-export-ready"
        for finding in report.findings_for_package("export-case-runtime-001")
    )


def test_export_package_readiness_blocks_missing_runtime_artifacts() -> None:
    report = _evaluator(
        evidence_bundles=tuple(
            _bundle(bundle_id)
            for bundle_id in (
                "ev-export-manifest-001",
                "ev-assurance-case-001",
                "ev-traceability-001",
                "ev-evidence-bundle-001",
                "ev-readiness-report-001",
                "ev-review-workflow-001",
                "ev-redaction-001",
            )
        ),
        provenance_manifest_ids=(
            "manifest-export-001",
            "manifest-assurance-case-001",
            "manifest-traceability-001",
            "manifest-evidence-bundle-001",
            "manifest-readiness-report-001",
            "manifest-review-workflow-001",
        ),
    ).evaluate(_manifest(artifacts=_required_artifacts()[:-1]))

    assert report.decision is ExportPackageReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "package-export-case-runtime-001-no-runtime-artifacts"
        for finding in report.findings_for_package("export-case-runtime-001")
    )


def test_export_package_readiness_blocks_missing_evidence() -> None:
    report = _evaluator(evidence_bundles=()).evaluate(_manifest())

    assert report.decision is ExportPackageReadinessDecision.BLOCKED
    assert report.findings_for_evidence_bundle("ev-export-manifest-001")


def test_export_package_readiness_blocks_missing_provenance() -> None:
    report = _evaluator(provenance_manifest_ids=("manifest-export-001",)).evaluate(_manifest())

    assert report.decision is ExportPackageReadinessDecision.BLOCKED
    assert report.findings_for_provenance_manifest("manifest-run-ledger-001")


def test_export_package_readiness_limited_for_evidence_warnings() -> None:
    report = _evaluator(evidence_bundles=_bundles(unhashed="ev-run-ledger-001")).evaluate(
        _manifest()
    )

    assert report.decision is ExportPackageReadinessDecision.LIMITED
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-run-ledger-001")


def test_export_package_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ExportPackageReadinessFinding(
            finding_id="finding-export-readiness-001",
            severity=ExportPackageReadinessFindingSeverity.BLOCKER,
            source=ExportPackageReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="artifact_id must not be blank"):
        ExportPackageReadinessFinding(
            finding_id="finding-export-readiness-001",
            severity=ExportPackageReadinessFindingSeverity.BLOCKER,
            source=ExportPackageReadinessFindingSource.ARTIFACT,
            message="Bad artifact.",
            artifact_id="",
        )
