from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.assurance_dossier import (
    AssuranceDossierManifest,
    AssuranceDossierStatus,
    DossierArtifactKind,
    DossierArtifactReference,
    DossierEvidenceReference,
    DossierTraceClosureStatus,
    DossierTraceThread,
)
from ix_autonomy_assurance_case_runtime.assurance_dossier_readiness import (
    ASSURANCE_DOSSIER_CAPABILITY_ID,
    AssuranceDossierLayerReadinessEvaluator,
    AssuranceDossierReadinessDecision,
    AssuranceDossierReadinessFinding,
    AssuranceDossierReadinessFindingSeverity,
    AssuranceDossierReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord


def _artifact(
    *,
    artifact_id: str,
    kind: DossierArtifactKind,
    source_record_id: str,
    evidence_bundle_ids: tuple[str, ...],
    provenance_manifest_ids: tuple[str, ...],
) -> DossierArtifactReference:
    return DossierArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        title=f"{kind.value} artifact",
        source_record_id=source_record_id,
        evidence_bundle_ids=evidence_bundle_ids,
        provenance_manifest_ids=provenance_manifest_ids,
    )


def _artifacts() -> tuple[DossierArtifactReference, ...]:
    return (
        _artifact(
            artifact_id="artifact-run-ledger-001",
            kind=DossierArtifactKind.RUN_LEDGER,
            source_record_id="run-ledger-001",
            evidence_bundle_ids=("ev-run-ledger-001",),
            provenance_manifest_ids=("manifest-run-ledger-001",),
        ),
        _artifact(
            artifact_id="artifact-review-workflow-001",
            kind=DossierArtifactKind.REVIEW_WORKFLOW,
            source_record_id="workflow-review-001",
            evidence_bundle_ids=("ev-review-workflow-001",),
            provenance_manifest_ids=("manifest-review-workflow-001",),
        ),
        _artifact(
            artifact_id="artifact-export-package-001",
            kind=DossierArtifactKind.EXPORT_PACKAGE,
            source_record_id="export-case-runtime-001",
            evidence_bundle_ids=("ev-export-package-001",),
            provenance_manifest_ids=("manifest-export-package-001",),
        ),
        _artifact(
            artifact_id="artifact-readiness-rollup-001",
            kind=DossierArtifactKind.READINESS_ROLLUP,
            source_record_id="prototype-rollup-001",
            evidence_bundle_ids=("ev-readiness-rollup-001",),
            provenance_manifest_ids=("manifest-readiness-rollup-001",),
        ),
    )


def _runtime_only_artifact() -> DossierArtifactReference:
    return _artifact(
        artifact_id="artifact-run-ledger-001",
        kind=DossierArtifactKind.RUN_LEDGER,
        source_record_id="run-ledger-001",
        evidence_bundle_ids=("ev-run-ledger-001",),
        provenance_manifest_ids=("manifest-run-ledger-001",),
    )


def _evidence_reference(
    *,
    reference_id: str = "evidence-ref-runtime-001",
    supports_artifact_ids: tuple[str, ...] = ("artifact-run-ledger-001",),
    supports_requirement_ids: tuple[str, ...] = ("req-runtime-boundary",),
    supports_hazard_ids: tuple[str, ...] = ("hazard-runtime-boundary",),
) -> DossierEvidenceReference:
    return DossierEvidenceReference(
        reference_id=reference_id,
        evidence_bundle_id="ev-run-ledger-001",
        supports_artifact_ids=supports_artifact_ids,
        supports_requirement_ids=supports_requirement_ids,
        supports_hazard_ids=supports_hazard_ids,
    )


def _trace_thread(
    *,
    closure_status: DossierTraceClosureStatus = DossierTraceClosureStatus.CLOSED,
    evidence_reference_ids: tuple[str, ...] = ("evidence-ref-runtime-001",),
    review_workflow_ids: tuple[str, ...] = ("workflow-review-001",),
    export_package_ids: tuple[str, ...] = ("export-case-runtime-001",),
) -> DossierTraceThread:
    return DossierTraceThread(
        trace_thread_id="trace-thread-runtime-001",
        mission_need_id="mission-need-runtime",
        closure_status=closure_status,
        requirement_ids=("req-runtime-boundary",),
        scenario_ids=("scenario-degraded-nav",),
        hazard_ids=("hazard-runtime-boundary",),
        control_ids=("control-safe-hold",),
        evidence_reference_ids=evidence_reference_ids,
        review_workflow_ids=review_workflow_ids,
        export_package_ids=export_package_ids,
    )


def _manifest(
    *,
    status: AssuranceDossierStatus = AssuranceDossierStatus.TRACE_CLOSED,
    trace_threads: tuple[DossierTraceThread, ...] | None = None,
    artifacts: tuple[DossierArtifactReference, ...] | None = None,
    evidence_references: tuple[DossierEvidenceReference, ...] | None = None,
    disclaimer: str | None = None,
) -> AssuranceDossierManifest:
    return AssuranceDossierManifest(
        dossier_id="dossier-runtime-001",
        case_id="case-runtime-001",
        title="Runtime assurance trace-closure dossier",
        status=status,
        created_at_utc="2026-05-12T15:00:00Z",
        trace_threads=trace_threads if trace_threads is not None else (_trace_thread(),),
        artifacts=artifacts if artifacts is not None else _artifacts(),
        evidence_references=(
            evidence_references
            if evidence_references is not None
            else (_evidence_reference(),)
        ),
        disclaimer=disclaimer
        or (
            "Local prototype assurance dossier only; not an official certification, "
            "authority-to-operate decision, deployment approval, or agency acceptance."
        ),
    )


