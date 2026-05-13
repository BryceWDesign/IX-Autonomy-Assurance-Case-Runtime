"""Export package readiness decision surface.

Export package manifests and validation reports only support serious prototype
maturity when they prove machine-readable package posture, clean evidence,
provenance coverage, runtime artifact coverage, redaction-aware packaging, and
clear non-official prototype disclaimers. This module turns those checks into
the capability gate for the ``audit-report-export`` target.

The checks are local prototype checks only. They do not claim official submission
readiness, certification, authority to operate, deployment approval, agency
acceptance, or legal records-management compliance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.export_package import ExportPackageManifest
from ix_autonomy_assurance_case_runtime.export_package_validation import (
    ExportPackageValidationFinding,
    ExportPackageValidationFindingSeverity,
    ExportPackageValidationFindingSource,
    ExportPackageValidationReport,
    ExportPackageValidator,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

EXPORT_PACKAGE_CAPABILITY_ID = "audit-report-export"


class ExportPackageReadinessDecision(RuntimeStrEnum):
    """Decision for whether export packaging can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the export package capability."""

        return self is ExportPackageReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks export-based maturity progress."""

        return self is ExportPackageReadinessDecision.BLOCKED


class ExportPackageReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized export package readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks export package completion."""

        return self is ExportPackageReadinessFindingSeverity.BLOCKER


class ExportPackageReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced an export package readiness finding."""

    VALIDATION = "validation"
    PACKAGE = "package"
    ARTIFACT = "artifact"
    REDACTION = "redaction"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    DISCLAIMER = "disclaimer"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class ExportPackageReadinessFinding:
    """One normalized export package readiness finding."""

    finding_id: str
    severity: ExportPackageReadinessFindingSeverity
    source: ExportPackageReadinessFindingSource
    message: str
    package_id: str | None = None
    artifact_id: str | None = None
    redaction_rule_id: str | None = None
    evidence_bundle_id: str | None = None
    provenance_manifest_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate export package readiness finding fields."""

        _require_identifier(self.finding_id, "export package readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Export package readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("package_id", self.package_id),
            ("artifact_id", self.artifact_id),
            ("redaction_rule_id", self.redaction_rule_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("provenance_manifest_id", self.provenance_manifest_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ExportPackageLayerReadinessReport:
    """Combined readiness report for the audit/report/export capability layer."""

    decision: ExportPackageReadinessDecision
    validation_report: ExportPackageValidationReport
    findings: tuple[ExportPackageReadinessFinding, ...]
    capability_id: str = EXPORT_PACKAGE_CAPABILITY_ID

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
            if finding.severity is ExportPackageReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether export packaging can count as complete."""

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
        """Evaluate prototype claim readiness with export package completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_package(
        self,
        package_id: str,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Return findings for a package ID."""

        return tuple(finding for finding in self.findings if finding.package_id == package_id)

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_redaction_rule(
        self,
        redaction_rule_id: str,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Return findings for a redaction rule ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.redaction_rule_id == redaction_rule_id
        )

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_provenance_manifest(
        self,
        provenance_manifest_id: str,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Return findings for a provenance manifest ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.provenance_manifest_id == provenance_manifest_id
        )

    def summary(self) -> str:
        """Return a deterministic export package readiness summary."""

        return (
            f"export-package-readiness: {self.decision.value} "
            f"({self.validation_report.artifact_count} artifact(s), "
            f"{self.validation_report.redaction_rule_count} redaction rule(s), "
            f"{self.validation_report.evidence_bundle_count} evidence bundle(s), "
            f"{self.validation_report.provenance_manifest_count} provenance manifest(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class ExportPackageLayerReadinessEvaluator:
    """Evaluate whether export packaging can count toward prototype maturity."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        provenance_manifest_ids: Iterable[str] = (),
    ) -> None:
        """Create an export package readiness evaluator."""

        self._validator = ExportPackageValidator(
            evidence_bundles=evidence_bundles,
            provenance_manifest_ids=provenance_manifest_ids,
        )

    def evaluate(
        self,
        manifest: ExportPackageManifest,
    ) -> ExportPackageLayerReadinessReport:
        """Evaluate export package validation and readiness as one surface."""

        validation_report = self._validator.validate(manifest)
        findings = (
            self._build_readiness_findings(manifest)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return ExportPackageLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[ExportPackageReadinessFinding] = []
        if not manifest.is_export_ready():
            findings.append(
                ExportPackageReadinessFinding(
                    finding_id=f"package-{manifest.package_id}-not-export-ready",
                    severity=ExportPackageReadinessFindingSeverity.BLOCKER,
                    source=ExportPackageReadinessFindingSource.PACKAGE,
                    message=(
                        "Export package manifest must be structurally export-ready before "
                        "the export capability can be counted complete."
                    ),
                    package_id=manifest.package_id,
                )
            )
        if not manifest.runtime_artifact_ids():
            findings.append(
                ExportPackageReadinessFinding(
                    finding_id=f"package-{manifest.package_id}-no-runtime-artifacts",
                    severity=ExportPackageReadinessFindingSeverity.BLOCKER,
                    source=ExportPackageReadinessFindingSource.ARTIFACT,
                    message=(
                        "Export package readiness requires at least one runtime artifact "
                        "such as a run ledger, telemetry replay, scenario campaign, or "
                        "monitoring trail."
                    ),
                    package_id=manifest.package_id,
                )
            )
        if not manifest.required_provenance_manifest_ids():
            findings.append(
                ExportPackageReadinessFinding(
                    finding_id=f"package-{manifest.package_id}-no-provenance-references",
                    severity=ExportPackageReadinessFindingSeverity.BLOCKER,
                    source=ExportPackageReadinessFindingSource.PROVENANCE,
                    message="Export package readiness requires provenance manifest references.",
                    package_id=manifest.package_id,
                )
            )
        if manifest.sensitive_artifact_ids() and not manifest.redaction_rules:
            findings.append(
                ExportPackageReadinessFinding(
                    finding_id=f"package-{manifest.package_id}-sensitive-without-redaction",
                    severity=ExportPackageReadinessFindingSeverity.BLOCKER,
                    source=ExportPackageReadinessFindingSource.REDACTION,
                    message=(
                        "Sensitive export artifacts require redaction rules before export "
                        "package completion."
                    ),
                    package_id=manifest.package_id,
                )
            )
        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[ExportPackageValidationFinding, ...],
    ) -> tuple[ExportPackageReadinessFinding, ...]:
        """Normalize export package validation findings into readiness findings."""

        return tuple(
            ExportPackageReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=_map_validation_source(finding.source),
                message=finding.message,
                package_id=finding.package_id,
                artifact_id=finding.artifact_id,
                redaction_rule_id=finding.redaction_rule_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                provenance_manifest_id=finding.provenance_manifest_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[ExportPackageReadinessFinding, ...],
    ) -> ExportPackageReadinessDecision:
        """Return the combined export package readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return ExportPackageReadinessDecision.BLOCKED
        if any(
            finding.severity is ExportPackageReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return ExportPackageReadinessDecision.LIMITED
        return ExportPackageReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: ExportPackageValidationFindingSeverity,
) -> ExportPackageReadinessFindingSeverity:
    """Map export package validation severity to readiness severity."""

    if severity is ExportPackageValidationFindingSeverity.BLOCKER:
        return ExportPackageReadinessFindingSeverity.BLOCKER
    if severity is ExportPackageValidationFindingSeverity.WARNING:
        return ExportPackageReadinessFindingSeverity.WARNING
    return ExportPackageReadinessFindingSeverity.INFO


def _map_validation_source(
    source: ExportPackageValidationFindingSource,
) -> ExportPackageReadinessFindingSource:
    """Map export package validation source to readiness source."""

    source_map = {
        ExportPackageValidationFindingSource.PACKAGE: ExportPackageReadinessFindingSource.PACKAGE,
        ExportPackageValidationFindingSource.ARTIFACT: ExportPackageReadinessFindingSource.ARTIFACT,
        ExportPackageValidationFindingSource.REDACTION: (
            ExportPackageReadinessFindingSource.REDACTION
        ),
        ExportPackageValidationFindingSource.EVIDENCE: ExportPackageReadinessFindingSource.EVIDENCE,
        ExportPackageValidationFindingSource.PROVENANCE: (
            ExportPackageReadinessFindingSource.PROVENANCE
        ),
        ExportPackageValidationFindingSource.DISCLAIMER: (
            ExportPackageReadinessFindingSource.DISCLAIMER
        ),
    }
    return source_map.get(source, ExportPackageReadinessFindingSource.VALIDATION)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable export package readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
