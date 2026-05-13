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

VALID_SHA256 = "a" * 64


def _digest(
    *,
    digest_id: str = "digest-evidence-001",
    artifact_id: str = "ev-framework-crosswalk-001",
    digest_hex: str = VALID_SHA256,
) -> ArtifactDigest:
    return ArtifactDigest(
        digest_id=digest_id,
        artifact_id=artifact_id,
        artifact_type=ProvenanceArtifactType.EVIDENCE_BUNDLE,
        algorithm=ProvenanceDigestAlgorithm.SHA256,
        digest_hex=digest_hex,
        generated_at_utc="2026-05-12T12:00:00Z",
        size_bytes=1024,
        source_uri="local://evidence/ev-framework-crosswalk-001.json",
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
        key_id="key-system-owner-001",
        organization="Assurance Lab",
        trust_level=trust_level,
        contact="owner@example.invalid",
    )


def _signature(
    *,
    signature_id: str = "sig-evidence-001",
    digest_id: str = "digest-evidence-001",
    signer_id: str = "signer-system-owner-001",
    status: ProvenanceVerificationStatus = ProvenanceVerificationStatus.VERIFIED,
) -> ProvenanceSignature:
    return ProvenanceSignature(
        signature_id=signature_id,
        digest_id=digest_id,
        signer_id=signer_id,
        algorithm=ProvenanceSignatureAlgorithm.ED25519,
        status=status,
        signed_at_utc="2026-05-12T12:01:00Z",
        signature_value="signed-artifact-digest-placeholder",
    )


def _attestation() -> ProvenanceAttestation:
    return ProvenanceAttestation(
        attestation_id="attestation-evidence-001",
        predicate_type="ix.assurance.provenance.v1",
        issuer="Assurance Lab",
        issued_at_utc="2026-05-12T12:02:00Z",
        subject_artifact_ids=("ev-framework-crosswalk-001",),
        digest_ids=("digest-evidence-001",),
        signature_ids=("sig-evidence-001",),
        statement_refs=("local://attestations/attestation-evidence-001.json",),
    )


def test_artifact_digest_validates_sha256_hex_and_timestamp() -> None:
    digest = _digest()

    assert digest.algorithm.hexdigest_length == 64
    assert digest.artifact_type.is_audit_artifact()
    assert digest.generated_at.year == 2026

    with pytest.raises(ContractValueError, match="invalid hexadecimal digest length"):
        _digest(digest_hex="abc")

    with pytest.raises(ContractValueError, match="must be hexadecimal"):
        _digest(digest_hex="g" * 64)

    with pytest.raises(ContractValueError, match="must include a timezone"):
        ArtifactDigest(
            digest_id="digest-evidence-001",
            artifact_id="ev-framework-crosswalk-001",
            artifact_type=ProvenanceArtifactType.EVIDENCE_BUNDLE,
            algorithm=ProvenanceDigestAlgorithm.SHA256,
            digest_hex=VALID_SHA256,
            generated_at_utc="2026-05-12T12:00:00",
        )


def test_signer_identity_tracks_role_trust_and_external_review_posture() -> None:
    signer = _signer()

    assert signer.role.can_support_authority_claim()
    assert signer.can_support_external_review()
    assert ProvenanceTrustLevel.LOCAL_HASH_ONLY.supports_external_review() is False

    with pytest.raises(ContractValueError, match="external attestation readiness"):
        _signer(
            role=ProvenanceSignerRole.BUILD_SYSTEM,
            trust_level=ProvenanceTrustLevel.EXTERNAL_ATTESTATION_READY,
        )


def test_provenance_signature_enforces_unsigned_boundary() -> None:
    unsigned = ProvenanceSignature(
        signature_id="sig-unsigned-001",
        digest_id="digest-evidence-001",
        signer_id="signer-system-owner-001",
        algorithm=ProvenanceSignatureAlgorithm.UNSIGNED,
        status=ProvenanceVerificationStatus.UNSIGNED,
        signed_at_utc="2026-05-12T12:01:00Z",
    )

    assert not unsigned.supports_signed_claim()

    with pytest.raises(ContractValueError, match="must use unsigned status"):
        ProvenanceSignature(
            signature_id="sig-unsigned-001",
            digest_id="digest-evidence-001",
            signer_id="signer-system-owner-001",
            algorithm=ProvenanceSignatureAlgorithm.UNSIGNED,
            status=ProvenanceVerificationStatus.UNVERIFIED,
            signed_at_utc="2026-05-12T12:01:00Z",
        )

    with pytest.raises(ContractValueError, match="must not include a signature"):
        ProvenanceSignature(
            signature_id="sig-unsigned-001",
            digest_id="digest-evidence-001",
            signer_id="signer-system-owner-001",
            algorithm=ProvenanceSignatureAlgorithm.UNSIGNED,
            status=ProvenanceVerificationStatus.UNSIGNED,
            signed_at_utc="2026-05-12T12:01:00Z",
            signature_value="not-allowed",
        )


