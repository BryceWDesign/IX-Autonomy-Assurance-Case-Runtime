"""Provenance and attestation domain records.

The serious prototype needs signed evidence and artifact provenance before it can
make credible claims about audit-ready artifact integrity. This module adds the
strict local domain records for artifact digests, signer identity, signatures,
attestations, and manifests. It intentionally does not perform cryptographic
signature verification yet; later commits can add verification engines on top of
these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from string import hexdigits

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable provenance identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank provenance text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _require_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a nonempty tuple of nonblank unique strings."""

    if not values:
        raise ContractValueError(f"{field_name} must not be empty.")
    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _require_optional_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate an optional tuple of nonblank unique strings."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    _require_text(value, field_name)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 UTC timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class ProvenanceArtifactType(RuntimeStrEnum):
    """Artifact type that can be covered by provenance records."""

    EVIDENCE_BUNDLE = "evidence_bundle"
    RUN_LEDGER = "run_ledger"
    ASSURANCE_REPORT = "assurance_report"
    EXPORT_PACKAGE = "export_package"
    MODEL_CARD = "model_card"
    POLICY_PACK = "policy_pack"
    REGISTRY_CATALOG = "registry_catalog"
    FRAMEWORK_CROSSWALK = "framework_crosswalk"
    TELEMETRY_REPLAY = "telemetry_replay"

    def is_audit_artifact(self) -> bool:
        """Return whether this artifact normally supports audit review."""

        return self in {
            ProvenanceArtifactType.EVIDENCE_BUNDLE,
            ProvenanceArtifactType.RUN_LEDGER,
            ProvenanceArtifactType.ASSURANCE_REPORT,
            ProvenanceArtifactType.EXPORT_PACKAGE,
            ProvenanceArtifactType.POLICY_PACK,
            ProvenanceArtifactType.REGISTRY_CATALOG,
            ProvenanceArtifactType.FRAMEWORK_CROSSWALK,
            ProvenanceArtifactType.TELEMETRY_REPLAY,
        }


class ProvenanceDigestAlgorithm(RuntimeStrEnum):
    """Digest algorithm used for provenance records."""

    SHA256 = "sha256"

    @property
    def hexdigest_length(self) -> int:
        """Return expected hexadecimal digest length."""

        if self is ProvenanceDigestAlgorithm.SHA256:
            return 64
        raise ContractValueError(f"Unsupported digest algorithm {self.value!r}.")


class ProvenanceSignatureAlgorithm(RuntimeStrEnum):
    """Signature algorithm declared by a provenance signature record."""

    UNSIGNED = "unsigned"
    LOCAL_DEVELOPMENT_TEST_ONLY = "local_development_test_only"
    ED25519 = "ed25519"
    ECDSA_P256_SHA256 = "ecdsa_p256_sha256"
    RSA_PSS_SHA256 = "rsa_pss_sha256"

    def is_external_assurance_grade(self) -> bool:
        """Return whether the algorithm can support external trust claims."""

        return self in {
            ProvenanceSignatureAlgorithm.ED25519,
            ProvenanceSignatureAlgorithm.ECDSA_P256_SHA256,
            ProvenanceSignatureAlgorithm.RSA_PSS_SHA256,
        }

    def is_unsigned(self) -> bool:
        """Return whether this algorithm represents an explicitly unsigned artifact."""

        return self is ProvenanceSignatureAlgorithm.UNSIGNED


class ProvenanceVerificationStatus(RuntimeStrEnum):
    """Verification status for a provenance signature."""

    UNSIGNED = "unsigned"
    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    FAILED = "failed"
    EXPIRED = "expired"
    KEY_UNTRUSTED = "key_untrusted"

    def supports_signed_claim(self) -> bool:
        """Return whether this status can support a signed provenance claim."""

        return self is ProvenanceVerificationStatus.VERIFIED

    def blocks_signed_claim(self) -> bool:
        """Return whether this status blocks a signed provenance claim."""

        return not self.supports_signed_claim()


