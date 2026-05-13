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
from ix_autonomy_assurance_case_runtime.provenance_verifier import (
    ProvenanceManifestDecision,
    ProvenanceManifestVerifier,
    ProvenanceVerificationFinding,
    ProvenanceVerificationFindingSeverity,
    ProvenanceVerificationFindingSource,
    ProvenanceVerificationPolicy,
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
    attestation_id: str = "attestation-evidence-001",
    signature_ids: tuple[str, ...] = ("sig-evidence-001",),
) -> ProvenanceAttestation:
    return ProvenanceAttestation(
        attestation_id=attestation_id,
        predicate_type="ix.assurance.provenance.v1",
        issuer="Assurance Lab",
        issued_at_utc="2026-05-12T12:02:00Z",
        subject_artifact_ids=("ev-framework-crosswalk-001",),
        digest_ids=("digest-evidence-001",),
        signature_ids=signature_ids,
    )


def _manifest(
    *,
    signer: ProvenanceSignerIdentity | None = None,
    signature: ProvenanceSignature | None = None,
    attestations: tuple[ProvenanceAttestation, ...] | None = None,
) -> ProvenanceManifest:
    actual_signature = signature or _signature()
    return ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(_digest(),),
        signer_identities=(signer or _signer(),),
        signatures=(actual_signature,),
        attestations=(_attestation(),) if attestations is None else attestations,
    )


def test_provenance_manifest_verifier_accepts_complete_external_grade_manifest() -> None:
    report = ProvenanceManifestVerifier().verify(_manifest())

    assert report.decision is ProvenanceManifestDecision.VERIFIED
    assert report.supports_signed_provenance_claim()
    assert report.artifact_count == 1
    assert report.signed_artifact_count == 1
    assert report.attestation_count == 1
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "provenance-verification: verified "
        "(1/1 signed artifact(s), 1 attestation(s), 0 blocker(s), 0 warning(s))"
    )


def test_provenance_manifest_verifier_fails_unsigned_artifact_under_default_policy() -> None:
    manifest = ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(_digest(),),
    )

    report = ProvenanceManifestVerifier().verify(manifest)

    assert report.decision is ProvenanceManifestDecision.FAILED
    assert not report.supports_signed_provenance_claim()
    assert report.signed_artifact_count == 0
    assert report.blocker_count == 3
    assert {
        finding.finding_id
        for finding in report.findings_for_artifact("ev-framework-crosswalk-001")
    } >= {
        "artifact-ev-framework-crosswalk-001-has-no-signature",
        "artifact-ev-framework-crosswalk-001-has-no-attestation",
    }


def test_provenance_manifest_verifier_can_limit_unsigned_artifact_under_relaxed_policy() -> None:
    manifest = ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(_digest(),),
    )
    policy = ProvenanceVerificationPolicy(
        require_external_review_signatures=False,
        require_signed_attestations=False,
        require_attestation_per_artifact=False,
    )

    report = ProvenanceManifestVerifier(policy).verify(manifest)

    assert policy.requires_strong_signed_claims() is False
    assert report.decision is ProvenanceManifestDecision.LIMITED
    assert report.blocker_count == 0
    assert report.warning_count == 1


def test_provenance_manifest_verifier_blocks_failed_signature_status() -> None:
    report = ProvenanceManifestVerifier().verify(
        _manifest(signature=_signature(status=ProvenanceVerificationStatus.FAILED))
    )

    assert report.decision is ProvenanceManifestDecision.FAILED
    assert any(
        finding.finding_id == "signature-sig-evidence-001-status-failed"
        for finding in report.findings_for_signature("sig-evidence-001")
    )


def test_provenance_manifest_verifier_blocks_local_test_signature_for_external_claim() -> None:
    report = ProvenanceManifestVerifier().verify(
        _manifest(
            signature=_signature(
                algorithm=ProvenanceSignatureAlgorithm.LOCAL_DEVELOPMENT_TEST_ONLY,
            )
        )
    )

    assert report.decision is ProvenanceManifestDecision.FAILED
    assert report.signed_artifact_count == 0
    assert any(
        finding.finding_id
        == "signature-sig-evidence-001-algorithm-local_development_test_only-not-external-grade"
        for finding in report.findings
    )


def test_provenance_manifest_verifier_blocks_low_trust_signer_for_external_claim() -> None:
    report = ProvenanceManifestVerifier().verify(
        _manifest(
            signer=_signer(trust_level=ProvenanceTrustLevel.LOCAL_HASH_ONLY),
        )
    )

    assert report.decision is ProvenanceManifestDecision.FAILED
    assert any(
        finding.finding_id == "signer-signer-system-owner-001-trust-local_hash_only"
        for finding in report.findings
    )


def test_provenance_manifest_verifier_warns_when_audit_artifact_has_non_authority_signer() -> None:
    report = ProvenanceManifestVerifier().verify(
        _manifest(
            signer=_signer(
                role=ProvenanceSignerRole.BUILD_SYSTEM,
                trust_level=ProvenanceTrustLevel.SIGNED_BY_IDENTIFIED_KEY,
            )
        )
    )

    assert report.decision is ProvenanceManifestDecision.LIMITED
    assert report.warning_count == 1
    assert report.findings[0].finding_id == (
        "artifact-ev-framework-crosswalk-001-signed-by-non-authority-role"
    )
    assert report.findings[0].source is ProvenanceVerificationFindingSource.SIGNER


def test_provenance_manifest_verifier_blocks_unsigned_attestation() -> None:
    report = ProvenanceManifestVerifier().verify(
        _manifest(attestations=(_attestation(signature_ids=()),))
    )

    assert report.decision is ProvenanceManifestDecision.FAILED
    assert report.findings_for_attestation("attestation-evidence-001")[0].finding_id == (
        "attestation-attestation-evidence-001-unsigned"
    )


def test_provenance_verification_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        ProvenanceVerificationFinding(
            finding_id="bad-finding",
            severity=ProvenanceVerificationFindingSeverity.BLOCKER,
            source=ProvenanceVerificationFindingSource.MANIFEST,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank signature ID"):
        ProvenanceVerificationFinding(
            finding_id="bad-finding",
            severity=ProvenanceVerificationFindingSeverity.BLOCKER,
            source=ProvenanceVerificationFindingSource.SIGNATURE,
            message="Bad finding.",
            signature_id="",
        )
