"""Readiness guardrails for serious-prototype maturity claims.

The project can improve toward an 80-percent serious open-source prototype, but
it must not claim that posture until the required capability families are
implemented and evidence-backed. This module turns the target model into a
small, deterministic claim gate so future work has an enforceable anti-overclaim
boundary.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    RuntimeStrEnum,
)
from ix_autonomy_assurance_case_runtime.prototype_target import (
    PrototypeCapabilityTarget,
    assess_serious_prototype_maturity,
    build_serious_prototype_targets,
)


class PrototypeClaimLevel(RuntimeStrEnum):
    """Claim levels the runtime may be asked to evaluate."""

    LOCAL_REFERENCE_RUNTIME = "local_reference_runtime"
    SERIOUS_OPEN_SOURCE_PROTOTYPE = "serious_open_source_prototype"
    FEDERAL_ALIGNED_PROTOTYPE = "federal_aligned_prototype"
    OPERATIONAL_DEPLOYMENT_READY = "operational_deployment_ready"
    CERTIFIED_OR_AUTHORIZED = "certified_or_authorized"

    @property
    def rank(self) -> int:
        """Return an ordinal rank where larger values need stronger proof."""

        ranks = {
            PrototypeClaimLevel.LOCAL_REFERENCE_RUNTIME: 1,
            PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE: 2,
            PrototypeClaimLevel.FEDERAL_ALIGNED_PROTOTYPE: 3,
            PrototypeClaimLevel.OPERATIONAL_DEPLOYMENT_READY: 4,
            PrototypeClaimLevel.CERTIFIED_OR_AUTHORIZED: 5,
        }
        return ranks[self]

    def requires_serious_target(self) -> bool:
        """Return whether this claim level requires the 80-percent target."""

        return self.rank >= PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE.rank

    def cannot_be_self_attested_by_repo(self) -> bool:
        """Return whether source code alone can never justify this claim."""

        return self in {
            PrototypeClaimLevel.OPERATIONAL_DEPLOYMENT_READY,
            PrototypeClaimLevel.CERTIFIED_OR_AUTHORIZED,
        }


class PrototypeReadinessDecision(RuntimeStrEnum):
    """Outcome of a serious-prototype readiness evaluation."""

    ALLOW = "allow"
    LIMIT = "limit"
    BLOCK = "block"

    def permits_claim(self) -> bool:
        """Return whether the requested claim may be made with any limits."""

        return self in {
            PrototypeReadinessDecision.ALLOW,
            PrototypeReadinessDecision.LIMIT,
        }


class PrototypeFindingSeverity(RuntimeStrEnum):
    """Severity for readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_claim(self) -> bool:
        """Return whether this finding blocks the requested claim."""

        return self is PrototypeFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class PrototypeReadinessFinding:
    """One finding emitted by the prototype readiness gate."""

    finding_id: str
    severity: PrototypeFindingSeverity
    message: str
    capability_id: str | None = None
    blocked_claim: str | None = None

    def __post_init__(self) -> None:
        """Validate finding records before they become audit evidence."""

        if not self.finding_id.strip():
            raise ContractValueError("Prototype readiness finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Prototype readiness finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Prototype readiness finding {self.finding_id!r} needs a message."
            )
        if self.capability_id is not None and not self.capability_id.strip():
            raise ContractValueError(
                f"Prototype readiness finding {self.finding_id!r} has a blank capability ID."
            )
        if self.blocked_claim is not None and not self.blocked_claim.strip():
            raise ContractValueError(
                f"Prototype readiness finding {self.finding_id!r} has a blank blocked claim."
            )


