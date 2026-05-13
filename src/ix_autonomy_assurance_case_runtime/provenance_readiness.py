"""Signed-provenance readiness decision surface.

The provenance subsystem now has strict manifest records and a manifest verifier.
This module combines those pieces into one capability-completion gate so the
project can only count signed provenance as complete when audit-facing artifacts
have verified external-review-grade signatures, authority-aware signer posture,
and signed attestation coverage.

This module does not perform real cryptographic verification and does not claim
certification, external attestation service integration, authority to operate, or
agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.provenance import ProvenanceManifest
from ix_autonomy_assurance_case_runtime.provenance_verifier import (
    ProvenanceManifestDecision,
    ProvenanceManifestVerificationReport,
    ProvenanceManifestVerifier,
    ProvenanceVerificationFinding,
    ProvenanceVerificationFindingSeverity,
    ProvenanceVerificationPolicy,
)

PROVENANCE_CAPABILITY_ID = "signed-provenance"


class ProvenanceReadinessDecision(RuntimeStrEnum):
    """Decision for whether signed provenance can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the signed-provenance capability."""

        return self is ProvenanceReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks provenance-based maturity progress."""

        return self is ProvenanceReadinessDecision.BLOCKED


class ProvenanceReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized provenance-readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks signed-provenance completion."""

        return self is ProvenanceReadinessFindingSeverity.BLOCKER


class ProvenanceReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a normalized provenance-readiness finding."""

    VERIFICATION = "verification"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class ProvenanceReadinessFinding:
    """One normalized signed-provenance readiness finding."""

    finding_id: str
    severity: ProvenanceReadinessFindingSeverity
    source: ProvenanceReadinessFindingSource
    message: str
    artifact_id: str | None = None
    digest_id: str | None = None
    signature_id: str | None = None
    signer_id: str | None = None
    attestation_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate normalized provenance-readiness findings."""

        if not self.finding_id.strip():
            raise ContractValueError("Provenance readiness finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Provenance readiness finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} needs a message."
            )
        if self.artifact_id is not None and not self.artifact_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} has a blank artifact ID."
            )
        if self.digest_id is not None and not self.digest_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} has a blank digest ID."
            )
        if self.signature_id is not None and not self.signature_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} has a blank signature ID."
            )
        if self.signer_id is not None and not self.signer_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} has a blank signer ID."
            )
        if self.attestation_id is not None and not self.attestation_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} "
                "has a blank attestation ID."
            )
        if self.source_finding_id is not None and not self.source_finding_id.strip():
            raise ContractValueError(
                f"Provenance readiness finding {self.finding_id!r} "
                "has a blank source finding ID."
            )


@dataclass(frozen=True, slots=True)
class ProvenanceLayerReadinessReport:
    """Combined readiness report for the signed-provenance capability layer."""

    decision: ProvenanceReadinessDecision
    verification_report: ProvenanceManifestVerificationReport
    findings: tuple[ProvenanceReadinessFinding, ...]
    capability_id: str = PROVENANCE_CAPABILITY_ID

    @property
    def blocker_count(self) -> int:
        """Return normalized blocker count."""

        return sum(finding.severity.blocks_completion() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return normalized warning count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ProvenanceReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether signed provenance can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this readiness report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with signed-provenance completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_artifact(self, artifact_id: str) -> tuple[ProvenanceReadinessFinding, ...]:
        """Return normalized findings for an artifact."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_signature(
        self,
        signature_id: str,
    ) -> tuple[ProvenanceReadinessFinding, ...]:
        """Return normalized findings for a signature."""

        return tuple(
            finding for finding in self.findings if finding.signature_id == signature_id
        )

    def findings_for_attestation(
        self,
        attestation_id: str,
    ) -> tuple[ProvenanceReadinessFinding, ...]:
        """Return normalized findings for an attestation."""

        return tuple(
            finding for finding in self.findings if finding.attestation_id == attestation_id
        )

    def summary(self) -> str:
        """Return a deterministic signed-provenance readiness summary."""

        return (
            f"provenance-readiness: {self.decision.value} "
            f"({self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class ProvenanceLayerReadinessEvaluator:
    """Evaluate whether signed provenance can count toward prototype maturity."""

    def __init__(self, policy: ProvenanceVerificationPolicy | None = None) -> None:
        """Create a signed-provenance readiness evaluator."""

        self._verifier = ProvenanceManifestVerifier(policy)

    def evaluate(self, manifest: ProvenanceManifest) -> ProvenanceLayerReadinessReport:
        """Evaluate provenance verification and readiness as one decision surface."""

        verification_report = self._verifier.verify(manifest)
        findings = (
            self._build_readiness_findings(manifest)
            + self._normalize_verification_findings(verification_report.findings)
        )
        decision = self._decide(
            verification_report=verification_report,
            findings=findings,
        )
        return ProvenanceLayerReadinessReport(
            decision=decision,
            verification_report=verification_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        manifest: ProvenanceManifest,
    ) -> tuple[ProvenanceReadinessFinding, ...]:
        """Build readiness findings not emitted by the manifest verifier."""

        audit_artifact_digests = tuple(
            digest
            for digest in manifest.artifact_digests
            if digest.artifact_type.is_audit_artifact()
        )
        if audit_artifact_digests:
            return ()
        return (
            ProvenanceReadinessFinding(
                finding_id="provenance-readiness-no-audit-artifacts",
                severity=ProvenanceReadinessFindingSeverity.BLOCKER,
                source=ProvenanceReadinessFindingSource.READINESS,
                message=(
                    "Signed-provenance readiness requires at least one audit-facing artifact "
                    "digest such as an evidence bundle, run ledger, report, export package, "
                    "policy pack, registry catalog, framework crosswalk, or telemetry replay."
                ),
            ),
        )

    @staticmethod
    def _normalize_verification_findings(
        findings: tuple[ProvenanceVerificationFinding, ...],
    ) -> tuple[ProvenanceReadinessFinding, ...]:
        """Normalize provenance verification findings."""

        return tuple(
            ProvenanceReadinessFinding(
                finding_id=f"verification-{finding.finding_id}",
                severity=_map_verification_severity(finding.severity),
                source=ProvenanceReadinessFindingSource.VERIFICATION,
                message=finding.message,
                artifact_id=finding.artifact_id,
                digest_id=finding.digest_id,
                signature_id=finding.signature_id,
                signer_id=finding.signer_id,
                attestation_id=finding.attestation_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        verification_report: ProvenanceManifestVerificationReport,
        findings: tuple[ProvenanceReadinessFinding, ...],
    ) -> ProvenanceReadinessDecision:
        """Return the combined signed-provenance readiness decision."""

        if verification_report.decision is ProvenanceManifestDecision.FAILED:
            return ProvenanceReadinessDecision.BLOCKED
        if any(finding.severity.blocks_completion() for finding in findings):
            return ProvenanceReadinessDecision.BLOCKED
        if verification_report.decision is ProvenanceManifestDecision.LIMITED:
            return ProvenanceReadinessDecision.LIMITED
        if any(
            finding.severity is ProvenanceReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return ProvenanceReadinessDecision.LIMITED
        return ProvenanceReadinessDecision.COMPLETE


def _map_verification_severity(
    severity: ProvenanceVerificationFindingSeverity,
) -> ProvenanceReadinessFindingSeverity:
    """Map provenance verification severity to normalized readiness severity."""

    if severity is ProvenanceVerificationFindingSeverity.BLOCKER:
        return ProvenanceReadinessFindingSeverity.BLOCKER
    if severity is ProvenanceVerificationFindingSeverity.WARNING:
        return ProvenanceReadinessFindingSeverity.WARNING
    return ProvenanceReadinessFindingSeverity.INFO
