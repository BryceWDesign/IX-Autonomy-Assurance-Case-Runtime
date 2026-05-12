"""Policy-layer readiness decision surface.

The policy subsystem now has strict policy-pack records, an evaluator, and waiver
evidence coverage checks. This module combines those pieces into one decision
surface so the project can only count the policy-pack capability as complete
when policy evaluation, waiver control, and waiver evidence coverage are clean
enough to support the serious-prototype target.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.policy import PolicyPack, PolicyWaiver
from ix_autonomy_assurance_case_runtime.policy_evaluator import (
    PolicyEvaluationFinding,
    PolicyEvaluationFindingSeverity,
    PolicyEvaluationReport,
    PolicyEvaluationRequest,
    PolicyEvaluator,
)
from ix_autonomy_assurance_case_runtime.policy_waiver_evidence import (
    PolicyWaiverEvidenceCoverageReport,
    PolicyWaiverEvidenceFinding,
    PolicyWaiverEvidenceFindingSeverity,
    PolicyWaiverEvidenceValidator,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

POLICY_CAPABILITY_ID = "policy-pack-engine"


class PolicyLayerReadinessDecision(RuntimeStrEnum):
    """Decision for whether the policy layer can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the policy target capability."""

        return self is PolicyLayerReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks policy-based maturity progress."""

        return self is PolicyLayerReadinessDecision.BLOCKED


class PolicyReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized policy-readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks policy completion."""

        return self is PolicyReadinessFindingSeverity.BLOCKER


class PolicyReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a normalized policy-readiness finding."""

    EVALUATION = "evaluation"
    WAIVER_EVIDENCE = "waiver_evidence"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class PolicyReadinessFinding:
    """One normalized finding from policy evaluation or waiver evidence validation."""

    finding_id: str
    severity: PolicyReadinessFindingSeverity
    source: PolicyReadinessFindingSource
    message: str
    request_id: str | None = None
    rule_id: str | None = None
    waiver_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate normalized policy-readiness findings."""

        if not self.finding_id.strip():
            raise ContractValueError("Policy readiness finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Policy readiness finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Policy readiness finding {self.finding_id!r} needs a message."
            )
        if self.request_id is not None and not self.request_id.strip():
            raise ContractValueError(
                f"Policy readiness finding {self.finding_id!r} has a blank request ID."
            )
        if self.rule_id is not None and not self.rule_id.strip():
            raise ContractValueError(
                f"Policy readiness finding {self.finding_id!r} has a blank rule ID."
            )
        if self.waiver_id is not None and not self.waiver_id.strip():
            raise ContractValueError(
                f"Policy readiness finding {self.finding_id!r} has a blank waiver ID."
            )
        if self.source_finding_id is not None and not self.source_finding_id.strip():
            raise ContractValueError(
                f"Policy readiness finding {self.finding_id!r} has a blank source finding ID."
            )


@dataclass(frozen=True, slots=True)
class PolicyLayerReadinessReport:
    """Combined readiness report for the policy-pack capability layer."""

    decision: PolicyLayerReadinessDecision
    evaluation_reports: tuple[PolicyEvaluationReport, ...]
    waiver_evidence_report: PolicyWaiverEvidenceCoverageReport
    findings: tuple[PolicyReadinessFinding, ...]
    capability_id: str = POLICY_CAPABILITY_ID

    @property
    def blocker_count(self) -> int:
        """Return the number of normalized blockers."""

        return sum(finding.severity.blocks_completion() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return the number of normalized warnings."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is PolicyReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether the policy capability can count as complete."""

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
        """Evaluate prototype claim readiness with this policy completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_request(self, request_id: str) -> tuple[PolicyReadinessFinding, ...]:
        """Return normalized findings for a policy request."""

        return tuple(finding for finding in self.findings if finding.request_id == request_id)

    def findings_for_waiver(self, waiver_id: str) -> tuple[PolicyReadinessFinding, ...]:
        """Return normalized findings for a policy waiver."""

        return tuple(finding for finding in self.findings if finding.waiver_id == waiver_id)

    def summary(self) -> str:
        """Return a deterministic policy-readiness summary."""

        return (
            f"policy-readiness: {self.decision.value} "
            f"({self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class PolicyLayerReadinessEvaluator:
    """Evaluate whether the policy layer can count toward prototype maturity."""

    def __init__(
        self,
        policy_pack: PolicyPack,
        waivers: Iterable[PolicyWaiver] = (),
        evidence_bundles: Iterable[EvidenceBundle] = (),
    ) -> None:
        """Create a policy-readiness evaluator."""

        self._policy_pack = policy_pack
        self._waivers = tuple(waivers)
        self._policy_evaluator = PolicyEvaluator(policy_pack, waivers=self._waivers)
        self._waiver_evidence_validator = PolicyWaiverEvidenceValidator(
            policy_pack,
            evidence_bundles,
        )

    def evaluate(
        self,
        requests: Iterable[PolicyEvaluationRequest],
        *,
        as_of_utc: str | None = None,
    ) -> PolicyLayerReadinessReport:
        """Evaluate policy decisions and waiver evidence as one readiness surface."""

        request_tuple = tuple(requests)
        evaluation_reports = tuple(
            self._policy_evaluator.evaluate(request) for request in request_tuple
        )
        waiver_evidence_report = self._waiver_evidence_validator.validate(
            self._waivers,
            as_of_utc=as_of_utc,
        )
        findings = (
            self._build_readiness_findings(request_tuple)
            + self._normalize_evaluation_findings(evaluation_reports)
            + self._normalize_waiver_evidence_findings(waiver_evidence_report.findings)
        )
        decision = self._decide(
            request_tuple=request_tuple,
            evaluation_reports=evaluation_reports,
            waiver_evidence_report=waiver_evidence_report,
            findings=findings,
        )
        return PolicyLayerReadinessReport(
            decision=decision,
            evaluation_reports=evaluation_reports,
            waiver_evidence_report=waiver_evidence_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        request_tuple: tuple[PolicyEvaluationRequest, ...],
    ) -> tuple[PolicyReadinessFinding, ...]:
        """Build policy-readiness findings not emitted by subsystem validators."""

        if request_tuple:
            return ()
        return (
            PolicyReadinessFinding(
                finding_id="policy-readiness-no-evaluation-requests",
                severity=PolicyReadinessFindingSeverity.BLOCKER,
                source=PolicyReadinessFindingSource.READINESS,
                message=(
                    "Policy readiness requires at least one evaluation request to demonstrate "
                    "policy-pack execution."
                ),
            ),
        )

    @staticmethod
    def _normalize_evaluation_findings(
        evaluation_reports: tuple[PolicyEvaluationReport, ...],
    ) -> tuple[PolicyReadinessFinding, ...]:
        """Normalize policy evaluation findings."""

        normalized: list[PolicyReadinessFinding] = []
        for report in evaluation_reports:
            for finding in report.findings:
                normalized.append(
                    _policy_evaluation_finding_to_readiness(
                        request_id=report.request_id,
                        finding=finding,
                    )
                )
        return tuple(normalized)

    @staticmethod
    def _normalize_waiver_evidence_findings(
        findings: tuple[PolicyWaiverEvidenceFinding, ...],
    ) -> tuple[PolicyReadinessFinding, ...]:
        """Normalize waiver evidence coverage findings."""

        return tuple(
            PolicyReadinessFinding(
                finding_id=f"waiver-evidence-{finding.finding_id}",
                severity=_map_waiver_evidence_severity(finding.severity),
                source=PolicyReadinessFindingSource.WAIVER_EVIDENCE,
                message=finding.message,
                waiver_id=finding.waiver_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        request_tuple: tuple[PolicyEvaluationRequest, ...],
        evaluation_reports: tuple[PolicyEvaluationReport, ...],
        waiver_evidence_report: PolicyWaiverEvidenceCoverageReport,
        findings: tuple[PolicyReadinessFinding, ...],
    ) -> PolicyLayerReadinessDecision:
        """Return the combined policy-readiness decision."""

        if not request_tuple:
            return PolicyLayerReadinessDecision.BLOCKED
        if waiver_evidence_report.blocker_count:
            return PolicyLayerReadinessDecision.BLOCKED
        if any(report.decision.blocks_action() for report in evaluation_reports):
            return PolicyLayerReadinessDecision.BLOCKED
        if any(finding.severity.blocks_completion() for finding in findings):
            return PolicyLayerReadinessDecision.BLOCKED
        if waiver_evidence_report.warning_count:
            return PolicyLayerReadinessDecision.LIMITED
        if any(
            finding.severity is PolicyReadinessFindingSeverity.WARNING for finding in findings
        ):
            return PolicyLayerReadinessDecision.LIMITED
        return PolicyLayerReadinessDecision.COMPLETE


def _policy_evaluation_finding_to_readiness(
    request_id: str,
    finding: PolicyEvaluationFinding,
) -> PolicyReadinessFinding:
    """Convert a policy evaluation finding into normalized readiness form."""

    return PolicyReadinessFinding(
        finding_id=f"evaluation-{request_id}-{finding.finding_id}",
        severity=_map_evaluation_severity(finding.severity),
        source=PolicyReadinessFindingSource.EVALUATION,
        message=finding.message,
        request_id=request_id,
        rule_id=finding.rule_id,
        waiver_id=finding.waiver_id,
        source_finding_id=finding.finding_id,
    )


def _map_evaluation_severity(
    severity: PolicyEvaluationFindingSeverity,
) -> PolicyReadinessFindingSeverity:
    """Map policy evaluation severity to normalized readiness severity."""

    if severity is PolicyEvaluationFindingSeverity.BLOCKER:
        return PolicyReadinessFindingSeverity.BLOCKER
    if severity is PolicyEvaluationFindingSeverity.WARNING:
        return PolicyReadinessFindingSeverity.WARNING
    return PolicyReadinessFindingSeverity.INFO


def _map_waiver_evidence_severity(
    severity: PolicyWaiverEvidenceFindingSeverity,
) -> PolicyReadinessFindingSeverity:
    """Map waiver evidence severity to normalized readiness severity."""

    if severity is PolicyWaiverEvidenceFindingSeverity.BLOCKER:
        return PolicyReadinessFindingSeverity.BLOCKER
    if severity is PolicyWaiverEvidenceFindingSeverity.WARNING:
        return PolicyReadinessFindingSeverity.WARNING
    return PolicyReadinessFindingSeverity.INFO
