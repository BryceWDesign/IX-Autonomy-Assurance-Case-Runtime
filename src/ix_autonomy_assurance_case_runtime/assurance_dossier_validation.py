"""Assurance dossier validation against trace, evidence, provenance, and export links.

Assurance dossier manifests describe the final trace-closure surface from mission
need to evidence-backed review. This validator checks whether those records are
grounded in local evidence bundles, provenance manifest IDs, export package IDs,
runtime artifacts, review workflow links, and non-official prototype disclaimers.

The checks are local prototype checks only. They do not claim certification,
authority to operate, deployment approval, official endorsement, or agency
acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.assurance_dossier import (
    AssuranceDossierManifest,
    DossierArtifactKind,
    DossierArtifactReference,
    DossierEvidenceReference,
)
from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle


class AssuranceDossierValidationFindingSeverity(RuntimeStrEnum):
    """Severity for assurance dossier validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_dossier_readiness(self) -> bool:
        """Return whether this finding blocks dossier readiness."""

        return self is AssuranceDossierValidationFindingSeverity.BLOCKER


class AssuranceDossierValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced an assurance dossier validation finding."""

    DOSSIER = "dossier"
    TRACE_THREAD = "trace_thread"
    ARTIFACT = "artifact"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    REVIEW = "review"
    EXPORT = "export"
    DISCLAIMER = "disclaimer"


@dataclass(frozen=True, slots=True)
class AssuranceDossierValidationFinding:
    """One assurance dossier validation finding."""

    finding_id: str
    severity: AssuranceDossierValidationFindingSeverity
    source: AssuranceDossierValidationFindingSource
    message: str
    dossier_id: str | None = None
    trace_thread_id: str | None = None
    artifact_id: str | None = None
    evidence_reference_id: str | None = None
    evidence_bundle_id: str | None = None
    provenance_manifest_id: str | None = None
    review_workflow_id: str | None = None
    export_package_id: str | None = None
    requirement_id: str | None = None
    hazard_id: str | None = None

    def __post_init__(self) -> None:
        """Validate assurance dossier validation finding fields."""

        _require_identifier(self.finding_id, "assurance dossier validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Assurance dossier validation finding {self.finding_id!r} needs a message."
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
            ("requirement_id", self.requirement_id),
            ("hazard_id", self.hazard_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class AssuranceDossierValidationReport:
    """Validation report for one assurance dossier manifest."""

    dossier_id: str
    trace_thread_count: int
    artifact_count: int
    evidence_reference_count: int
    evidence_bundle_count: int
    provenance_manifest_count: int
    export_package_count: int
    findings: tuple[AssuranceDossierValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate assurance dossier validation report counters."""

        _require_identifier(self.dossier_id, "dossier_id")
        for field_name, value in (
            ("trace_thread_count", self.trace_thread_count),
            ("artifact_count", self.artifact_count),
            ("evidence_reference_count", self.evidence_reference_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
            ("provenance_manifest_count", self.provenance_manifest_count),
            ("export_package_count", self.export_package_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(
            finding.severity.blocks_dossier_readiness() for finding in self.findings
        )

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is AssuranceDossierValidationFindingSeverity.WARNING
        )

    def is_dossier_ready(self) -> bool:
        """Return whether dossier validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_trace_thread(
        self,
        trace_thread_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for a trace thread ID."""

        return tuple(
            finding for finding in self.findings if finding.trace_thread_id == trace_thread_id
        )

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_evidence_reference(
        self,
        evidence_reference_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for an evidence reference ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_reference_id == evidence_reference_id
        )

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_provenance_manifest(
        self,
        provenance_manifest_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for a provenance manifest ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.provenance_manifest_id == provenance_manifest_id
        )

    def findings_for_export_package(
        self,
        export_package_id: str,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Return findings for an export package ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.export_package_id == export_package_id
        )

    def summary(self) -> str:
        """Return a deterministic assurance dossier validation summary."""

        return (
            f"assurance-dossier-validation: {self.dossier_id} "
            f"({self.trace_thread_count} trace thread(s), "
            f"{self.artifact_count} artifact(s), "
            f"{self.evidence_reference_count} evidence reference(s), "
            f"{self.evidence_bundle_count} evidence bundle(s), "
            f"{self.provenance_manifest_count} provenance manifest(s), "
            f"{self.export_package_count} export package(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class AssuranceDossierValidator:
    """Validate assurance dossier manifests against local evidence and references."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        provenance_manifest_ids: Iterable[str] = (),
        export_package_ids: Iterable[str] = (),
    ) -> None:
        """Create an assurance dossier validator."""

        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)
        self._provenance_manifest_ids = _normalize_identifier_set(
            tuple(provenance_manifest_ids),
            "provenance_manifest_ids",
        )
        self._export_package_ids = _normalize_identifier_set(
            tuple(export_package_ids),
            "export_package_ids",
        )

    def validate(
        self,
        manifest: AssuranceDossierManifest,
    ) -> AssuranceDossierValidationReport:
        """Validate one assurance dossier manifest."""

        findings = (
            self._validate_dossier_posture(manifest)
            + self._validate_trace_threads(manifest)
            + self._validate_artifacts(manifest)
            + self._validate_evidence_references(manifest)
            + self._validate_evidence(manifest)
            + self._validate_provenance(manifest)
            + self._validate_exports(manifest)
            + self._validate_disclaimer(manifest)
        )
        return AssuranceDossierValidationReport(
            dossier_id=manifest.dossier_id,
            trace_thread_count=len(manifest.trace_threads),
            artifact_count=len(manifest.artifacts),
            evidence_reference_count=len(manifest.evidence_references),
            evidence_bundle_count=len(manifest.required_evidence_bundle_ids()),
            provenance_manifest_count=len(manifest.required_provenance_manifest_ids()),
            export_package_count=len(manifest.export_package_ids()),
            findings=findings,
        )

    @staticmethod
    def _index_evidence_bundles(
        bundles: Iterable[EvidenceBundle],
    ) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(
                    f"Duplicate assurance dossier evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_dossier_posture(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate dossier-level closure posture."""

        findings: list[AssuranceDossierValidationFinding] = []
        if not manifest.status.can_support_trace_closure():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-status-not-trace-closed",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.DOSSIER,
                    message="Assurance dossier status does not support trace closure.",
                    dossier_id=manifest.dossier_id,
                )
            )
        if manifest.open_trace_thread_ids():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-open-trace-threads",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.TRACE_THREAD,
                    message="Assurance dossier contains trace threads that are not closed.",
                    dossier_id=manifest.dossier_id,
                )
            )
        if manifest.blocking_trace_thread_ids():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-blocking-trace-threads",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.TRACE_THREAD,
                    message="Assurance dossier contains trace threads that block acceptance.",
                    dossier_id=manifest.dossier_id,
                )
            )
        if not manifest.runtime_artifact_ids():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-runtime-artifacts",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.ARTIFACT,
                    message="Assurance dossier requires at least one runtime artifact.",
                    dossier_id=manifest.dossier_id,
                )
            )
        if not manifest.closure_artifact_ids():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-closure-artifacts",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.ARTIFACT,
                    message="Assurance dossier requires at least one closure artifact.",
                    dossier_id=manifest.dossier_id,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_trace_threads(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate trace thread links to evidence, review, and export records."""

        findings: list[AssuranceDossierValidationFinding] = []
        evidence_reference_ids = {
            reference.reference_id for reference in manifest.evidence_references
        }
        review_workflow_source_ids = _source_record_ids_for_kind(
            manifest.artifacts,
            DossierArtifactKind.REVIEW_WORKFLOW,
        )
        for thread in manifest.trace_threads:
            if not thread.is_closed():
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"trace-{thread.trace_thread_id}-not-closed",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.TRACE_THREAD,
                        message="Dossier trace thread is not closed.",
                        dossier_id=manifest.dossier_id,
                        trace_thread_id=thread.trace_thread_id,
                    )
                )
            for reference_id in thread.evidence_reference_ids:
                if reference_id not in evidence_reference_ids:
                    findings.append(
                        AssuranceDossierValidationFinding(
                            finding_id=(
                                f"trace-{thread.trace_thread_id}-evidence-ref-"
                                f"{reference_id}-missing"
                            ),
                            severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                            source=AssuranceDossierValidationFindingSource.EVIDENCE,
                            message="Trace thread references a missing evidence reference.",
                            dossier_id=manifest.dossier_id,
                            trace_thread_id=thread.trace_thread_id,
                            evidence_reference_id=reference_id,
                        )
                    )
            for review_workflow_id in thread.review_workflow_ids:
                if review_workflow_id not in review_workflow_source_ids:
                    findings.append(
                        AssuranceDossierValidationFinding(
                            finding_id=(
                                f"trace-{thread.trace_thread_id}-review-"
                                f"{review_workflow_id}-missing"
                            ),
                            severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                            source=AssuranceDossierValidationFindingSource.REVIEW,
                            message="Trace thread references a missing review workflow artifact.",
                            dossier_id=manifest.dossier_id,
                            trace_thread_id=thread.trace_thread_id,
                            review_workflow_id=review_workflow_id,
                        )
                    )
            findings.extend(_trace_requirement_and_hazard_findings(manifest, thread.trace_thread_id))
        return tuple(findings)

    @staticmethod
    def _validate_artifacts(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate artifact coverage and provenance backing."""

        findings: list[AssuranceDossierValidationFinding] = []
        present_kinds = {artifact.kind for artifact in manifest.artifacts}
        required_kinds = {
            DossierArtifactKind.REVIEW_WORKFLOW,
            DossierArtifactKind.EXPORT_PACKAGE,
            DossierArtifactKind.READINESS_ROLLUP,
        }
        for missing_kind in sorted(required_kinds - present_kinds, key=lambda kind: kind.value):
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-missing-{missing_kind.value}",
                    severity=AssuranceDossierValidationFindingSeverity.WARNING,
                    source=AssuranceDossierValidationFindingSource.ARTIFACT,
                    message=f"Assurance dossier is stronger with {missing_kind.value} coverage.",
                    dossier_id=manifest.dossier_id,
                )
            )

        for artifact in manifest.artifacts:
            if (
                artifact.kind is not DossierArtifactKind.PROVENANCE_MANIFEST
                and not artifact.is_provenance_backed()
            ):
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"artifact-{artifact.artifact_id}-no-provenance",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.PROVENANCE,
                        message="Dossier artifact lacks provenance manifest references.",
                        dossier_id=manifest.dossier_id,
                        artifact_id=artifact.artifact_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_evidence_references(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate evidence references against artifact and trace links."""

        findings: list[AssuranceDossierValidationFinding] = []
        artifact_ids = {artifact.artifact_id for artifact in manifest.artifacts}
        thread_requirement_ids = {
            requirement_id
            for thread in manifest.trace_threads
            for requirement_id in thread.requirement_ids
        }
        thread_hazard_ids = {
            hazard_id for thread in manifest.trace_threads for hazard_id in thread.hazard_ids
        }

        for reference in manifest.evidence_references:
            for artifact_id in reference.supports_artifact_ids:
                if artifact_id not in artifact_ids:
                    findings.append(
                        AssuranceDossierValidationFinding(
                            finding_id=(
                                f"evidence-ref-{reference.reference_id}-artifact-"
                                f"{artifact_id}-missing"
                            ),
                            severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                            source=AssuranceDossierValidationFindingSource.EVIDENCE,
                            message="Evidence reference supports a missing dossier artifact.",
                            dossier_id=manifest.dossier_id,
                            evidence_reference_id=reference.reference_id,
                            artifact_id=artifact_id,
                        )
                    )
            for requirement_id in reference.supports_requirement_ids:
                if requirement_id not in thread_requirement_ids:
                    findings.append(
                        AssuranceDossierValidationFinding(
                            finding_id=(
                                f"evidence-ref-{reference.reference_id}-requirement-"
                                f"{requirement_id}-missing"
                            ),
                            severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                            source=AssuranceDossierValidationFindingSource.TRACE_THREAD,
                            message="Evidence reference supports a requirement not in any thread.",
                            dossier_id=manifest.dossier_id,
                            evidence_reference_id=reference.reference_id,
                            requirement_id=requirement_id,
                        )
                    )
            for hazard_id in reference.supports_hazard_ids:
                if hazard_id not in thread_hazard_ids:
                    findings.append(
                        AssuranceDossierValidationFinding(
                            finding_id=(
                                f"evidence-ref-{reference.reference_id}-hazard-"
                                f"{hazard_id}-missing"
                            ),
                            severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                            source=AssuranceDossierValidationFindingSource.TRACE_THREAD,
                            message="Evidence reference supports a hazard not in any thread.",
                            dossier_id=manifest.dossier_id,
                            evidence_reference_id=reference.reference_id,
                            hazard_id=hazard_id,
                        )
                    )
        return tuple(findings)

    def _validate_evidence(
        self,
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate referenced evidence bundle existence and integrity."""

        findings: list[AssuranceDossierValidationFinding] = []
        for bundle_id in manifest.required_evidence_bundle_ids():
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.EVIDENCE,
                        message="Assurance dossier references a missing evidence bundle.",
                        dossier_id=manifest.dossier_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue
            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        dossier_id=manifest.dossier_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=AssuranceDossierValidationFindingSeverity.WARNING,
                        source=AssuranceDossierValidationFindingSource.EVIDENCE,
                        message=warning,
                        dossier_id=manifest.dossier_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    def _validate_provenance(
        self,
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate provenance manifest reference coverage."""

        findings: list[AssuranceDossierValidationFinding] = []
        required_ids = manifest.required_provenance_manifest_ids()
        if not required_ids:
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-provenance",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.PROVENANCE,
                    message="Assurance dossier requires provenance manifest references.",
                    dossier_id=manifest.dossier_id,
                )
            )
        for manifest_id in required_ids:
            if manifest_id not in self._provenance_manifest_ids:
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"provenance-{manifest_id}-missing",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.PROVENANCE,
                        message="Assurance dossier references a missing provenance manifest.",
                        dossier_id=manifest.dossier_id,
                        provenance_manifest_id=manifest_id,
                    )
                )
        return tuple(findings)

    def _validate_exports(
        self,
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate export package references."""

        findings: list[AssuranceDossierValidationFinding] = []
        if not manifest.export_package_ids():
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"dossier-{manifest.dossier_id}-no-export-package",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.EXPORT,
                    message="Assurance dossier requires export package references.",
                    dossier_id=manifest.dossier_id,
                )
            )
        for package_id in manifest.export_package_ids():
            if package_id not in self._export_package_ids:
                findings.append(
                    AssuranceDossierValidationFinding(
                        finding_id=f"export-{package_id}-missing",
                        severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                        source=AssuranceDossierValidationFindingSource.EXPORT,
                        message="Assurance dossier references a missing export package.",
                        dossier_id=manifest.dossier_id,
                        export_package_id=package_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_disclaimer(
        manifest: AssuranceDossierManifest,
    ) -> tuple[AssuranceDossierValidationFinding, ...]:
        """Validate non-official prototype disclaimer posture."""

        disclaimer_lower = manifest.disclaimer.lower()
        required_terms = ("prototype", "not", "certification", "agency acceptance")
        missing_terms = tuple(term for term in required_terms if term not in disclaimer_lower)
        if not missing_terms:
            return ()
        return (
            AssuranceDossierValidationFinding(
                finding_id=f"dossier-{manifest.dossier_id}-disclaimer-weak",
                severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                source=AssuranceDossierValidationFindingSource.DISCLAIMER,
                message=(
                    "Assurance dossier disclaimer must clearly avoid certification, "
                    "deployment, authority-to-operate, or agency acceptance claims."
                ),
                dossier_id=manifest.dossier_id,
            ),
        )


def _trace_requirement_and_hazard_findings(
    manifest: AssuranceDossierManifest,
    trace_thread_id: str,
) -> tuple[AssuranceDossierValidationFinding, ...]:
    """Validate that evidence references support a trace thread's requirements and hazards."""

    thread = next(
        dossier_thread
        for dossier_thread in manifest.trace_threads
        if dossier_thread.trace_thread_id == trace_thread_id
    )
    evidence_by_id = {
        reference.reference_id: reference for reference in manifest.evidence_references
    }
    linked_references = tuple(
        evidence_by_id[reference_id]
        for reference_id in thread.evidence_reference_ids
        if reference_id in evidence_by_id
    )
    supported_requirements = {
        requirement_id
        for reference in linked_references
        for requirement_id in reference.supports_requirement_ids
    }
    supported_hazards = {
        hazard_id for reference in linked_references for hazard_id in reference.supports_hazard_ids
    }

    findings: list[AssuranceDossierValidationFinding] = []
    for requirement_id in thread.requirement_ids:
        if requirement_id not in supported_requirements:
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=(
                        f"trace-{thread.trace_thread_id}-requirement-"
                        f"{requirement_id}-unsupported"
                    ),
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.EVIDENCE,
                    message="Trace thread requirement lacks supporting evidence reference.",
                    dossier_id=manifest.dossier_id,
                    trace_thread_id=thread.trace_thread_id,
                    requirement_id=requirement_id,
                )
            )
    for hazard_id in thread.hazard_ids:
        if hazard_id not in supported_hazards:
            findings.append(
                AssuranceDossierValidationFinding(
                    finding_id=f"trace-{thread.trace_thread_id}-hazard-{hazard_id}-unsupported",
                    severity=AssuranceDossierValidationFindingSeverity.BLOCKER,
                    source=AssuranceDossierValidationFindingSource.EVIDENCE,
                    message="Trace thread hazard lacks supporting evidence reference.",
                    dossier_id=manifest.dossier_id,
                    trace_thread_id=thread.trace_thread_id,
                    hazard_id=hazard_id,
                )
            )
    return tuple(findings)


def _source_record_ids_for_kind(
    artifacts: tuple[DossierArtifactReference, ...],
    kind: DossierArtifactKind,
) -> set[str]:
    """Return source record IDs for artifacts of a kind."""

    return {artifact.source_record_id for artifact in artifacts if artifact.kind is kind}


def _normalize_identifier_set(values: tuple[str, ...], field_name: str) -> set[str]:
    """Validate identifier values and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
    return set(normalized)


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable assurance dossier validation identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != normalized:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized
