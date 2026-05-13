"""Verification layer for local provenance manifests.

The provenance domain records define artifact digests, signers, signatures, and
attestations. This module evaluates whether those records can support a signed
provenance claim. It intentionally does not perform real cryptographic signature
verification yet. Instead, it validates the declared verification state, signer
trust posture, audit-artifact signer role, signature-grade algorithm, and
attestation coverage.

Real cryptographic verification, key discovery, certificate-chain validation,
hardware-backed signing, transparency logs, and external attestation services
remain future deployment concerns.
"""

from __future__ import annotations

from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.provenance import (
    ArtifactDigest,
    ProvenanceArtifactType,
    ProvenanceAttestation,
    ProvenanceManifest,
    ProvenanceSignature,
    ProvenanceSignerIdentity,
    ProvenanceVerificationStatus,
)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable provenance-verification identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank provenance-verification text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


class ProvenanceManifestDecision(RuntimeStrEnum):
    """Decision for whether a manifest supports signed provenance claims."""

    VERIFIED = "verified"
    LIMITED = "limited"
    FAILED = "failed"

    def supports_signed_provenance_claim(self) -> bool:
        """Return whether this decision can support a signed provenance claim."""

        return self is ProvenanceManifestDecision.VERIFIED

    def blocks_signed_provenance_claim(self) -> bool:
        """Return whether this decision blocks a signed provenance claim."""

        return self is ProvenanceManifestDecision.FAILED


