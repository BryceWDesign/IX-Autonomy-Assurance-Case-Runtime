"""Export package validation against evidence, provenance, and redaction posture.

Export package manifests describe what should leave the runtime for review. This
validator checks whether the package is structurally exportable, evidence-backed,
provenance-referenced, redaction-aware, and clearly marked as a local prototype
artifact rather than an official approval, certification, ATO, or agency
acceptance package.

The checks are local prototype checks only. They do not claim official submission
readiness, certification, authority to operate, deployment approval, agency
acceptance, or legal records-management compliance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.export_package import (
    ExportArtifactKind,
    ExportArtifactReference,
    ExportPackageManifest,
    ExportRedactionRule,
)


class ExportPackageValidationFindingSeverity(RuntimeStrEnum):
    """Severity for export package validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_export_readiness(self) -> bool:
        """Return whether this finding blocks export readiness."""

        return self is ExportPackageValidationFindingSeverity.BLOCKER


class ExportPackageValidationFindingSource(RuntimeStrEnum):
    """Subsystem that produced an export package validation finding."""

    PACKAGE = "package"
    ARTIFACT = "artifact"
    REDACTION = "redaction"
    EVIDENCE = "evidence"
    PROVENANCE = "provenance"
    DISCLAIMER = "disclaimer"