@dataclass(frozen=True, slots=True)
class PrototypeReadinessReport:
    """Result of a claim-readiness evaluation."""

    requested_claim_level: PrototypeClaimLevel
    decision: PrototypeReadinessDecision
    achieved_percent: int
    target_percent: int
    completed_capability_ids: tuple[str, ...]
    remaining_capability_ids: tuple[str, ...]
    findings: tuple[PrototypeReadinessFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return how many findings block the requested claim."""

        return sum(1 for finding in self.findings if finding.severity.blocks_claim())

    @property
    def warning_count(self) -> int:
        """Return how many findings warn about claim limits."""

        return sum(
            1 for finding in self.findings if finding.severity is PrototypeFindingSeverity.WARNING
        )

    @property
    def blocked_claims(self) -> tuple[str, ...]:
        """Return unique claim limits raised by readiness findings."""

        return tuple(
            dict.fromkeys(
                finding.blocked_claim
                for finding in self.findings
                if finding.blocked_claim is not None
            )
        )

    def permits_requested_claim(self) -> bool:
        """Return whether the requested claim level may be used."""

        return self.decision.permits_claim()

    def summary(self) -> str:
        """Return a concise deterministic summary for logs and CLI surfaces."""

        return (
            f"{self.requested_claim_level.value}: {self.decision.value} "
            f"({self.achieved_percent}/{self.target_percent} maturity, "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class PrototypeReadinessGate:
    """Evaluate whether the repo may make a requested maturity claim."""

    def __init__(self, targets: Iterable[PrototypeCapabilityTarget] | None = None) -> None:
        """Create a gate with canonical targets unless explicit targets are supplied."""

        self._targets = (
            tuple(targets) if targets is not None else build_serious_prototype_targets()
        )
        self._target_by_id = {target.capability_id: target for target in self._targets}
        if len(self._target_by_id) != len(self._targets):
            raise ContractValueError(
                "Prototype readiness targets must have unique capability IDs."
            )

    def evaluate(
        self,
        completed_capability_ids: Iterable[str],
        requested_claim_level: PrototypeClaimLevel,
    ) -> PrototypeReadinessReport:
        """Evaluate completed capabilities against the requested claim level."""

        assessment = assess_serious_prototype_maturity(completed_capability_ids)
        required_remaining_capability_ids = tuple(
            capability_id
            for capability_id in assessment.remaining_capability_ids
            if self._target_by_id[capability_id].required_for_serious_prototype
        )
        findings = list(
            self._build_missing_capability_findings(
                requested_claim_level=requested_claim_level,
                remaining_capability_ids=required_remaining_capability_ids,
            )
        )
        findings.extend(
            self._build_unexpected_capability_findings(
                assessment.unexpected_capability_ids,
            )
        )
        findings.extend(
            self._build_duplicate_capability_findings(
                assessment.duplicate_capability_ids,
            )
        )

        if requested_claim_level.cannot_be_self_attested_by_repo():
            findings.append(
                PrototypeReadinessFinding(
                    finding_id="external-authorization-required",
                    severity=PrototypeFindingSeverity.BLOCKER,
                    message=(
                        "Repository evidence alone cannot establish operational deployment, "
                        "certification, authorization, classified readiness, or agency acceptance."
                    ),
                    blocked_claim="Cannot self-attest operational or certified readiness.",
                )
            )

        if requested_claim_level is PrototypeClaimLevel.FEDERAL_ALIGNED_PROTOTYPE:
            findings.append(
                PrototypeReadinessFinding(
                    finding_id="alignment-not-endorsement",
                    severity=PrototypeFindingSeverity.WARNING,
                    message=(
                        "Federal/IC/DoD alignment means the prototype maps to public governance "
                        "and assurance concepts; it is not an official endorsement or authority "
                        "to operate."
                    ),
                    blocked_claim="Cannot claim official federal, IC, or DoD endorsement.",
                )
            )

        decision = self._decide(
            requested_claim_level=requested_claim_level,
            target_met=assessment.meets_serious_prototype_target(),
            findings=tuple(findings),
        )
        return PrototypeReadinessReport(
            requested_claim_level=requested_claim_level,
            decision=decision,
            achieved_percent=assessment.achieved_percent,
            target_percent=assessment.target_percent,
            completed_capability_ids=assessment.completed_capability_ids,
            remaining_capability_ids=assessment.remaining_capability_ids,
            findings=tuple(findings),
        )

    @staticmethod
    def _build_unexpected_capability_findings(
        unexpected_capability_ids: tuple[str, ...],
    ) -> tuple[PrototypeReadinessFinding, ...]:
        """Build warning findings for completed IDs outside the target model."""

        return tuple(
            PrototypeReadinessFinding(
                finding_id=f"unexpected-{capability_id}",
                severity=PrototypeFindingSeverity.WARNING,
                message=(
                    f"Completed capability {capability_id!r} is not part of the "
                    "prototype maturity target model and does not increase maturity."
                ),
                capability_id=capability_id,
            )
            for capability_id in unexpected_capability_ids
        )

    @staticmethod
    def _build_duplicate_capability_findings(
        duplicate_capability_ids: tuple[str, ...],
    ) -> tuple[PrototypeReadinessFinding, ...]:
        """Build warning findings for duplicate completed IDs."""

        return tuple(
            PrototypeReadinessFinding(
                finding_id=f"duplicate-{capability_id}",
                severity=PrototypeFindingSeverity.WARNING,
                message=(
                    f"Completed capability {capability_id!r} was supplied more than "
                    "once and is counted only once."
                ),
                capability_id=capability_id,
            )
            for capability_id in duplicate_capability_ids
        )

    def _build_missing_capability_findings(
        self,
        requested_claim_level: PrototypeClaimLevel,
        remaining_capability_ids: tuple[str, ...],
    ) -> tuple[PrototypeReadinessFinding, ...]:
        """Build blocker findings for remaining capabilities when a claim needs them."""

        if not requested_claim_level.requires_serious_target():
            if remaining_capability_ids:
                return (
                    PrototypeReadinessFinding(
                        finding_id="target-not-yet-complete",
                        severity=PrototypeFindingSeverity.WARNING,
                        message=(
                            "The repo may be described as a local reference runtime, but the "
                            "80-percent serious prototype capability set is not complete yet."
                        ),
                        blocked_claim="Cannot claim serious prototype completion yet.",
                    ),
                )
            return ()

        return tuple(
            PrototypeReadinessFinding(
                finding_id=f"missing-{capability_id}",
                severity=PrototypeFindingSeverity.BLOCKER,
                message=(
                    f"Required capability {capability_id!r} is not complete enough for "
                    f"{requested_claim_level.value!r}."
                ),
                capability_id=capability_id,
                blocked_claim=self._target_by_id[capability_id].blocked_claims_until_met[0],
            )
            for capability_id in remaining_capability_ids
        )

    @staticmethod
    def _decide(
        requested_claim_level: PrototypeClaimLevel,
        target_met: bool,
        findings: tuple[PrototypeReadinessFinding, ...],
    ) -> PrototypeReadinessDecision:
        """Return the readiness decision for a requested claim level."""

        if any(finding.severity.blocks_claim() for finding in findings):
            return PrototypeReadinessDecision.BLOCK
        if requested_claim_level.requires_serious_target() and not target_met:
            return PrototypeReadinessDecision.BLOCK
        if requested_claim_level is PrototypeClaimLevel.FEDERAL_ALIGNED_PROTOTYPE:
            return PrototypeReadinessDecision.LIMIT
        if any(finding.severity is PrototypeFindingSeverity.WARNING for finding in findings):
            return PrototypeReadinessDecision.LIMIT
        return PrototypeReadinessDecision.ALLOW
