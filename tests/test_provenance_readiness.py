from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.provenance import (
    ArtifactDigest,
    ProvenanceArtifactType,
    ProvenanceAttestation,
    ProvenanceDigestAlgorithm,
    ProvenanceManifest,
    ProvenanceSignature,
    ProvenanceSignatureAlgorithm,
    ProvenanceSignerIdentity,
    ProvenanceSignerRole,
    ProvenanceTrustLevel,
    ProvenanceVerificationStatus,
)
from ix_autonomy_assurance_case_runtime.provenance_readiness import (
    ProvenanceLayerReadinessEvaluator,
    ProvenanceReadinessDecision,
    ProvenanceReadinessFinding,
    ProvenanceReadinessFindingSeverity,
    ProvenanceReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)


VALID_SHA256 = "a" * 64


def _digest(
    *,
    digest_id: str = "digest-evidence-001",
    artifact_id: str = "ev-framework-crosswalk-001",
    artifact_type: ProvenanceArtifactType = ProvenanceArtifactType.EVIDENCE_BUNDLE,
) -> ArtifactDigest:
    return ArtifactDigest(
        digest_id=digest_id,
        artifact_id=artifact_id,
        artifact_type=artifact_type,
        algorithm=ProvenanceDigestAlgorithm.SHA256,
        digest_hex=VALID_SHA256,
        generated_at_utc="2026-05-12T12:00:00Z",
        size_bytes=1024,
    )


def _signer(
    *,
    signer_id: str = "signer-system-owner-001",
    role: ProvenanceSignerRole = ProvenanceSignerRole.SYSTEM_OWNER,
    trust_level: ProvenanceTrustLevel = ProvenanceTrustLevel.SIGNED_BY_IDENTIFIED_KEY,
) -> ProvenanceSignerIdentity:
    return ProvenanceSignerIdentity(
        signer_id=signer_id,
        display_name="System Owner",
        role=role,
        key_id=f"key-{signer_id}",
        organization="Assurance Lab",
        trust_level=trust_level,
    )


def _signature(
    *,
    signature_id: str = "sig-evidence-001",
    digest_id: str = "digest-evidence-001",
    signer_id: str = "signer-system-owner-001",
    algorithm: ProvenanceSignatureAlgorithm = ProvenanceSignatureAlgorithm.ED25519,
    status: ProvenanceVerificationStatus = ProvenanceVerificationStatus.VERIFIED,
) -> ProvenanceSignature:
    return ProvenanceSignature(
        signature_id=signature_id,
        digest_id=digest_id,
        signer_id=signer_id,
        algorithm=algorithm,
        status=status,
        signed_at_utc="2026-05-12T12:01:00Z",
        signature_value="signed-artifact-digest-placeholder",
    )


def _attestation(
    *,
    signature_ids: tuple[str, ...] = ("sig-evidence-001",),
    subject_artifact_ids: tuple[str, ...] = ("ev-framework-crosswalk-001",),
) -> ProvenanceAttestation:
    return ProvenanceAttestation(
        attestation_id="attestation-evidence-001",
        predicate_type="ix.assurance.provenance.v1",
        issuer="Assurance Lab",
        issued_at_utc="2026-05-12T12:02:00Z",
        subject_artifact_ids=subject_artifact_ids,
        digest_ids=("digest-evidence-001",),
        signature_ids=signature_ids,
    )


def _manifest(
    *,
    digest: ArtifactDigest | None = None,
    signer: ProvenanceSignerIdentity | None = None,
    signature: ProvenanceSignature | None = None,
    attestation: ProvenanceAttestation | None = None,
) -> ProvenanceManifest:
    actual_digest = digest or _digest()
    actual_signature = signature or _signature(digest_id=actual_digest.digest_id)
    actual_attestation = attestation or _attestation(
        subject_artifact_ids=(actual_digest.artifact_id,)
    )
    return ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(actual_digest,),
        signer_identities=(signer or _signer(),),
        signatures=(actual_signature,),
        attestations=(actual_attestation,),
    )


def test_provenance_readiness_completes_with_verified_audit_artifact_manifest() -> None:
    report = ProvenanceLayerReadinessEvaluator().evaluate(_manifest())

    assert report.decision is ProvenanceReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == ("signed-provenance",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "provenance-readiness: complete "
        "(0 blocker(s), 0 warning(s), capability=signed-provenance)"
    )


def test_provenance_readiness_feeds_prototype_claim_gate() -> None:
    report = ProvenanceLayerReadinessEvaluator().evaluate(_manifest())

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=(
            "registry-layer",
            "policy-pack-engine",
            "framework-crosswalks",
        ),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 56
    assert prototype_report.completed_capability_ids == (
        "registry-layer",
        "policy-pack-engine",
        "framework-crosswalks",
        "signed-provenance",
    )
    assert "telemetry-adapters" in prototype_report.remaining_capability_ids


def test_provenance_readiness_blocks_failed_signature_manifest() -> None:
    report = ProvenanceLayerReadinessEvaluator().evaluate(
        _manifest(
            signature=_signature(status=ProvenanceVerificationStatus.FAILED),
        )
    )

    assert report.decision is ProvenanceReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert report.blocker_count >= 1
    assert any(
        finding.source is ProvenanceReadinessFindingSource.VERIFICATION
        for finding in report.findings_for_signature("sig-evidence-001")
    )


def test_provenance_readiness_is_limited_for_non_authority_audit_artifact_signer() -> None:
    report = ProvenanceLayerReadinessEvaluator().evaluate(
        _manifest(
            signer=_signer(
                role=ProvenanceSignerRole.BUILD_SYSTEM,
                trust_level=ProvenanceTrustLevel.SIGNED_BY_IDENTIFIED_KEY,
            )
        )
    )

    assert report.decision is ProvenanceReadinessDecision.LIMITED
    assert not report.is_complete()
    assert report.warning_count == 1
    assert report.findings_for_artifact("ev-framework-crosswalk-001")[0].source is (
        ProvenanceReadinessFindingSource.VERIFICATION
    )


def test_provenance_readiness_blocks_manifest_without_audit_facing_artifacts() -> None:
    digest = _digest(
        artifact_id="model-card-nav-001",
        artifact_type=ProvenanceArtifactType.MODEL_CARD,
    )
    report = ProvenanceLayerReadinessEvaluator().evaluate(
        _manifest(
            digest=digest,
            signature=_signature(digest_id=digest.digest_id),
            attestation=_attestation(subject_artifact_ids=(digest.artifact_id,)),
        )
    )

    assert report.decision is ProvenanceReadinessDecision.BLOCKED
    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "provenance-readiness-no-audit-artifacts"
    assert report.findings[0].source is ProvenanceReadinessFindingSource.READINESS


def test_provenance_readiness_blocks_unsigned_attestation() -> None:
    report = ProvenanceLayerReadinessEvaluator().evaluate(
        _manifest(attestation=_attestation(signature_ids=()))
    )

    assert report.decision is ProvenanceReadinessDecision.BLOCKED
    assert report.findings_for_attestation("attestation-evidence-001")[0].finding_id == (
        "verification-attestation-attestation-evidence-001-unsigned"
    )


def test_provenance_readiness_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ProvenanceReadinessFinding(
            finding_id="bad-finding",
            severity=ProvenanceReadinessFindingSeverity.BLOCKER,
            source=ProvenanceReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank signer ID"):
        ProvenanceReadinessFinding(
            finding_id="bad-finding",
            severity=ProvenanceReadinessFindingSeverity.BLOCKER,
            source=ProvenanceReadinessFindingSource.VERIFICATION,
            message="Bad finding.",
            signer_id="",
        )