def _bundle(bundle_id: str, *, hashed: bool = True) -> EvidenceBundle:
    bundle = EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-runtime-001",
        records=(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}",
                kind="assurance-dossier",
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
        "ev-run-ledger-001",
        "ev-review-workflow-001",
        "ev-export-package-001",
        "ev-readiness-rollup-001",
    )
    return tuple(_bundle(bundle_id, hashed=bundle_id != unhashed) for bundle_id in bundle_ids)


def _provenance_manifest_ids() -> tuple[str, ...]:
    return (
        "manifest-run-ledger-001",
        "manifest-review-workflow-001",
        "manifest-export-package-001",
        "manifest-readiness-rollup-001",
    )


def _evaluator(
    *,
    evidence_bundles: tuple[EvidenceBundle, ...] | None = None,
    provenance_manifest_ids: tuple[str, ...] = _provenance_manifest_ids(),
    export_package_ids: tuple[str, ...] = ("export-case-runtime-001",),
) -> AssuranceDossierLayerReadinessEvaluator:
    return AssuranceDossierLayerReadinessEvaluator(
        evidence_bundles=_bundles() if evidence_bundles is None else evidence_bundles,
        provenance_manifest_ids=provenance_manifest_ids,
        export_package_ids=export_package_ids,
    )


def test_assurance_dossier_readiness_completes_clean_trace_closed_dossier() -> None:
    report = _evaluator().evaluate(_manifest())

    assert report.decision is AssuranceDossierReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == (ASSURANCE_DOSSIER_CAPABILITY_ID,)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "assurance-dossier-readiness: complete "
        "(1 trace thread(s), 4 artifact(s), 1 evidence reference(s), "
        "4 evidence bundle(s), 4 provenance manifest(s), 1 export package(s), "
        "0 blocker(s), 0 warning(s), capability=assurance-dossier)"
    )


def test_assurance_dossier_readiness_blocks_draft_or_open_trace_dossier() -> None:
    report = _evaluator().evaluate(
        _manifest(
            status=AssuranceDossierStatus.DRAFT,
            trace_threads=(
                _trace_thread(
                    closure_status=DossierTraceClosureStatus.PARTIAL,
                    export_package_ids=(),
                ),
            ),
        )
    )

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert any(
        finding.finding_id == "dossier-dossier-runtime-001-not-trace-closed"
        for finding in report.findings_for_dossier("dossier-runtime-001")
    )
    assert report.findings_for_trace_thread("trace-thread-runtime-001")


def test_assurance_dossier_readiness_blocks_missing_closure_artifacts() -> None:
    report = _evaluator(
        evidence_bundles=(_bundle("ev-run-ledger-001"),),
        provenance_manifest_ids=("manifest-run-ledger-001",),
    ).evaluate(
        _manifest(
            artifacts=(_runtime_only_artifact(),),
        )
    )

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "dossier-dossier-runtime-001-no-closure-artifacts"
        for finding in report.findings_for_dossier("dossier-runtime-001")
    )


def test_assurance_dossier_readiness_blocks_missing_evidence_bundle() -> None:
    report = _evaluator(evidence_bundles=()).evaluate(_manifest())

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert report.findings_for_evidence_bundle("ev-run-ledger-001")


def test_assurance_dossier_readiness_blocks_missing_provenance_manifest() -> None:
    report = _evaluator(
        provenance_manifest_ids=("manifest-run-ledger-001",),
    ).evaluate(_manifest())

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert report.findings_for_provenance_manifest("manifest-review-workflow-001")


def test_assurance_dossier_readiness_blocks_missing_export_package() -> None:
    report = _evaluator(export_package_ids=()).evaluate(_manifest())

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert report.findings_for_export_package("export-case-runtime-001")


def test_assurance_dossier_readiness_limited_for_evidence_warnings() -> None:
    report = _evaluator(evidence_bundles=_bundles(unhashed="ev-run-ledger-001")).evaluate(
        _manifest()
    )

    assert report.decision is AssuranceDossierReadinessDecision.LIMITED
    assert report.warning_count == 2
    assert report.findings_for_evidence_bundle("ev-run-ledger-001")


def test_assurance_dossier_readiness_blocks_weak_disclaimer() -> None:
    report = _evaluator().evaluate(_manifest(disclaimer="Ready for review."))

    assert report.decision is AssuranceDossierReadinessDecision.BLOCKED
    assert any(
        finding.source is AssuranceDossierReadinessFindingSource.DISCLAIMER
        for finding in report.findings
    )


def test_assurance_dossier_readiness_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        AssuranceDossierReadinessFinding(
            finding_id="finding-dossier-readiness-001",
            severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
            source=AssuranceDossierReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="artifact_id must not be blank"):
        AssuranceDossierReadinessFinding(
            finding_id="finding-dossier-readiness-001",
            severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
            source=AssuranceDossierReadinessFindingSource.ARTIFACT,
            message="Bad artifact.",
            artifact_id="",
        )
