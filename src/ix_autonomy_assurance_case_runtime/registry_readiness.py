"""Registry-layer readiness decision surface.

The registry subsystem now has strict records, catalog cross-reference
validation, and evidence coverage validation. This module combines those pieces
into one decision surface so the project can only count the registry capability
as complete when registry records, references, and evidence coverage are all
clean enough to support the serious-prototype target.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.registry_catalog import (
    RegistryCatalog,
    RegistryFindingSeverity,
    RegistryValidationFinding,
    RegistryValidationReport,
)
from ix_autonomy_assurance_case_runtime.registry_evidence import (
    RegistryEvidenceCoverageReport,
    RegistryEvidenceFinding,
    RegistryEvidenceFindingSeverity,
    RegistryEvidenceValidator,
)

REGISTRY_CAPABILITY_ID = "registry-layer"


class RegistryReadinessDecision(RuntimeStrEnum):
    """Decision for whether the registry layer can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the registry target capability."""

        return self is RegistryReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks registry-based maturity progress."""

        return self is RegistryReadinessDecision.BLOCKED


class RegistryReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized registry-readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks registry completion."""

        return self is RegistryReadinessFindingSeverity.BLOCKER


class RegistryReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a normalized readiness finding."""

    CATALOG = "catalog"
    EVIDENCE = "evidence"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class RegistryReadinessFinding:
    """One normalized finding from catalog, evidence, or readiness validation."""

    finding_id: str
    severity: RegistryReadinessFindingSeverity
    source: RegistryReadinessFindingSource
    message: str
    subject_id: str
    subject_type: str
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate normalized readiness findings."""

        if not self.finding_id.strip():
            raise ContractValueError("Registry readiness finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Registry readiness finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Registry readiness finding {self.finding_id!r} needs a message."
            )
        if not self.subject_id.strip():
            raise ContractValueError(
                f"Registry readiness finding {self.finding_id!r} needs a subject ID."
            )
        if not self.subject_type.strip():
            raise ContractValueError(
                f"Registry readiness finding {self.finding_id!r} needs a subject type."
            )
        if self.source_finding_id is not None and not self.source_finding_id.strip():
            raise ContractValueError(
                f"Registry readiness finding {self.finding_id!r} has a blank source finding ID."
            )


@dataclass(frozen=True, slots=True)
class RegistryLayerReadinessReport:
    """Combined readiness report for the registry capability layer."""

    decision: RegistryReadinessDecision
    catalog_report: RegistryValidationReport
    evidence_report: RegistryEvidenceCoverageReport
    findings: tuple[RegistryReadinessFinding, ...]
    capability_id: str = REGISTRY_CAPABILITY_ID

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
            if finding.severity is RegistryReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether the registry capability can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this readiness report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness using this registry completion state."""

        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=self.completed_capability_ids(),
            requested_claim_level=requested_claim_level,
        )

    def findings_for_subject(self, subject_id: str) -> tuple[RegistryReadinessFinding, ...]:
        """Return normalized findings for a registry subject."""

        return tuple(finding for finding in self.findings if finding.subject_id == subject_id)

    def summary(self) -> str:
        """Return a deterministic registry-readiness summary."""

        return (
            f"registry-readiness: {self.decision.value} "
            f"({self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class RegistryLayerReadinessEvaluator:
    """Evaluate whether the registry layer can count toward prototype maturity."""

    def __init__(self, evidence_bundles: Iterable[EvidenceBundle]) -> None:
        """Create a registry-readiness evaluator with available evidence bundles."""

        self._evidence_validator = RegistryEvidenceValidator(evidence_bundles)

    def evaluate(self, catalog: RegistryCatalog) -> RegistryLayerReadinessReport:
        """Evaluate catalog validation and evidence coverage as one readiness decision."""

        catalog_report = catalog.validate()
        evidence_report = self._evidence_validator.validate(catalog)

        findings = (
            self._normalize_catalog_findings(catalog_report.findings)
            + self._normalize_evidence_findings(evidence_report.findings)
        )
        decision = self._decide(
            catalog_report=catalog_report,
            evidence_report=evidence_report,
            findings=findings,
        )

        return RegistryLayerReadinessReport(
            decision=decision,
            catalog_report=catalog_report,
            evidence_report=evidence_report,
            findings=findings,
        )

    @staticmethod
    def _normalize_catalog_findings(
        findings: tuple[RegistryValidationFinding, ...],
    ) -> tuple[RegistryReadinessFinding, ...]:
        """Normalize catalog validation findings."""

        return tuple(
            RegistryReadinessFinding(
                finding_id=f"catalog-{finding.finding_id}",
                severity=_map_catalog_severity(finding.severity),
                source=RegistryReadinessFindingSource.CATALOG,
                message=finding.message,
                subject_id=finding.subject_id,
                subject_type=finding.subject_type.value,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _normalize_evidence_findings(
        findings: tuple[RegistryEvidenceFinding, ...],
    ) -> tuple[RegistryReadinessFinding, ...]:
        """Normalize registry evidence coverage findings."""

        return tuple(
            RegistryReadinessFinding(
                finding_id=f"evidence-{finding.finding_id}",
                severity=_map_evidence_severity(finding.severity),
                source=RegistryReadinessFindingSource.EVIDENCE,
                message=finding.message,
                subject_id=finding.subject_id,
                subject_type=finding.subject_type.value,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        catalog_report: RegistryValidationReport,
        evidence_report: RegistryEvidenceCoverageReport,
        findings: tuple[RegistryReadinessFinding, ...],
    ) -> RegistryReadinessDecision:
        """Return the combined registry-readiness decision."""

        if catalog_report.blocker_count or evidence_report.blocker_count:
            return RegistryReadinessDecision.BLOCKED
        if any(finding.severity.blocks_completion() for finding in findings):
            return RegistryReadinessDecision.BLOCKED
        if catalog_report.warning_count or evidence_report.warning_count:
            return RegistryReadinessDecision.LIMITED
        if any(
            finding.severity is RegistryReadinessFindingSeverity.WARNING for finding in findings
        ):
            return RegistryReadinessDecision.LIMITED
        return RegistryReadinessDecision.COMPLETE


def _map_catalog_severity(
    severity: RegistryFindingSeverity,
) -> RegistryReadinessFindingSeverity:
    """Map catalog finding severity to normalized readiness severity."""

    if severity is RegistryFindingSeverity.BLOCKER:
        return RegistryReadinessFindingSeverity.BLOCKER
    if severity is RegistryFindingSeverity.WARNING:
        return RegistryReadinessFindingSeverity.WARNING
    return RegistryReadinessFindingSeverity.INFO


def _map_evidence_severity(
    severity: RegistryEvidenceFindingSeverity,
) -> RegistryReadinessFindingSeverity:
    """Map evidence finding severity to normalized readiness severity."""

    if severity is RegistryEvidenceFindingSeverity.BLOCKER:
        return RegistryReadinessFindingSeverity.BLOCKER
    if severity is RegistryEvidenceFindingSeverity.WARNING:
        return RegistryReadinessFindingSeverity.WARNING
    return RegistryReadinessFindingSeverity.INFO