class ProvenanceVerificationFindingSeverity(RuntimeStrEnum):
    """Severity for provenance verification findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_signed_claim(self) -> bool:
        """Return whether this finding blocks signed provenance claims."""

        return self is ProvenanceVerificationFindingSeverity.BLOCKER


class ProvenanceVerificationFindingSource(RuntimeStrEnum):
    """Source area for a provenance verification finding."""

    ARTIFACT = "artifact"
    SIGNATURE = "signature"
    SIGNER = "signer"
    ATTESTATION = "attestation"
    MANIFEST = "manifest"


@dataclass(frozen=True, slots=True)
class ProvenanceVerificationPolicy:
    """Policy knobs for local manifest verification."""

    require_external_review_signatures: bool = True
    require_signed_attestations: bool = True
    require_attestation_per_artifact: bool = True
    require_authority_signer_for_audit_artifacts: bool = True

    def requires_strong_signed_claims(self) -> bool:
        """Return whether the policy expects external-review-grade signatures."""

        return self.require_external_review_signatures or self.require_signed_attestations


@dataclass(frozen=True, slots=True)
class ProvenanceVerificationFinding:
    """One issue found while verifying a provenance manifest."""

    finding_id: str
    severity: ProvenanceVerificationFindingSeverity
    source: ProvenanceVerificationFindingSource
    message: str
    artifact_id: str | None = None
    digest_id: str | None = None
    signature_id: str | None = None
    signer_id: str | None = None
    attestation_id: str | None = None

    def __post_init__(self) -> None:
        """Validate provenance verification finding fields."""

        if not self.finding_id.strip():
            raise ContractValueError("Provenance verification finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Provenance verification finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} needs a message."
            )
        if self.artifact_id is not None and not self.artifact_id.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} has a blank artifact ID."
            )
        if self.digest_id is not None and not self.digest_id.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} has a blank digest ID."
            )
        if self.signature_id is not None and not self.signature_id.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} has a blank signature ID."
            )
        if self.signer_id is not None and not self.signer_id.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} has a blank signer ID."
            )
        if self.attestation_id is not None and not self.attestation_id.strip():
            raise ContractValueError(
                f"Provenance verification finding {self.finding_id!r} has a blank attestation ID."
            )


@dataclass(frozen=True, slots=True)
class ProvenanceManifestVerificationReport:
    """Verification report for a provenance manifest."""

    manifest_id: str
    decision: ProvenanceManifestDecision
    artifact_count: int
    signed_artifact_count: int
    attestation_count: int
    findings: tuple[ProvenanceVerificationFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(1 for finding in self.findings if finding.severity.blocks_signed_claim())

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ProvenanceVerificationFindingSeverity.WARNING
        )

    def supports_signed_provenance_claim(self) -> bool:
        """Return whether this report supports a signed provenance claim."""

        return self.decision.supports_signed_provenance_claim()

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Return findings tied to a specific artifact."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_signature(
        self,
        signature_id: str,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Return findings tied to a specific signature."""

        return tuple(finding for finding in self.findings if finding.signature_id == signature_id)

    def findings_for_attestation(
        self,
        attestation_id: str,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Return findings tied to a specific attestation."""

        return tuple(
            finding for finding in self.findings if finding.attestation_id == attestation_id
        )

    def summary(self) -> str:
        """Return a deterministic provenance verification summary."""

        return (
            f"provenance-verification: {self.decision.value} "
            f"({self.signed_artifact_count}/{self.artifact_count} signed artifact(s), "
            f"{self.attestation_count} attestation(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class ProvenanceManifestVerifier:
    """Verify whether a local provenance manifest can support signed claims."""

    def __init__(
        self,
        policy: ProvenanceVerificationPolicy | None = None,
    ) -> None:
        """Create a provenance manifest verifier."""

        self._policy = policy or ProvenanceVerificationPolicy()

    def verify(self, manifest: ProvenanceManifest) -> ProvenanceManifestVerificationReport:
        """Verify a provenance manifest against the configured local policy."""

        digest_by_id = {digest.digest_id: digest for digest in manifest.artifact_digests}
        signer_by_id = {signer.signer_id: signer for signer in manifest.signer_identities}
        findings: list[ProvenanceVerificationFinding] = []

        findings.extend(self._verify_artifact_signature_coverage(manifest))
        findings.extend(
            self._verify_signature_posture(
                manifest=manifest,
                digest_by_id=digest_by_id,
                signer_by_id=signer_by_id,
            )
        )
        findings.extend(
            self._verify_attestation_posture(
                manifest=manifest,
                digest_by_id=digest_by_id,
            )
        )

        decision = self._decide(tuple(findings))
        return ProvenanceManifestVerificationReport(
            manifest_id=manifest.manifest_id,
            decision=decision,
            artifact_count=len(manifest.artifact_digests),
            signed_artifact_count=sum(
                1
                for digest in manifest.artifact_digests
                if manifest.has_signed_claim_for_artifact(digest.artifact_id)
            ),
            attestation_count=len(manifest.attestations),
            findings=tuple(findings),
        )

    def _verify_artifact_signature_coverage(
        self,
        manifest: ProvenanceManifest,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify that artifacts have signatures strong enough for the policy."""

        findings: list[ProvenanceVerificationFinding] = []
        for digest in manifest.artifact_digests:
            signatures = manifest.signatures_for_digest(digest.digest_id)
            if not signatures:
                findings.append(
                    ProvenanceVerificationFinding(
                        finding_id=f"artifact-{digest.artifact_id}-has-no-signature",
                        severity=self._unsigned_artifact_severity(),
                        source=ProvenanceVerificationFindingSource.ARTIFACT,
                        message="Artifact has no provenance signature record.",
                        artifact_id=digest.artifact_id,
                        digest_id=digest.digest_id,
                    )
                )
                continue
            if not any(signature.supports_signed_claim() for signature in signatures):
                findings.append(
                    ProvenanceVerificationFinding(
                        finding_id=f"artifact-{digest.artifact_id}-has-no-verified-signature",
                        severity=self._unsigned_artifact_severity(),
                        source=ProvenanceVerificationFindingSource.ARTIFACT,
                        message=(
                            "Artifact has signature records, but none support an "
                            "external-review-grade signed provenance claim."
                        ),
                        artifact_id=digest.artifact_id,
                        digest_id=digest.digest_id,
                    )
                )
        return tuple(findings)

    def _verify_signature_posture(
        self,
        manifest: ProvenanceManifest,
        digest_by_id: dict[str, ArtifactDigest],
        signer_by_id: dict[str, ProvenanceSignerIdentity],
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify declared signature status, algorithm, and signer trust posture."""

        findings: list[ProvenanceVerificationFinding] = []
        for signature in manifest.signatures:
            digest = digest_by_id[signature.digest_id]
            signer = signer_by_id[signature.signer_id]

            findings.extend(self._verify_signature_status(signature, digest))
            findings.extend(self._verify_signature_algorithm(signature, digest))
            findings.extend(self._verify_signer_trust(signature, digest, signer))
            findings.extend(self._verify_audit_artifact_signer_role(signature, digest, signer))

        return tuple(findings)

    def _verify_signature_status(
        self,
        signature: ProvenanceSignature,
        digest: ArtifactDigest,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify signature status."""

        if signature.status is ProvenanceVerificationStatus.VERIFIED:
            return ()
        severity = (
            ProvenanceVerificationFindingSeverity.BLOCKER
            if signature.status
            in {
                ProvenanceVerificationStatus.FAILED,
                ProvenanceVerificationStatus.EXPIRED,
                ProvenanceVerificationStatus.KEY_UNTRUSTED,
            }
            else self._unsigned_artifact_severity()
        )
        return (
            ProvenanceVerificationFinding(
                finding_id=f"signature-{signature.signature_id}-status-{signature.status.value}",
                severity=severity,
                source=ProvenanceVerificationFindingSource.SIGNATURE,
                message=(
                    f"Signature status {signature.status.value!r} cannot support a "
                    "verified signed provenance claim."
                ),
                artifact_id=digest.artifact_id,
                digest_id=digest.digest_id,
                signature_id=signature.signature_id,
                signer_id=signature.signer_id,
            ),
        )

    def _verify_signature_algorithm(
        self,
        signature: ProvenanceSignature,
        digest: ArtifactDigest,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify whether a signature algorithm can support external review."""

        if signature.algorithm.is_external_assurance_grade():
            return ()
        return (
            ProvenanceVerificationFinding(
                finding_id=(
                    f"signature-{signature.signature_id}-algorithm-"
                    f"{signature.algorithm.value}-not-external-grade"
                ),
                severity=self._unsigned_artifact_severity(),
                source=ProvenanceVerificationFindingSource.SIGNATURE,
                message=(
                    f"Signature algorithm {signature.algorithm.value!r} is not "
                    "external-review-grade."
                ),
                artifact_id=digest.artifact_id,
                digest_id=digest.digest_id,
                signature_id=signature.signature_id,
                signer_id=signature.signer_id,
            ),
        )

    def _verify_signer_trust(
        self,
        signature: ProvenanceSignature,
        digest: ArtifactDigest,
        signer: ProvenanceSignerIdentity,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify whether the signer trust level can support external review."""

        if signer.can_support_external_review():
            return ()
        return (
            ProvenanceVerificationFinding(
                finding_id=f"signer-{signer.signer_id}-trust-{signer.trust_level.value}",
                severity=self._unsigned_artifact_severity(),
                source=ProvenanceVerificationFindingSource.SIGNER,
                message=(
                    f"Signer trust level {signer.trust_level.value!r} cannot support "
                    "external-review-grade provenance."
                ),
                artifact_id=digest.artifact_id,
                digest_id=digest.digest_id,
                signature_id=signature.signature_id,
                signer_id=signer.signer_id,
            ),
        )

    def _verify_audit_artifact_signer_role(
        self,
        signature: ProvenanceSignature,
        digest: ArtifactDigest,
        signer: ProvenanceSignerIdentity,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Warn when audit artifacts are signed only by non-authority roles."""

        if not self._policy.require_authority_signer_for_audit_artifacts:
            return ()
        if not digest.artifact_type.is_audit_artifact():
            return ()
        if signer.role.can_support_authority_claim():
            return ()
        return (
            ProvenanceVerificationFinding(
                finding_id=f"artifact-{digest.artifact_id}-signed-by-non-authority-role",
                severity=ProvenanceVerificationFindingSeverity.WARNING,
                source=ProvenanceVerificationFindingSource.SIGNER,
                message=(
                    "Audit-facing artifact is signed by a role that cannot support "
                    "authority-sensitive claims by itself."
                ),
                artifact_id=digest.artifact_id,
                digest_id=digest.digest_id,
                signature_id=signature.signature_id,
                signer_id=signer.signer_id,
            ),
        )

    def _verify_attestation_posture(
        self,
        manifest: ProvenanceManifest,
        digest_by_id: dict[str, ArtifactDigest],
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify attestation coverage and signed attestation posture."""

        findings: list[ProvenanceVerificationFinding] = []
        if self._policy.require_signed_attestations and not manifest.attestations:
            findings.append(
                ProvenanceVerificationFinding(
                    finding_id="manifest-has-no-attestations",
                    severity=ProvenanceVerificationFindingSeverity.BLOCKER,
                    source=ProvenanceVerificationFindingSource.MANIFEST,
                    message="Signed provenance policy requires at least one attestation.",
                )
            )

        if self._policy.require_attestation_per_artifact:
            findings.extend(self._verify_artifact_attestation_coverage(manifest, digest_by_id))

        for attestation in manifest.attestations:
            findings.extend(self._verify_signed_attestation(manifest, attestation))

        return tuple(findings)

    def _verify_artifact_attestation_coverage(
        self,
        manifest: ProvenanceManifest,
        digest_by_id: dict[str, ArtifactDigest],
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify that each artifact digest is covered by an attestation."""

        attested_digest_ids = {
            digest_id
            for attestation in manifest.attestations
            for digest_id in attestation.digest_ids
        }
        findings: list[ProvenanceVerificationFinding] = []
        for digest_id, digest in digest_by_id.items():
            if digest_id not in attested_digest_ids:
                findings.append(
                    ProvenanceVerificationFinding(
                        finding_id=f"artifact-{digest.artifact_id}-has-no-attestation",
                        severity=(
                            ProvenanceVerificationFindingSeverity.BLOCKER
                            if self._policy.require_signed_attestations
                            else ProvenanceVerificationFindingSeverity.WARNING
                        ),
                        source=ProvenanceVerificationFindingSource.ATTESTATION,
                        message="Artifact digest is not covered by a provenance attestation.",
                        artifact_id=digest.artifact_id,
                        digest_id=digest.digest_id,
                    )
                )
        return tuple(findings)

    def _verify_signed_attestation(
        self,
        manifest: ProvenanceManifest,
        attestation: ProvenanceAttestation,
    ) -> tuple[ProvenanceVerificationFinding, ...]:
        """Verify that attestation signatures support signed claims."""

        if not self._policy.require_signed_attestations:
            return ()
        if not attestation.signature_ids:
            return (
                ProvenanceVerificationFinding(
                    finding_id=f"attestation-{attestation.attestation_id}-unsigned",
                    severity=ProvenanceVerificationFindingSeverity.BLOCKER,
                    source=ProvenanceVerificationFindingSource.ATTESTATION,
                    message="Attestation has no signature reference.",
                    attestation_id=attestation.attestation_id,
                ),
            )

        signature_by_id = {signature.signature_id: signature for signature in manifest.signatures}
        supporting_signatures = tuple(
            signature_by_id[signature_id]
            for signature_id in attestation.signature_ids
            if signature_by_id[signature_id].supports_signed_claim()
        )
        if supporting_signatures:
            return ()

        return (
            ProvenanceVerificationFinding(
                finding_id=f"attestation-{attestation.attestation_id}-has-no-verified-signature",
                severity=ProvenanceVerificationFindingSeverity.BLOCKER,
                source=ProvenanceVerificationFindingSource.ATTESTATION,
                message="Attestation signatures do not support a verified signed claim.",
                attestation_id=attestation.attestation_id,
            ),
        )

    def _unsigned_artifact_severity(self) -> ProvenanceVerificationFindingSeverity:
        """Return severity for unsigned or weakly signed artifacts under policy."""

        if self._policy.require_external_review_signatures:
            return ProvenanceVerificationFindingSeverity.BLOCKER
        return ProvenanceVerificationFindingSeverity.WARNING

    @staticmethod
    def _decide(
        findings: tuple[ProvenanceVerificationFinding, ...],
    ) -> ProvenanceManifestDecision:
        """Decide manifest verification posture from findings."""

        if any(finding.severity.blocks_signed_claim() for finding in findings):
            return ProvenanceManifestDecision.FAILED
        if any(
            finding.severity is ProvenanceVerificationFindingSeverity.WARNING
            for finding in findings
        ):
            return ProvenanceManifestDecision.LIMITED
        return ProvenanceManifestDecision.VERIFIED