@dataclass(frozen=True, slots=True)
class ExportPackageValidationFinding:
    """One export package validation finding."""

    finding_id: str
    severity: ExportPackageValidationFindingSeverity
    source: ExportPackageValidationFindingSource
    message: str
    package_id: str | None = None
    artifact_id: str | None = None
    redaction_rule_id: str | None = None
    evidence_bundle_id: str | None = None
    provenance_manifest_id: str | None = None

    def __post_init__(self) -> None:
        """Validate export package validation finding fields."""

        _require_identifier(self.finding_id, "export package validation finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Export package validation finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("package_id", self.package_id),
            ("artifact_id", self.artifact_id),
            ("redaction_rule_id", self.redaction_rule_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("provenance_manifest_id", self.provenance_manifest_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ExportPackageValidationReport:
    """Validation report for one export package manifest."""

    package_id: str
    artifact_count: int
    redaction_rule_count: int
    evidence_bundle_count: int
    provenance_manifest_count: int
    findings: tuple[ExportPackageValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate export package validation report counters."""

        _require_identifier(self.package_id, "package_id")
        for field_name, value in (
            ("artifact_count", self.artifact_count),
            ("redaction_rule_count", self.redaction_rule_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
            ("provenance_manifest_count", self.provenance_manifest_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(finding.severity.blocks_export_readiness() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ExportPackageValidationFindingSeverity.WARNING
        )

    def is_export_ready(self) -> bool:
        """Return whether export package validation has no blockers."""

        return self.blocker_count == 0

    def findings_for_artifact(
        self,
        artifact_id: str,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Return findings for an artifact ID."""

        return tuple(finding for finding in self.findings if finding.artifact_id == artifact_id)

    def findings_for_redaction_rule(
        self,
        redaction_rule_id: str,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Return findings for a redaction rule ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.redaction_rule_id == redaction_rule_id
        )

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_provenance_manifest(
        self,
        provenance_manifest_id: str,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Return findings for a provenance manifest ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.provenance_manifest_id == provenance_manifest_id
        )

    def summary(self) -> str:
        """Return a deterministic export package validation summary."""

        return (
            f"export-package-validation: {self.package_id} "
            f"({self.artifact_count} artifact(s), "
            f"{self.redaction_rule_count} redaction rule(s), "
            f"{self.evidence_bundle_count} evidence bundle(s), "
            f"{self.provenance_manifest_count} provenance manifest(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class ExportPackageValidator:
    """Validate export package manifests against evidence and provenance coverage."""

    def __init__(
        self,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        provenance_manifest_ids: Iterable[str] = (),
    ) -> None:
        """Create an export package validator."""

        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)
        self._provenance_manifest_ids = _normalize_identifier_set(
            tuple(provenance_manifest_ids),
            "provenance_manifest_ids",
        )

    def validate(self, manifest: ExportPackageManifest) -> ExportPackageValidationReport:
        """Validate one export package manifest."""

        findings = (
            self._validate_package_posture(manifest)
            + self._validate_artifacts(manifest)
            + self._validate_redaction(manifest)
            + self._validate_evidence(manifest)
            + self._validate_provenance(manifest)
            + self._validate_disclaimer(manifest)
        )
        return ExportPackageValidationReport(
            package_id=manifest.package_id,
            artifact_count=len(manifest.artifacts),
            redaction_rule_count=len(manifest.redaction_rules),
            evidence_bundle_count=len(manifest.required_evidence_bundle_ids()),
            provenance_manifest_count=len(manifest.required_provenance_manifest_ids()),
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
                    f"Duplicate export package evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_package_posture(
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate package-level export posture."""

        findings: list[ExportPackageValidationFinding] = []
        if not manifest.status.can_be_exported():
            findings.append(
                ExportPackageValidationFinding(
                    finding_id=f"package-{manifest.package_id}-status-not-exportable",
                    severity=ExportPackageValidationFindingSeverity.BLOCKER,
                    source=ExportPackageValidationFindingSource.PACKAGE,
                    message="Export package status does not permit export emission.",
                    package_id=manifest.package_id,
                )
            )
        if not manifest.package_format.is_machine_readable():
            findings.append(
                ExportPackageValidationFinding(
                    finding_id=f"package-{manifest.package_id}-format-not-machine-readable",
                    severity=ExportPackageValidationFindingSeverity.BLOCKER,
                    source=ExportPackageValidationFindingSource.PACKAGE,
                    message="Export package format must be machine-readable.",
                    package_id=manifest.package_id,
                )
            )
        if not manifest.required_evidence_bundle_ids():
            findings.append(
                ExportPackageValidationFinding(
                    finding_id=f"package-{manifest.package_id}-no-evidence",
                    severity=ExportPackageValidationFindingSeverity.BLOCKER,
                    source=ExportPackageValidationFindingSource.EVIDENCE,
                    message="Export package requires evidence bundle references.",
                    package_id=manifest.package_id,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_artifacts(
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate artifact-level coverage expectations."""

        findings: list[ExportPackageValidationFinding] = []
        required_kinds = {
            ExportArtifactKind.ASSURANCE_CASE,
            ExportArtifactKind.TRACEABILITY_GRAPH,
            ExportArtifactKind.EVIDENCE_BUNDLE,
            ExportArtifactKind.READINESS_REPORT,
            ExportArtifactKind.REVIEW_WORKFLOW,
        }
        present_kinds = {artifact.kind for artifact in manifest.artifacts}
        for missing_kind in sorted(required_kinds - present_kinds, key=lambda kind: kind.value):
            findings.append(
                ExportPackageValidationFinding(
                    finding_id=f"package-{manifest.package_id}-missing-{missing_kind.value}",
                    severity=ExportPackageValidationFindingSeverity.WARNING,
                    source=ExportPackageValidationFindingSource.ARTIFACT,
                    message=(
                        "Export package is stronger when it includes "
                        f"{missing_kind.value!r} coverage."
                    ),
                    package_id=manifest.package_id,
                )
            )

        for artifact in manifest.artifacts:
            if artifact.required and artifact.kind.requires_evidence_reference() and not artifact.evidence_bundle_ids:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"artifact-{artifact.artifact_id}-missing-evidence",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.ARTIFACT,
                        message="Required export artifact is missing evidence bundle references.",
                        package_id=manifest.package_id,
                        artifact_id=artifact.artifact_id,
                    )
                )
            if artifact.kind.is_runtime_artifact() and not artifact.provenance_manifest_ids:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"artifact-{artifact.artifact_id}-runtime-no-provenance",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.PROVENANCE,
                        message="Runtime export artifacts require provenance manifest references.",
                        package_id=manifest.package_id,
                        artifact_id=artifact.artifact_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _validate_redaction(
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate redaction coverage for sensitive export artifacts."""

        findings: list[ExportPackageValidationFinding] = []
        rule_kinds = _redaction_rule_kinds(manifest.redaction_rules)
        for artifact in manifest.artifacts:
            if not artifact.needs_redaction_review():
                continue
            if artifact.kind not in rule_kinds:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"artifact-{artifact.artifact_id}-missing-redaction-rule",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.REDACTION,
                        message="Sensitive export artifact has no matching redaction rule.",
                        package_id=manifest.package_id,
                        artifact_id=artifact.artifact_id,
                    )
                )
        for rule in manifest.redaction_rules:
            if rule.required and not rule.evidence_bundle_ids:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"redaction-{rule.rule_id}-missing-evidence",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.REDACTION,
                        message="Required redaction rule lacks evidence bundle references.",
                        package_id=manifest.package_id,
                        redaction_rule_id=rule.rule_id,
                    )
                )
        return tuple(findings)

    def _validate_evidence(
        self,
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate evidence bundle existence and integrity."""

        findings: list[ExportPackageValidationFinding] = []
        for bundle_id in manifest.required_evidence_bundle_ids():
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.EVIDENCE,
                        message="Export package references a missing evidence bundle.",
                        package_id=manifest.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue
            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        package_id=manifest.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=ExportPackageValidationFindingSeverity.WARNING,
                        source=ExportPackageValidationFindingSource.EVIDENCE,
                        message=warning,
                        package_id=manifest.package_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    def _validate_provenance(
        self,
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate provenance manifest reference coverage."""

        findings: list[ExportPackageValidationFinding] = []
        for manifest_id in manifest.required_provenance_manifest_ids():
            if manifest_id not in self._provenance_manifest_ids:
                findings.append(
                    ExportPackageValidationFinding(
                        finding_id=f"provenance-{manifest_id}-missing",
                        severity=ExportPackageValidationFindingSeverity.BLOCKER,
                        source=ExportPackageValidationFindingSource.PROVENANCE,
                        message="Export package references a missing provenance manifest.",
                        package_id=manifest.package_id,
                        provenance_manifest_id=manifest_id,
                    )
                )
        if not manifest.required_provenance_manifest_ids():
            findings.append(
                ExportPackageValidationFinding(
                    finding_id=f"package-{manifest.package_id}-no-provenance",
                    severity=ExportPackageValidationFindingSeverity.BLOCKER,
                    source=ExportPackageValidationFindingSource.PROVENANCE,
                    message="Export package requires provenance manifest references.",
                    package_id=manifest.package_id,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_disclaimer(
        manifest: ExportPackageManifest,
    ) -> tuple[ExportPackageValidationFinding, ...]:
        """Validate non-official prototype disclaimer posture."""

        disclaimer_lower = manifest.disclaimer.lower()
        required_terms = ("prototype", "not", "certification", "agency acceptance")
        missing_terms = tuple(term for term in required_terms if term not in disclaimer_lower)
        if not missing_terms:
            return ()
        return (
            ExportPackageValidationFinding(
                finding_id=f"package-{manifest.package_id}-disclaimer-weak",
                severity=ExportPackageValidationFindingSeverity.BLOCKER,
                source=ExportPackageValidationFindingSource.DISCLAIMER,
                message=(
                    "Export package disclaimer must clearly avoid certification, official "
                    "approval, deployment, or agency acceptance claims."
                ),
                package_id=manifest.package_id,
            ),
        )


def _redaction_rule_kinds(rules: tuple[ExportRedactionRule, ...]) -> set[ExportArtifactKind]:
    """Return artifact kinds covered by redaction rules."""

    covered: set[ExportArtifactKind] = set()
    for rule in rules:
        covered.update(rule.target_artifact_kinds)
    return covered


def _normalize_identifier_set(values: tuple[str, ...], field_name: str) -> set[str]:
    """Validate identifier values and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicates.")
    return set(normalized)


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable export package validation identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != normalized:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized
