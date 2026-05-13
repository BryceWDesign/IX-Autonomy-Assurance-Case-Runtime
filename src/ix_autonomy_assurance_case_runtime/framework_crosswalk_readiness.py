"""Framework-crosswalk readiness decision surface.

The framework-crosswalk subsystem can now model public framework objectives,
map them to local runtime artifacts, and validate evidence coverage behind those
mappings. This module combines those pieces into one readiness decision so the
project can only count the framework-crosswalk capability as complete when the
crosswalk is mapped, evidence-backed, federal/IC/DoD-facing, and free of
blockers.

This module does not claim official compliance, certification, endorsement,
authority to operate, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.framework_crosswalk import (
    FrameworkCoverageReport,
    FrameworkCrosswalk,
    FrameworkCrosswalkFinding,
    FrameworkCrosswalkFindingSeverity,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk_evidence import (
    FrameworkEvidenceCoverageReport,
    FrameworkEvidenceFinding,
    FrameworkEvidenceFindingSeverity,
    FrameworkEvidenceValidator,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

FRAMEWORK_CROSSWALK_CAPABILITY_ID = "framework-crosswalks"


class FrameworkCrosswalkReadinessDecision(RuntimeStrEnum):
    """Decision for whether framework crosswalks can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the framework-crosswalk capability."""

        return self is FrameworkCrosswalkReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks crosswalk-based maturity progress."""

        return self is FrameworkCrosswalkReadinessDecision.BLOCKED


class FrameworkCrosswalkReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized framework-crosswalk readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks framework-crosswalk completion."""

        return self is FrameworkCrosswalkReadinessFindingSeverity.BLOCKER


class FrameworkCrosswalkReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a normalized crosswalk-readiness finding."""

    CROSSWALK = "crosswalk"
    EVIDENCE = "evidence"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class FrameworkCrosswalkReadinessFinding:
    """One normalized framework-crosswalk readiness finding."""

    finding_id: str
    severity: FrameworkCrosswalkReadinessFindingSeverity
    source: FrameworkCrosswalkReadinessFindingSource
    message: str
    control_id: str | None = None
    mapping_id: str | None = None
    bundle_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate normalized crosswalk-readiness findings."""

        if not self.finding_id.strip():
            raise ContractValueError("Framework crosswalk readiness finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Framework crosswalk readiness finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Framework crosswalk readiness finding {self.finding_id!r} needs a message."
            )
        if self.control_id is not None and not self.control_id.strip():
            raise ContractValueError(
                f"Framework crosswalk readiness finding {self.finding_id!r} "
                "has a blank control ID."
            )
        if self.mapping_id is not None and not self.mapping_id.strip():
            raise ContractValueError(
                f"Framework crosswalk readiness finding {self.finding_id!r} "
                "has a blank mapping ID."
            )
        if self.bundle_id is not None and not self.bundle_id.strip():
            raise ContractValueError(
                f"Framework crosswalk readiness finding {self.finding_id!r} "
                "has a blank bundle ID."
            )
        if self.source_finding_id is not None and not self.source_finding_id.strip():
            raise ContractValueError(
                f"Framework crosswalk readiness finding {self.finding_id!r} "
                "has a blank source finding ID."
            )


@dataclass(frozen=True, slots=True)
class FrameworkCrosswalkLayerReadinessReport:
    """Combined readiness report for the framework-crosswalk capability layer."""

    decision: FrameworkCrosswalkReadinessDecision
    coverage_report: FrameworkCoverageReport
    evidence_report: FrameworkEvidenceCoverageReport
    findings: tuple[FrameworkCrosswalkReadinessFinding, ...]
    capability_id: str = FRAMEWORK_CROSSWALK_CAPABILITY_ID

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
            if finding.severity is FrameworkCrosswalkReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether the framework-crosswalk capability can count as complete."""

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
        """Evaluate prototype claim readiness with this crosswalk completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_control(
        self,
        control_id: str,
    ) -> tuple[FrameworkCrosswalkReadinessFinding, ...]:
        """Return normalized findings for a control objective."""

        return tuple(finding for finding in self.findings if finding.control_id == control_id)

    def findings_for_mapping(
        self,
        mapping_id: str,
    ) -> tuple[FrameworkCrosswalkReadinessFinding, ...]:
        """Return normalized findings for a control mapping."""

        return tuple(finding for finding in self.findings if finding.mapping_id == mapping_id)

    def summary(self) -> str:
        """Return a deterministic framework-crosswalk readiness summary."""

        return (
            f"framework-crosswalk-readiness: {self.decision.value} "
            f"({self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class FrameworkCrosswalkLayerReadinessEvaluator:
    """Evaluate whether framework crosswalks can count toward prototype maturity."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle]) -> None:
        """Create a framework-crosswalk readiness evaluator."""

        self._evidence_validator = FrameworkEvidenceValidator(evidence_bundles)

    def evaluate(self, crosswalk: FrameworkCrosswalk) -> FrameworkCrosswalkLayerReadinessReport:
        """Evaluate coverage and evidence as one framework-crosswalk readiness surface."""

        coverage_report = crosswalk.build_coverage_report()
        evidence_report = self._evidence_validator.validate(crosswalk)
        findings = (
            self._build_readiness_findings(crosswalk)
            + self._normalize_crosswalk_findings(coverage_report.findings)
            + self._normalize_evidence_findings(evidence_report.findings)
        )
        decision = self._decide(
            coverage_report=coverage_report,
            evidence_report=evidence_report,
            findings=findings,
        )

        return FrameworkCrosswalkLayerReadinessReport(
            decision=decision,
            coverage_report=coverage_report,
            evidence_report=evidence_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        crosswalk: FrameworkCrosswalk,
    ) -> tuple[FrameworkCrosswalkReadinessFinding, ...]:
        """Build readiness findings not emitted by crosswalk/evidence validators."""

        findings: list[FrameworkCrosswalkReadinessFinding] = []
        if not crosswalk.objectives:
            findings.append(
                FrameworkCrosswalkReadinessFinding(
                    finding_id="framework-crosswalk-no-objectives",
                    severity=FrameworkCrosswalkReadinessFindingSeverity.BLOCKER,
                    source=FrameworkCrosswalkReadinessFindingSource.READINESS,
                    message=(
                        "Framework-crosswalk readiness requires at least one control "
                        "objective."
                    ),
                )
            )
            return tuple(findings)

        has_federal_or_national_security_objective = any(
            objective.framework.is_federal_or_national_security_facing()
            for objective in crosswalk.objectives
        )
        if not has_federal_or_national_security_objective:
            findings.append(
                FrameworkCrosswalkReadinessFinding(
                    finding_id="framework-crosswalk-no-federal-national-security-objective",
                    severity=FrameworkCrosswalkReadinessFindingSeverity.BLOCKER,
                    source=FrameworkCrosswalkReadinessFindingSource.READINESS,
                    message=(
                        "Framework-crosswalk readiness for this prototype requires at least "
                        "one federal, IC, or DoD-facing framework objective."
                    ),
                )
            )

        if not crosswalk.mappings:
            findings.append(
                FrameworkCrosswalkReadinessFinding(
                    finding_id="framework-crosswalk-no-mappings",
                    severity=FrameworkCrosswalkReadinessFindingSeverity.BLOCKER,
                    source=FrameworkCrosswalkReadinessFindingSource.READINESS,
                    message=(
                        "Framework-crosswalk readiness requires at least one local artifact "
                        "mapping."
                    ),
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_crosswalk_findings(
        findings: tuple[FrameworkCrosswalkFinding, ...],
    ) -> tuple[FrameworkCrosswalkReadinessFinding, ...]:
        """Normalize framework crosswalk findings."""

        return tuple(
            FrameworkCrosswalkReadinessFinding(
                finding_id=f"crosswalk-{finding.finding_id}",
                severity=_map_crosswalk_severity(finding.severity),
                source=FrameworkCrosswalkReadinessFindingSource.CROSSWALK,
                message=finding.message,
                control_id=finding.control_id,
                mapping_id=finding.mapping_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _normalize_evidence_findings(
        findings: tuple[FrameworkEvidenceFinding, ...],
    ) -> tuple[FrameworkCrosswalkReadinessFinding, ...]:
        """Normalize framework evidence coverage findings."""

        return tuple(
            FrameworkCrosswalkReadinessFinding(
                finding_id=f"evidence-{finding.finding_id}",
                severity=_map_evidence_severity(finding.severity),
                source=FrameworkCrosswalkReadinessFindingSource.EVIDENCE,
                message=finding.message,
                control_id=finding.control_id,
                mapping_id=finding.mapping_id,
                bundle_id=finding.bundle_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        coverage_report: FrameworkCoverageReport,
        evidence_report: FrameworkEvidenceCoverageReport,
        findings: tuple[FrameworkCrosswalkReadinessFinding, ...],
    ) -> FrameworkCrosswalkReadinessDecision:
        """Return the combined framework-crosswalk readiness decision."""

        if coverage_report.blocker_count or evidence_report.blocker_count:
            return FrameworkCrosswalkReadinessDecision.BLOCKED
        if any(finding.severity.blocks_completion() for finding in findings):
            return FrameworkCrosswalkReadinessDecision.BLOCKED
        if coverage_report.warning_count or evidence_report.warning_count:
            return FrameworkCrosswalkReadinessDecision.LIMITED
        if any(
            finding.severity is FrameworkCrosswalkReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return FrameworkCrosswalkReadinessDecision.LIMITED
        return FrameworkCrosswalkReadinessDecision.COMPLETE


def _map_crosswalk_severity(
    severity: FrameworkCrosswalkFindingSeverity,
) -> FrameworkCrosswalkReadinessFindingSeverity:
    """Map framework crosswalk severity to normalized readiness severity."""

    if severity is FrameworkCrosswalkFindingSeverity.BLOCKER:
        return FrameworkCrosswalkReadinessFindingSeverity.BLOCKER
    if severity is FrameworkCrosswalkFindingSeverity.WARNING:
        return FrameworkCrosswalkReadinessFindingSeverity.WARNING
    return FrameworkCrosswalkReadinessFindingSeverity.INFO


def _map_evidence_severity(
    severity: FrameworkEvidenceFindingSeverity,
) -> FrameworkCrosswalkReadinessFindingSeverity:
    """Map framework evidence severity to normalized readiness severity."""

    if severity is FrameworkEvidenceFindingSeverity.BLOCKER:
        return FrameworkCrosswalkReadinessFindingSeverity.BLOCKER
    if severity is FrameworkEvidenceFindingSeverity.WARNING:
        return FrameworkCrosswalkReadinessFindingSeverity.WARNING
    return FrameworkCrosswalkReadinessFindingSeverity.INFO
