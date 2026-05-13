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
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError


def _artifact(
    *,
    artifact_id: str = "artifact-run-ledger-001",
    kind: DossierArtifactKind = DossierArtifactKind.RUN_LEDGER,
    evidence_bundle_ids: tuple[str, ...] = ("ev-run-ledger-001",),
    provenance_manifest_ids: tuple[str, ...] = ("manifest-run-ledger-001",),
) -> DossierArtifactReference:
    return DossierArtifactReference(
        artifact_id=artifact_id,
        kind=kind,
        title=f"{kind.value} artifact",
        source_record_id=f"source-{artifact_id}",
        evidence_bundle_ids=evidence_bundle_ids,
        provenance_manifest_ids=provenance_manifest_ids,
        notes=("reviewable artifact",),
    )


def _evidence_reference(
    *,
    reference_id: str = "evidence-ref-runtime-001",
    evidence_bundle_id: str = "ev-run-ledger-001",
) -> DossierEvidenceReference:
    return DossierEvidenceReference(
        reference_id=reference_id,
        evidence_bundle_id=evidence_bundle_id,
        supports_artifact_ids=("artifact-run-ledger-001",),
        supports_requirement_ids=("req-runtime-boundary",),
        supports_hazard_ids=("hazard-runtime-boundary",),
    )


def _trace_thread(
    *,
    closure_status: DossierTraceClosureStatus = DossierTraceClosureStatus.CLOSED,
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
        evidence_reference_ids=("evidence-ref-runtime-001",),
        review_workflow_ids=("workflow-review-001",),
        export_package_ids=export_package_ids,
    )


def _manifest(
    *,
    status: AssuranceDossierStatus = AssuranceDossierStatus.TRACE_CLOSED,
    trace_threads: tuple[DossierTraceThread, ...] | None = None,
    artifacts: tuple[DossierArtifactReference, ...] | None = None,
    evidence_references: tuple[DossierEvidenceReference, ...] | None = None,
) -> AssuranceDossierManifest:
    return AssuranceDossierManifest(
        dossier_id="dossier-runtime-001",
        case_id="case-runtime-001",
        title="Runtime assurance trace-closure dossier",
        status=status,
        created_at_utc="2026-05-12T15:00:00Z",
        trace_threads=trace_threads if trace_threads is not None else (_trace_thread(),),
        artifacts=artifacts
        if artifacts is not None
        else (
            _artifact(),
            _artifact(
                artifact_id="artifact-review-workflow-001",
                kind=DossierArtifactKind.REVIEW_WORKFLOW,
                evidence_bundle_ids=("ev-review-workflow-001",),
                provenance_manifest_ids=("manifest-review-workflow-001",),
            ),
            _artifact(
                artifact_id="artifact-export-package-001",
                kind=DossierArtifactKind.EXPORT_PACKAGE,
                evidence_bundle_ids=("ev-export-package-001",),
                provenance_manifest_ids=("manifest-export-package-001",),
            ),
        ),
        evidence_references=(
            evidence_references if evidence_references is not None else (_evidence_reference(),)
        ),
        notes=("Local prototype dossier.",),
    )


def test_assurance_dossier_manifest_tracks_trace_evidence_runtime_and_export_links() -> None:
    manifest = _manifest()

    assert manifest.is_trace_closed()
    assert manifest.trace_thread_ids() == ("trace-thread-runtime-001",)
    assert manifest.open_trace_thread_ids() == ()
    assert manifest.blocking_trace_thread_ids() == ()
    assert manifest.runtime_artifact_ids() == ("artifact-run-ledger-001",)
    assert manifest.closure_artifact_ids() == (
        "artifact-review-workflow-001",
        "artifact-export-package-001",
    )
    assert manifest.required_evidence_bundle_ids() == (
        "ev-run-ledger-001",
        "ev-review-workflow-001",
        "ev-export-package-001",
    )
    assert manifest.required_provenance_manifest_ids() == (
        "manifest-run-ledger-001",
        "manifest-review-workflow-001",
        "manifest-export-package-001",
    )
    assert manifest.export_package_ids() == ("export-case-runtime-001",)