class ProvenanceSignerRole(RuntimeStrEnum):
    """Role of an identity that signs or attests to provenance."""

    BUILD_SYSTEM = "build_system"
    EVIDENCE_CUSTODIAN = "evidence_custodian"
    SYSTEM_OWNER = "system_owner"
    HUMAN_REVIEWER = "human_reviewer"
    GOVERNANCE_AUTHORITY = "governance_authority"

    def can_support_authority_claim(self) -> bool:
        """Return whether this signer role can support authority-sensitive claims."""

        return self in {
            ProvenanceSignerRole.SYSTEM_OWNER,
            ProvenanceSignerRole.HUMAN_REVIEWER,
            ProvenanceSignerRole.GOVERNANCE_AUTHORITY,
        }


class ProvenanceTrustLevel(RuntimeStrEnum):
    """Trust posture for provenance material."""

    LOCAL_HASH_ONLY = "local_hash_only"
    LOCAL_TEST_SIGNATURE = "local_test_signature"
    SIGNED_BY_IDENTIFIED_KEY = "signed_by_identified_key"
    EXTERNAL_ATTESTATION_READY = "external_attestation_ready"

    def supports_external_review(self) -> bool:
        """Return whether this trust level can support stronger external review."""

        return self in {
            ProvenanceTrustLevel.SIGNED_BY_IDENTIFIED_KEY,
            ProvenanceTrustLevel.EXTERNAL_ATTESTATION_READY,
        }


@dataclass(frozen=True, slots=True)
class ArtifactDigest:
    """Digest record for one provenance-covered artifact."""

    digest_id: str
    artifact_id: str
    artifact_type: ProvenanceArtifactType
    algorithm: ProvenanceDigestAlgorithm
    digest_hex: str
    generated_at_utc: str
    size_bytes: int | None = None
    source_uri: str = ""

    def __post_init__(self) -> None:
        """Validate artifact digest records."""

        _require_identifier(self.digest_id, "digest_id")
        _require_identifier(self.artifact_id, "artifact_id")
        _parse_utc_timestamp(self.generated_at_utc, "digest generated_at_utc")
        if len(self.digest_hex) != self.algorithm.hexdigest_length:
            raise ContractValueError(
                f"Digest {self.digest_id!r} has invalid hexadecimal digest length."
            )
        if any(character not in hexdigits for character in self.digest_hex):
            raise ContractValueError(f"Digest {self.digest_id!r} must be hexadecimal.")
        if self.size_bytes is not None and self.size_bytes <= 0:
            raise ContractValueError(f"Digest {self.digest_id!r} size_bytes must be positive.")
        if self.source_uri and not self.source_uri.strip():
            raise ContractValueError(f"Digest {self.digest_id!r} source_uri is blank.")

    @property
    def generated_at(self) -> datetime:
        """Return the parsed UTC generation time."""

        return _parse_utc_timestamp(self.generated_at_utc, "digest generated_at_utc")


@dataclass(frozen=True, slots=True)
class ProvenanceSignerIdentity:
    """Identity metadata for a signer referenced by provenance signatures."""

    signer_id: str
    display_name: str
    role: ProvenanceSignerRole
    key_id: str
    organization: str
    trust_level: ProvenanceTrustLevel
    contact: str = ""

    def __post_init__(self) -> None:
        """Validate signer identity records."""

        _require_identifier(self.signer_id, "signer_id")
        _require_text(self.display_name, "signer display_name")
        _require_identifier(self.key_id, "signer key_id")
        _require_text(self.organization, "signer organization")
        if self.contact and not self.contact.strip():
            raise ContractValueError(f"Signer {self.signer_id!r} contact is blank.")
        if (
            self.trust_level is ProvenanceTrustLevel.EXTERNAL_ATTESTATION_READY
            and self.role is ProvenanceSignerRole.BUILD_SYSTEM
        ):
            raise ContractValueError(
                "external attestation readiness requires accountable non-build-system authority."
            )

    def can_support_external_review(self) -> bool:
        """Return whether this signer can support stronger external review."""

        return self.trust_level.supports_external_review()