def test_provenance_signature_requires_value_for_signed_algorithms() -> None:
    signature = _signature()

    assert signature.supports_signed_claim()
    assert signature.signed_at.year == 2026
    assert ProvenanceSignatureAlgorithm.ED25519.is_external_assurance_grade()

    with pytest.raises(ContractValueError, match="requires a nonblank signature value"):
        ProvenanceSignature(
            signature_id="sig-evidence-001",
            digest_id="digest-evidence-001",
            signer_id="signer-system-owner-001",
            algorithm=ProvenanceSignatureAlgorithm.ED25519,
            status=ProvenanceVerificationStatus.VERIFIED,
            signed_at_utc="2026-05-12T12:01:00Z",
        )

    with pytest.raises(ContractValueError, match="cannot use unsigned status"):
        ProvenanceSignature(
            signature_id="sig-evidence-001",
            digest_id="digest-evidence-001",
            signer_id="signer-system-owner-001",
            algorithm=ProvenanceSignatureAlgorithm.ED25519,
            status=ProvenanceVerificationStatus.UNSIGNED,
            signed_at_utc="2026-05-12T12:01:00Z",
            signature_value="signed-artifact-digest-placeholder",
        )


def test_provenance_attestation_ties_subject_artifacts_digests_and_signatures() -> None:
    attestation = _attestation()

    assert attestation.is_signed()
    assert attestation.issued_at.year == 2026

    unsigned_attestation = ProvenanceAttestation(
        attestation_id="attestation-local-hash-only-001",
        predicate_type="ix.assurance.provenance.v1",
        issuer="Assurance Lab",
        issued_at_utc="2026-05-12T12:02:00Z",
        subject_artifact_ids=("ev-framework-crosswalk-001",),
        digest_ids=("digest-evidence-001",),
    )

    assert not unsigned_attestation.is_signed()


def test_provenance_manifest_accepts_valid_cross_references() -> None:
    manifest = ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(_digest(),),
        signer_identities=(_signer(),),
        signatures=(_signature(),),
        attestations=(_attestation(),),
    )

    assert manifest.created_at.year == 2026
    assert manifest.digest_by_id("digest-evidence-001") == _digest()
    assert manifest.digest_by_artifact_id("ev-framework-crosswalk-001") == _digest()
    assert manifest.signatures_for_digest("digest-evidence-001") == (_signature(),)
    assert manifest.has_signed_claim_for_artifact("ev-framework-crosswalk-001")
    assert manifest.unsigned_artifact_ids() == ()


def test_provenance_manifest_reports_unsigned_artifacts() -> None:
    manifest = ProvenanceManifest(
        manifest_id="manifest-provenance-001",
        created_at_utc="2026-05-12T12:03:00Z",
        artifact_digests=(_digest(),),
        signer_identities=(_signer(),),
        signatures=(
            ProvenanceSignature(
                signature_id="sig-local-test-001",
                digest_id="digest-evidence-001",
                signer_id="signer-system-owner-001",
                algorithm=ProvenanceSignatureAlgorithm.LOCAL_DEVELOPMENT_TEST_ONLY,
                status=ProvenanceVerificationStatus.VERIFIED,
                signed_at_utc="2026-05-12T12:01:00Z",
                signature_value="local-test-signature",
            ),
        ),
    )

    assert not manifest.has_signed_claim_for_artifact("ev-framework-crosswalk-001")
    assert manifest.unsigned_artifact_ids() == ("ev-framework-crosswalk-001",)


def test_provenance_manifest_rejects_duplicate_record_ids() -> None:
    with pytest.raises(ContractValueError, match="unique digest IDs"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(), _digest()),
        )

    with pytest.raises(ContractValueError, match="unique artifact IDs"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(
                _digest(digest_id="digest-evidence-001"),
                _digest(digest_id="digest-evidence-002"),
            ),
        )

    with pytest.raises(ContractValueError, match="unique signer IDs"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(), _signer()),
        )

    with pytest.raises(ContractValueError, match="unique signature IDs"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(),),
            signatures=(_signature(), _signature()),
        )


def test_provenance_manifest_rejects_unknown_signature_references() -> None:
    with pytest.raises(ContractValueError, match="references unknown digest"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(),),
            signatures=(_signature(digest_id="missing-digest"),),
        )

    with pytest.raises(ContractValueError, match="references unknown signer"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(),),
            signatures=(_signature(signer_id="missing-signer"),),
        )


def test_provenance_manifest_rejects_unknown_attestation_references() -> None:
    with pytest.raises(ContractValueError, match="unknown artifact IDs"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(),),
            signatures=(_signature(),),
            attestations=(
                ProvenanceAttestation(
                    attestation_id="attestation-evidence-001",
                    predicate_type="ix.assurance.provenance.v1",
                    issuer="Assurance Lab",
                    issued_at_utc="2026-05-12T12:02:00Z",
                    subject_artifact_ids=("missing-artifact",),
                    digest_ids=("digest-evidence-001",),
                    signature_ids=("sig-evidence-001",),
                ),
            ),
        )

    with pytest.raises(ContractValueError, match="unknown signatures"):
        ProvenanceManifest(
            manifest_id="manifest-provenance-001",
            created_at_utc="2026-05-12T12:03:00Z",
            artifact_digests=(_digest(),),
            signer_identities=(_signer(),),
            signatures=(_signature(),),
            attestations=(
                ProvenanceAttestation(
                    attestation_id="attestation-evidence-001",
                    predicate_type="ix.assurance.provenance.v1",
                    issuer="Assurance Lab",
                    issued_at_utc="2026-05-12T12:02:00Z",
                    subject_artifact_ids=("ev-framework-crosswalk-001",),
                    digest_ids=("digest-evidence-001",),
                    signature_ids=("missing-signature",),
                ),
            ),
        )