def test_trace_closed_dossier_rejects_open_trace_thread() -> None:
    with pytest.raises(ContractValueError, match="cannot contain open trace threads"):
        _manifest(
            trace_threads=(
                _trace_thread(
                    closure_status=DossierTraceClosureStatus.PARTIAL,
                    export_package_ids=(),
                ),
            )
        )


def test_draft_dossier_can_hold_open_trace_thread_for_work_in_progress() -> None:
    manifest = _manifest(
        status=AssuranceDossierStatus.DRAFT,
        trace_threads=(
            _trace_thread(
                closure_status=DossierTraceClosureStatus.PARTIAL,
                export_package_ids=(),
            ),
        ),
    )

    assert not manifest.is_trace_closed()
    assert manifest.open_trace_thread_ids() == ("trace-thread-runtime-001",)


def test_closed_trace_thread_requires_export_package_link() -> None:
    with pytest.raises(ContractValueError, match="closed dossier trace threads"):
        _trace_thread(export_package_ids=())


def test_dossier_artifact_requires_evidence_unless_provenance_manifest() -> None:
    with pytest.raises(ContractValueError, match="dossier artifacts require evidence"):
        _artifact(evidence_bundle_ids=())

    provenance_artifact = _artifact(
        kind=DossierArtifactKind.PROVENANCE_MANIFEST,
        evidence_bundle_ids=(),
        provenance_manifest_ids=("manifest-run-ledger-001",),
    )

    assert provenance_artifact.kind.is_closure_artifact()
    assert provenance_artifact.is_provenance_backed()


def test_dossier_evidence_reference_requires_artifact_and_requirement_links() -> None:
    with pytest.raises(ContractValueError, match="supports_artifact_ids"):
        DossierEvidenceReference(
            reference_id="evidence-ref-empty-artifact",
            evidence_bundle_id="ev-run-ledger-001",
            supports_artifact_ids=(),
            supports_requirement_ids=("req-runtime-boundary",),
        )

    with pytest.raises(ContractValueError, match="supports_requirement_ids"):
        DossierEvidenceReference(
            reference_id="evidence-ref-empty-requirement",
            evidence_bundle_id="ev-run-ledger-001",
            supports_artifact_ids=("artifact-run-ledger-001",),
            supports_requirement_ids=(),
        )


def test_assurance_dossier_manifest_rejects_duplicate_record_ids() -> None:
    thread = _trace_thread()
    artifact = _artifact()
    evidence_reference = _evidence_reference()

    with pytest.raises(ContractValueError, match="dossier trace thread IDs"):
        _manifest(trace_threads=(thread, thread))

    with pytest.raises(ContractValueError, match="dossier artifact IDs"):
        _manifest(artifacts=(artifact, artifact))

    with pytest.raises(ContractValueError, match="dossier evidence reference IDs"):
        _manifest(evidence_references=(evidence_reference, evidence_reference))


def test_assurance_dossier_records_validate_identifiers_and_timestamps() -> None:
    with pytest.raises(ContractValueError, match="dossier_id must not contain spaces"):
        AssuranceDossierManifest(
            dossier_id="dossier runtime",
            case_id="case-runtime-001",
            title="Runtime assurance trace-closure dossier",
            status=AssuranceDossierStatus.DRAFT,
            created_at_utc="2026-05-12T15:00:00Z",
            trace_threads=(_trace_thread(),),
            artifacts=(_artifact(),),
            evidence_references=(_evidence_reference(),),
        )

    with pytest.raises(ContractValueError, match="must include a timezone"):
        AssuranceDossierManifest(
            dossier_id="dossier-runtime-001",
            case_id="case-runtime-001",
            title="Runtime assurance trace-closure dossier",
            status=AssuranceDossierStatus.DRAFT,
            created_at_utc="2026-05-12T15:00:00",
            trace_threads=(_trace_thread(),),
            artifacts=(_artifact(),),
            evidence_references=(_evidence_reference(),),
        )