@dataclass(frozen=True, slots=True)
class ProvenanceSignature:
    """Signature or explicit unsigned marker for one artifact digest."""

    signature_id: str
    digest_id: str
    signer_id: str
    algorithm: ProvenanceSignatureAlgorithm
    status: ProvenanceVerificationStatus
    signed_at_utc: str
    signature_value: str | None = None
    verification_notes: str = ""

    def __post_init__(self) -> None:
        """Validate provenance signature records."""

        _require_identifier(self.signature_id, "signature_id")
        _require_identifier(self.digest_id, "signature digest_id")
        _require_identifier(self.signer_id, "signature signer_id")
        _parse_utc_timestamp(self.signed_at_utc, "signature signed_at_utc")
        if self.verification_notes and not self.verification_notes.strip():
            raise ContractValueError(
                f"Signature {self.signature_id!r} verification_notes are blank."
            )
        self._validate_unsigned_boundary()
        self._validate_signed_boundary()

    @property
    def signed_at(self) -> datetime:
        """Return the parsed UTC signature timestamp."""

        return _parse_utc_timestamp(self.signed_at_utc, "signature signed_at_utc")

    def supports_signed_claim(self) -> bool:
        """Return whether this signature can support a signed provenance claim."""

        return (
            self.status.supports_signed_claim()
            and self.algorithm.is_external_assurance_grade()
            and self.signature_value is not None
        )

    def _validate_unsigned_boundary(self) -> None:
        """Validate explicit unsigned signature records."""

        if self.algorithm.is_unsigned():
            if self.status is not ProvenanceVerificationStatus.UNSIGNED:
                raise ContractValueError(
                    f"Unsigned signature {self.signature_id!r} must use unsigned status."
                )
            if self.signature_value is not None:
                raise ContractValueError(
                    f"Unsigned signature {self.signature_id!r} must not include a signature."
                )

    def _validate_signed_boundary(self) -> None:
        """Validate signed signature records."""

        if self.algorithm.is_unsigned():
            return
        if self.status is ProvenanceVerificationStatus.UNSIGNED:
            raise ContractValueError(
                f"Signed algorithm {self.algorithm.value!r} cannot use unsigned status."
            )
        if self.signature_value is None or not self.signature_value.strip():
            raise ContractValueError(
                f"Signature {self.signature_id!r} requires a nonblank signature value."
            )


