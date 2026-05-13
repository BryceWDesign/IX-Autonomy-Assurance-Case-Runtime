"""Assurance dossier readiness decision surface.

Assurance dossier manifests and validation reports only support serious
prototype maturity when they prove closed trace threads, runtime evidence,
closure artifacts, clean evidence integrity, provenance coverage, export package
links, and non-official prototype disclaimer posture.

The checks are local prototype checks only. They do not claim certification,
authority to operate, deployment approval, official endorsement, or agency
acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.assurance_dossier import AssuranceDossierManifest
from ix_autonomy_assurance_case_runtime.assurance_dossier_validation import (
    AssuranceDossierValidationFinding,
    AssuranceDossierValidationFindingSeverity,
    AssuranceDossierValidationFindingSource,
    AssuranceDossierValidationReport,
    AssuranceDossierValidator,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)

ASSURANCE_DOSSIER_CAPABILITY_ID = "assurance-dossier"


class AssuranceDossierReadinessDecision(RuntimeStrEnum):
    """Decision for whether an assurance dossier can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the assurance dossier layer."""

        return self is AssuranceDossierReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks dossier-based maturity progress."""

        return self is AssuranceDossierReadinessDecision.BLOCKED


class AssuranceDossierReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized assurance dossier readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks dossier completion."""

        return self is AssuranceDossierReadinessFindingSeverity.BLOCKER


class AssuranceDossierReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced an assurance dossier readiness finding."""

    VALIDATION = "validation"
    DOSSIER = "dossier"
    TRACE_THREAD = "trace_thread"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    REVIEW = "review"
    EXPORT = "export"
    DISCLAIMER = "disclaimer"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class AssuranceDossierReadinessFinding:
    """One normalized assurance dossier readiness finding."""

    finding_id: str
    severity: AssuranceDossierReadinessFindingSeverity
    source: AssuranceDossierReadinessFindingSource
    message: str
    dossier_id: str | None = None
    trace_thread_id: str | None = None
    artifact_id: str | None = None
    evidence_reference_id: str | None = None
    evidence_bundle_id: str | None = None
    provenance_manifest_id: str | None = None
    review_workflow_id: str | None = None
    export_package_id: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate assurance dossier readiness finding fields."""

        _require_identifier(self.finding_id, "assurance dossier readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Assurance dossier readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("dossier_id", self.dossier_id),
            ("trace_thread_id", self.trace_thread_id),
            ("artifact_id", self.artifact_id),
            ("evidence_reference_id", self.evidence_reference_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("provenance_manifest_id", self.provenance_manifest_id),
            ("review_workflow_id", self.review_workflow_id),
            ("export_package_id", self.export_package_id),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class AssuranceDossierLayerReadinessReport:
    """Combined readiness report for the assurance-dossier layer."""

    decision: AssuranceDossierReadinessDecision
    validation_report: AssuranceDossierValidationReport
    findings: tuple[AssuranceDossierReadinessFinding, ...]
    capability_id: str = ASSURANCE_DOSSIER_CAPABILITY_ID

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
            if finding.severity is AssuranceDossierReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether the dossier layer can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with dossier completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_dossier(
        self,
        dossier_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for a dossier ID."""

        return tuple(finding for finding in self.findings if finding.dossier_id == dossier_id)

    def findings_for_trace_thread(
        self,
        trace_thread_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for a trace thread ID."""

        return tuple(
            finding for finding in self.findings if finding.trace_thread_id == trace_thread_id
        )

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_provenance_manifest(
        self,
        provenance_manifest_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for a provenance manifest ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.provenance_manifest_id == provenance_manifest_id
        )

    def findings_for_export_package(
        self,
        export_package_id: str,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Return findings for an export package ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.export_package_id == export_package_id
        )

    def summary(self) -> str:
        """Return a deterministic assurance dossier readiness summary."""

        return (
            f"assurance-dossier-readiness: {self.decision.value} "
            f"({self.validation_report.trace_thread_count} trace thread(s), "
            f"{self.validation_report.artifact_count} artifact(s), "
            f"{self.validation_report.evidence_reference_count} evidence reference(s), "
            f"{self.validation_report.evidence_bundle_count} evidence bundle(s), "
            f"{self.validation_report.provenance_manifest_count} provenance manifest(s), "
            f"{self.validation_report.export_package_count} export package(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class AssuranceDossierLayerReadinessEvaluator:
    """Evaluate whether an assurance dossier can count toward prototype maturity."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        provenance_manifest_ids: Iterable[str] = (),
        export_package_ids: Iterable[str] = (),
    ) -> None:
        """Create an assurance dossier readiness evaluator."""

        self._validator = AssuranceDossierValidator(
            evidence_bundles=evidence_bundles,
            provenance_manifest_ids=provenance_manifest_ids,
            export_package_ids=export_package_ids,
        )

    def evaluate(
        self,
        manifest: AssuranceDossierManifest,
    ) -> AssuranceDossierLayerReadinessReport:
        """Evaluate dossier validation and readiness as one surface."""

        validation_report = self._validator.validate(manifest)
        findings = (
            self._build_readiness_findings(manifest)
            + self._normalize_validation_findings(validation_report.findings)
        )
        return AssuranceDossierLayerReadinessReport(
            decision=self._decide(findings),
            validation_report=validation_report,
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Build readiness findings not emitted directly by validation."""

        findings: list[AssuranceDossierReadinessFinding] = []
        if not manifest.is_trace_closed():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-not-trace-closed",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.DOSSIER,
                    message=(
                        "Assurance dossier must be trace-closed before the dossier "
                        "layer can be counted complete."
                    ),
                    dossier_id=manifest.dossier_id,
                )
            )

        for trace_thread_id in manifest.open_trace_thread_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"trace-{trace_thread_id}-open",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.TRACE_THREAD,
                    message="Open dossier trace threads block dossier completion.",
                    dossier_id=manifest.dossier_id,
                    trace_thread_id=trace_thread_id,
                )
            )

        for trace_thread_id in manifest.blocking_trace_thread_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"trace-{trace_thread_id}-blocks-acceptance",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.TRACE_THREAD,
                    message="Blocking dossier trace threads prevent dossier completion.",
                    dossier_id=manifest.dossier_id,
                    trace_thread_id=trace_thread_id,
                )
            )

        if not manifest.runtime_artifact_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-runtime-artifacts",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.ARTIFACT,
                    message="Assurance dossier readiness requires runtime artifacts.",
                    dossier_id=manifest.dossier_id,
                )
            )

        if not manifest.closure_artifact_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-closure-artifacts",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.ARTIFACT,
                    message=(
                        "Assurance dossier readiness requires closure artifacts such as "
                        "review workflow, export package, evidence, provenance, or rollup."
                    ),
                    dossier_id=manifest.dossier_id,
                )
            )

        if not manifest.required_provenance_manifest_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-provenance",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.PROVENANCE,
                    message="Assurance dossier readiness requires provenance manifest links.",
                    dossier_id=manifest.dossier_id,
                )
            )

        if not manifest.export_package_ids():
            findings.append(
                AssuranceDossierReadinessFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-export-package",
                    severity=AssuranceDossierReadinessFindingSeverity.BLOCKER,
                    source=AssuranceDossierReadinessFindingSource.EXPORT,
                    message="Assurance dossier readiness requires export package links.",
                    dossier_id=manifest.dossier_id,
                )
            )

        return tuple(findings)

    @staticmethod
    def _normalize_validation_findings(
        findings: tuple[AssuranceDossierValidationFinding, ...],
    ) -> tuple[AssuranceDossierReadinessFinding, ...]:
        """Normalize assurance dossier validation findings into readiness findings."""

        return tuple(
            AssuranceDossierReadinessFinding(
                finding_id=f"validation-{finding.finding_id}",
                severity=_map_validation_severity(finding.severity),
                source=_map_validation_source(finding.source),
                message=finding.message,
                dossier_id=finding.dossier_id,
                trace_thread_id=finding.trace_thread_id,
                artifact_id=finding.artifact_id,
                evidence_reference_id=finding.evidence_reference_id,
                evidence_bundle_id=finding.evidence_bundle_id,
                provenance_manifest_id=finding.provenance_manifest_id,
                review_workflow_id=finding.review_workflow_id,
                export_package_id=finding.export_package_id,
                source_finding_id=finding.finding_id,
            )
            for finding in findings
        )

    @staticmethod
    def _decide(
        findings: tuple[AssuranceDossierReadinessFinding, ...],
    ) -> AssuranceDossierReadinessDecision:
        """Return the combined assurance dossier readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return AssuranceDossierReadinessDecision.BLOCKED
        if any(
            finding.severity is AssuranceDossierReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return AssuranceDossierReadinessDecision.LIMITED
        return AssuranceDossierReadinessDecision.COMPLETE


def _map_validation_severity(
    severity: AssuranceDossierValidationFindingSeverity,
) -> AssuranceDossierReadinessFindingSeverity:
    """Map assurance dossier validation severity to readiness severity."""

    if severity is AssuranceDossierValidationFindingSeverity.BLOCKER:
        return AssuranceDossierReadinessFindingSeverity.BLOCKER
    if severity is AssuranceDossierValidationFindingSeverity.WARNING:
        return AssuranceDossierReadinessFindingSeverity.WARNING
    return AssuranceDossierReadinessFindingSeverity.INFO


def _map_validation_source(
    source: AssuranceDossierValidationFindingSource,
) -> AssuranceDossierReadinessFindingSource:
    """Map assurance dossier validation source to readiness source."""

    source_map = {
        AssuranceDossierValidationFindingSource.DOSSIER: (
            AssuranceDossierReadinessFindingSource.DOSSIER
        ),
        AssuranceDossierValidationFindingSource.TRACE_THREAD: (
            AssuranceDossierReadinessFindingSource.TRACE_THREAD
        ),
        AssuranceDossierValidationFindingSource.ARTIFACT: (
            AssuranceDossierReadinessFindingSource.ARTIFACT
        ),
        AssuranceDossierValidationFindingSource.EVIDENCE: (
            AssuranceDossierReadinessFindingSource.EVIDENCE
        ),
        AssuranceDossierValidationFindingSource.PROVENANCE: (
            AssuranceDossierReadinessFindingSource.PROVENANCE
        ),
        AssuranceDossierValidationFindingSource.REVIEW: (
            AssuranceDossierReadinessFindingSource.REVIEW
        ),
        AssuranceDossierValidationFindingSource.EXPORT: (
            AssuranceDossierReadinessFindingSource.EXPORT
        ),
        AssuranceDossierValidationFindingSource.DISCLAIMER: (
            AssuranceDossierReadinessFindingSource.DISCLAIMER
        ),
    }
    return source_map.get(source, AssuranceDossierReadinessFindingSource.VALIDATION)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable assurance dossier readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