@dataclass(frozen=True, slots=True)
class ProvenanceAttestation:
    """Attestation statement tying artifacts, digests, signatures, and predicate data."""

    attestation_id: str
    predicate_type: str
    issuer: str
    issued_at_utc: str
    subject_artifact_ids: tuple[str, ...]
    digest_ids: tuple[str, ...]
    signature_ids: tuple[str, ...] = ()
    statement_refs: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate provenance attestation records."""

        _require_identifier(self.attestation_id, "attestation_id")
        _require_text(self.predicate_type, "attestation predicate_type")
        _require_text(self.issuer, "attestation issuer")
        _parse_utc_timestamp(self.issued_at_utc, "attestation issued_at_utc")
        _require_nonblank_unique_tuple(
            self.subject_artifact_ids,
            f"attestation {self.attestation_id!r} subject_artifact_ids",
        )
        _require_nonblank_unique_tuple(
            self.digest_ids,
            f"attestation {self.attestation_id!r} digest_ids",
        )
        _require_optional_nonblank_unique_tuple(
            self.signature_ids,
            f"attestation {self.attestation_id!r} signature_ids",
        )
        _require_optional_nonblank_unique_tuple(
            self.statement_refs,
            f"attestation {self.attestation_id!r} statement_refs",
        )
        if self.notes and not self.notes.strip():
            raise ContractValueError(f"Attestation {self.attestation_id!r} notes are blank.")

    @property
    def issued_at(self) -> datetime:
        """Return the parsed UTC attestation issue time."""

        return _parse_utc_timestamp(self.issued_at_utc, "attestation issued_at_utc")

    def is_signed(self) -> bool:
        """Return whether this attestation references at least one signature."""

        return bool(self.signature_ids)


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    """Local manifest collecting artifact digests, signers, signatures, and attestations."""

    manifest_id: str
    created_at_utc: str
    artifact_digests: tuple[ArtifactDigest, ...]
    signer_identities: tuple[ProvenanceSignerIdentity, ...] = ()
    signatures: tuple[ProvenanceSignature, ...] = ()
    attestations: tuple[ProvenanceAttestation, ...] = ()

    def __post_init__(self) -> None:
        """Validate manifest cross-references."""

        _require_identifier(self.manifest_id, "manifest_id")
        _parse_utc_timestamp(self.created_at_utc, "manifest created_at_utc")
        if not self.artifact_digests:
            raise ContractValueError("Provenance manifests require at least one artifact digest.")
        self._validate_unique_ids()
        self._validate_signature_references()
        self._validate_attestation_references()

    @property
    def created_at(self) -> datetime:
        """Return the parsed UTC manifest creation time."""

        return _parse_utc_timestamp(self.created_at_utc, "manifest created_at_utc")

    def digest_by_id(self, digest_id: str) -> ArtifactDigest | None:
        """Return a digest record by digest ID."""

        return {digest.digest_id: digest for digest in self.artifact_digests}.get(digest_id)

    def digest_by_artifact_id(self, artifact_id: str) -> ArtifactDigest | None:
        """Return a digest record by artifact ID."""

        return {
            digest.artifact_id: digest for digest in self.artifact_digests
        }.get(artifact_id)

    def signatures_for_digest(self, digest_id: str) -> tuple[ProvenanceSignature, ...]:
        """Return signatures attached to a digest ID."""

        return tuple(signature for signature in self.signatures if signature.digest_id == digest_id)

    def has_signed_claim_for_artifact(self, artifact_id: str) -> bool:
        """Return whether an artifact has at least one verified external-grade signature."""

        digest = self.digest_by_artifact_id(artifact_id)
        if digest is None:
            return False
        return any(
            signature.supports_signed_claim()
            for signature in self.signatures_for_digest(digest.digest_id)
        )

    def unsigned_artifact_ids(self) -> tuple[str, ...]:
        """Return artifact IDs lacking a verified external-grade signature."""

        return tuple(
            digest.artifact_id
            for digest in self.artifact_digests
            if not self.has_signed_claim_for_artifact(digest.artifact_id)
        )

    def _validate_unique_ids(self) -> None:
        """Reject duplicate manifest record IDs."""

        digest_ids = tuple(digest.digest_id for digest in self.artifact_digests)
        if len(digest_ids) != len(set(digest_ids)):
            raise ContractValueError("Provenance manifests require unique digest IDs.")

        artifact_ids = tuple(digest.artifact_id for digest in self.artifact_digests)
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ContractValueError("Provenance manifests require unique artifact IDs.")

        signer_ids = tuple(signer.signer_id for signer in self.signer_identities)
        if len(signer_ids) != len(set(signer_ids)):
            raise ContractValueError("Provenance manifests require unique signer IDs.")

        signature_ids = tuple(signature.signature_id for signature in self.signatures)
        if len(signature_ids) != len(set(signature_ids)):
            raise ContractValueError("Provenance manifests require unique signature IDs.")

        attestation_ids = tuple(attestation.attestation_id for attestation in self.attestations)
        if len(attestation_ids) != len(set(attestation_ids)):
            raise ContractValueError("Provenance manifests require unique attestation IDs.")

    def _validate_signature_references(self) -> None:
        """Validate signature references to digests and signers."""

        digest_ids = {digest.digest_id for digest in self.artifact_digests}
        signer_ids = {signer.signer_id for signer in self.signer_identities}
        for signature in self.signatures:
            if signature.digest_id not in digest_ids:
                raise ContractValueError(
                    f"Signature {signature.signature_id!r} references unknown digest "
                    f"{signature.digest_id!r}."
                )
            if signature.signer_id not in signer_ids:
                raise ContractValueError(
                    f"Signature {signature.signature_id!r} references unknown signer "
                    f"{signature.signer_id!r}."
                )

    def _validate_attestation_references(self) -> None:
        """Validate attestation references to artifacts, digests, and signatures."""

        artifact_ids = {digest.artifact_id for digest in self.artifact_digests}
        digest_ids = {digest.digest_id for digest in self.artifact_digests}
        signature_ids = {signature.signature_id for signature in self.signatures}
        for attestation in self.attestations:
            missing_artifacts = tuple(
                artifact_id
                for artifact_id in attestation.subject_artifact_ids
                if artifact_id not in artifact_ids
            )
            if missing_artifacts:
                raise ContractValueError(
                    f"Attestation {attestation.attestation_id!r} references unknown artifact IDs."
                )
            missing_digests = tuple(
                digest_id for digest_id in attestation.digest_ids if digest_id not in digest_ids
            )
            if missing_digests:
                raise ContractValueError(
                    f"Attestation {attestation.attestation_id!r} references unknown digest IDs."
                )
            missing_signatures = tuple(
                signature_id
                for signature_id in attestation.signature_ids
                if signature_id not in signature_ids
            )
            if missing_signatures:
                raise ContractValueError(
                    f"Attestation {attestation.attestation_id!r} references unknown signatures."
                )
