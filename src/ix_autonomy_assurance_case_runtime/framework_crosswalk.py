"""Framework crosswalk records for federal/IC/DoD-style assurance alignment.

The serious prototype needs a standards/control crosswalk layer so runtime
artifacts can be mapped to recognizable governance, acquisition, testing,
provenance, and oversight objectives. This module does not claim certification,
official endorsement, authority to operate, or complete compliance. It only
models transparent local mappings that can later be exported, reviewed, and
validated.
"""

from __future__ import annotations

from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable crosswalk identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate nonblank human-readable text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _require_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a nonempty tuple of nonblank unique strings."""

    if not values:
        raise ContractValueError(f"{field_name} must not be empty.")
    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _require_optional_nonblank_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate an optional tuple of nonblank unique strings."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


class AssuranceFramework(RuntimeStrEnum):
    """Public framework families a local crosswalk may reference."""

    NIST_AI_RMF = "nist_ai_rmf"
    GAO_AI_ACCOUNTABILITY = "gao_ai_accountability"
    OMB_AI_GOVERNANCE = "omb_ai_governance"
    OMB_AI_ACQUISITION = "omb_ai_acquisition"
    ODNI_AI_GOVERNANCE = "odni_ai_governance"
    DOD_AI_T_AND_E = "dod_ai_t_and_e"
    DOD_RESPONSIBLE_AI = "dod_responsible_ai"

    def is_federal_or_national_security_facing(self) -> bool:
        """Return whether this framework family is federal or national-security facing."""

        return self in {
            AssuranceFramework.OMB_AI_GOVERNANCE,
            AssuranceFramework.OMB_AI_ACQUISITION,
            AssuranceFramework.ODNI_AI_GOVERNANCE,
            AssuranceFramework.DOD_AI_T_AND_E,
            AssuranceFramework.DOD_RESPONSIBLE_AI,
        }


class AssuranceArtifactType(RuntimeStrEnum):
    """Runtime artifact type that can support a control objective."""

    MISSION_NEED = "mission_need"
    REQUIREMENT = "requirement"
    HAZARD = "hazard"
    CONTROL = "control"
    SCENARIO = "scenario"
    EVIDENCE_BUNDLE = "evidence_bundle"
    SAFETY_GATE = "safety_gate"
    POLICY_RULE = "policy_rule"
    REGISTRY_RECORD = "registry_record"
    REVIEW_RECORD = "review_record"
    RUN_LEDGER = "run_ledger"
    REPORT = "report"

    def is_audit_artifact(self) -> bool:
        """Return whether this artifact normally supports audit or oversight review."""

        return self in {
            AssuranceArtifactType.EVIDENCE_BUNDLE,
            AssuranceArtifactType.SAFETY_GATE,
            AssuranceArtifactType.POLICY_RULE,
            AssuranceArtifactType.REGISTRY_RECORD,
            AssuranceArtifactType.REVIEW_RECORD,
            AssuranceArtifactType.RUN_LEDGER,
            AssuranceArtifactType.REPORT,
        }


class ControlCoverageStatus(RuntimeStrEnum):
    """Coverage posture for a control objective."""

    SATISFIED = "satisfied"
    PARTIAL = "partial"
    MISSING = "missing"
    OUT_OF_SCOPE = "out_of_scope"
    NOT_ASSESSED = "not_assessed"

    def supports_alignment_claim(self) -> bool:
        """Return whether this status can support a limited alignment claim."""

        return self in {ControlCoverageStatus.SATISFIED, ControlCoverageStatus.PARTIAL}

    def requires_follow_up(self) -> bool:
        """Return whether this status requires review or remediation."""

        return self in {
            ControlCoverageStatus.PARTIAL,
            ControlCoverageStatus.MISSING,
            ControlCoverageStatus.NOT_ASSESSED,
        }


class FrameworkCrosswalkFindingSeverity(RuntimeStrEnum):
    """Severity for framework crosswalk findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_alignment(self) -> bool:
        """Return whether this finding blocks a crosswalk alignment claim."""

        return self is FrameworkCrosswalkFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class ControlObjective:
    """One framework control objective represented in the local crosswalk."""

    control_id: str
    framework: AssuranceFramework
    title: str
    objective: str
    artifact_types: tuple[AssuranceArtifactType, ...]
    expected_evidence_kinds: tuple[str, ...]
    source_reference: str = "public-framework-concept"
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate control objectives as stable review artifacts."""

        _require_identifier(self.control_id, "control_id")
        _require_text(self.title, "control objective title")
        _require_text(self.objective, "control objective")
        if not self.artifact_types:
            raise ContractValueError(f"Control objective {self.control_id!r} needs artifacts.")
        if len(self.artifact_types) != len(set(self.artifact_types)):
            raise ContractValueError(
                f"Control objective {self.control_id!r} has duplicate artifact types."
            )
        _require_nonblank_unique_tuple(
            self.expected_evidence_kinds,
            f"control objective {self.control_id!r} expected_evidence_kinds",
        )
        _require_text(self.source_reference, "control objective source_reference")
        if self.notes and not self.notes.strip():
            raise ContractValueError(f"Control objective {self.control_id!r} notes are blank.")

    def expects_artifact_type(self, artifact_type: AssuranceArtifactType) -> bool:
        """Return whether this objective expects a supporting artifact type."""

        return artifact_type in self.artifact_types

    def requires_audit_artifact(self) -> bool:
        """Return whether the objective expects at least one audit-facing artifact."""

        return any(artifact_type.is_audit_artifact() for artifact_type in self.artifact_types)


@dataclass(frozen=True, slots=True)
class ControlMapping:
    """Mapping from one control objective to one local runtime artifact."""

    mapping_id: str
    control_id: str
    artifact_type: AssuranceArtifactType
    artifact_id: str
    coverage_status: ControlCoverageStatus
    rationale: str
    evidence_bundle_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate control-to-artifact mappings."""

        _require_identifier(self.mapping_id, "mapping_id")
        _require_identifier(self.control_id, "mapping control_id")
        _require_identifier(self.artifact_id, "mapping artifact_id")
        _require_text(self.rationale, "mapping rationale")
        _require_optional_nonblank_unique_tuple(
            self.evidence_bundle_ids,
            f"mapping {self.mapping_id!r} evidence_bundle_ids",
        )
        if (
            self.coverage_status is ControlCoverageStatus.SATISFIED
            and not self.evidence_bundle_ids
        ):
            raise ContractValueError(
                f"Satisfied mapping {self.mapping_id!r} must reference evidence bundles."
            )

    def supports_alignment_claim(self) -> bool:
        """Return whether this mapping can support a limited alignment claim."""

        return self.coverage_status.supports_alignment_claim()


@dataclass(frozen=True, slots=True)
class FrameworkCrosswalkFinding:
    """One validation finding for framework control mappings."""

    finding_id: str
    severity: FrameworkCrosswalkFindingSeverity
    message: str
    control_id: str | None = None
    mapping_id: str | None = None

    def __post_init__(self) -> None:
        """Validate crosswalk finding fields."""

        if not self.finding_id.strip():
            raise ContractValueError("Framework crosswalk finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Framework crosswalk finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Framework crosswalk finding {self.finding_id!r} needs a message."
            )
        if self.control_id is not None and not self.control_id.strip():
            raise ContractValueError(
                f"Framework crosswalk finding {self.finding_id!r} has a blank control ID."
            )
        if self.mapping_id is not None and not self.mapping_id.strip():
            raise ContractValueError(
                f"Framework crosswalk finding {self.finding_id!r} has a blank mapping ID."
            )


@dataclass(frozen=True, slots=True)
class ControlCoverage:
    """Coverage summary for one control objective."""

    control_id: str
    framework: AssuranceFramework
    status: ControlCoverageStatus
    mapping_ids: tuple[str, ...]
    finding_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate control coverage records."""

        _require_identifier(self.control_id, "coverage control_id")
        _require_optional_nonblank_unique_tuple(self.mapping_ids, "coverage mapping_ids")
        _require_optional_nonblank_unique_tuple(self.finding_ids, "coverage finding_ids")

    def supports_alignment_claim(self) -> bool:
        """Return whether this coverage can support a limited alignment claim."""

        return self.status.supports_alignment_claim()


@dataclass(frozen=True, slots=True)
class FrameworkCoverageReport:
    """Coverage report for a framework crosswalk."""

    coverage: tuple[ControlCoverage, ...]
    findings: tuple[FrameworkCrosswalkFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(1 for finding in self.findings if finding.severity.blocks_alignment())

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is FrameworkCrosswalkFindingSeverity.WARNING
        )

    def is_alignment_ready(self) -> bool:
        """Return whether the crosswalk has no blockers."""

        return self.blocker_count == 0

    def coverage_for_control(self, control_id: str) -> ControlCoverage | None:
        """Return coverage for one control objective if present."""

        return {coverage.control_id: coverage for coverage in self.coverage}.get(control_id)

    def summary(self) -> str:
        """Return a deterministic coverage summary."""

        satisfied = sum(
            1 for coverage in self.coverage if coverage.status is ControlCoverageStatus.SATISFIED
        )
        partial = sum(
            1
            for coverage in self.coverage
            if coverage.status is ControlCoverageStatus.PARTIAL
        )
        missing = sum(
            1
            for coverage in self.coverage
            if coverage.status
            in {ControlCoverageStatus.MISSING, ControlCoverageStatus.NOT_ASSESSED}
        )
        return (
            "framework-crosswalk: "
            f"{len(self.coverage)} control(s), {satisfied} satisfied, {partial} partial, "
            f"{missing} missing/not assessed, {self.blocker_count} blocker(s), "
            f"{self.warning_count} warning(s)"
        )


@dataclass(frozen=True, slots=True)
class FrameworkCrosswalk:
    """Local crosswalk from framework objectives to runtime artifacts."""

    objectives: tuple[ControlObjective, ...]
    mappings: tuple[ControlMapping, ...] = ()

    def __post_init__(self) -> None:
        """Reject duplicate objective and mapping IDs."""

        objective_ids = tuple(objective.control_id for objective in self.objectives)
        if len(objective_ids) != len(set(objective_ids)):
            raise ContractValueError("framework crosswalk objectives must have unique IDs.")
        mapping_ids = tuple(mapping.mapping_id for mapping in self.mappings)
        if len(mapping_ids) != len(set(mapping_ids)):
            raise ContractValueError("framework crosswalk mappings must have unique IDs.")

    def objectives_for_framework(
        self,
        framework: AssuranceFramework,
    ) -> tuple[ControlObjective, ...]:
        """Return objectives for a framework in crosswalk order."""

        return tuple(objective for objective in self.objectives if objective.framework is framework)

    def mappings_for_control(self, control_id: str) -> tuple[ControlMapping, ...]:
        """Return mappings for one control objective."""

        return tuple(mapping for mapping in self.mappings if mapping.control_id == control_id)

    def build_coverage_report(self) -> FrameworkCoverageReport:
        """Build a deterministic coverage report for the crosswalk."""

        objective_by_id = {objective.control_id: objective for objective in self.objectives}
        findings: list[FrameworkCrosswalkFinding] = []
        findings.extend(self._validate_mapping_references(objective_by_id))
        coverage = tuple(
            self._build_control_coverage(objective, findings)
            for objective in self.objectives
        )
        return FrameworkCoverageReport(coverage=coverage, findings=tuple(findings))

    def _validate_mapping_references(
        self,
        objective_by_id: dict[str, ControlObjective],
    ) -> tuple[FrameworkCrosswalkFinding, ...]:
        """Validate mapping references to objectives and expected artifact types."""

        findings: list[FrameworkCrosswalkFinding] = []
        for mapping in self.mappings:
            objective = objective_by_id.get(mapping.control_id)
            if objective is None:
                findings.append(
                    FrameworkCrosswalkFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-missing-control",
                        severity=FrameworkCrosswalkFindingSeverity.BLOCKER,
                        message="Control mapping references a missing control objective.",
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
                continue
            if not objective.expects_artifact_type(mapping.artifact_type):
                findings.append(
                    FrameworkCrosswalkFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-unexpected-artifact-type",
                        severity=FrameworkCrosswalkFindingSeverity.WARNING,
                        message=(
                            "Control mapping uses an artifact type not expected "
                            "by the objective."
                        ),
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
            if mapping.coverage_status.requires_follow_up():
                findings.append(
                    FrameworkCrosswalkFinding(
                        finding_id=f"mapping-{mapping.mapping_id}-{mapping.coverage_status.value}",
                        severity=FrameworkCrosswalkFindingSeverity.WARNING,
                        message=(
                            "Control mapping is not fully satisfied and needs review or "
                            "additional evidence."
                        ),
                        control_id=mapping.control_id,
                        mapping_id=mapping.mapping_id,
                    )
                )
        return tuple(findings)

    def _build_control_coverage(
        self,
        objective: ControlObjective,
        findings: list[FrameworkCrosswalkFinding],
    ) -> ControlCoverage:
        """Build coverage for one objective."""

        mappings = self.mappings_for_control(objective.control_id)
        if not mappings:
            finding = FrameworkCrosswalkFinding(
                finding_id=f"control-{objective.control_id}-not-assessed",
                severity=FrameworkCrosswalkFindingSeverity.WARNING,
                message="Control objective has no local artifact mappings yet.",
                control_id=objective.control_id,
            )
            findings.append(finding)
            return ControlCoverage(
                control_id=objective.control_id,
                framework=objective.framework,
                status=ControlCoverageStatus.NOT_ASSESSED,
                mapping_ids=(),
                finding_ids=(finding.finding_id,),
            )

        valid_mappings = tuple(
            mapping for mapping in mappings if mapping.control_id == objective.control_id
        )
        status = _aggregate_coverage_status(valid_mappings)
        finding_ids = tuple(
            finding.finding_id
            for finding in findings
            if finding.control_id == objective.control_id
        )
        return ControlCoverage(
            control_id=objective.control_id,
            framework=objective.framework,
            status=status,
            mapping_ids=tuple(mapping.mapping_id for mapping in valid_mappings),
            finding_ids=finding_ids,
        )


def _aggregate_coverage_status(mappings: tuple[ControlMapping, ...]) -> ControlCoverageStatus:
    """Aggregate coverage status for all mappings attached to one objective."""

    statuses = tuple(mapping.coverage_status for mapping in mappings)
    if any(status is ControlCoverageStatus.SATISFIED for status in statuses):
        return ControlCoverageStatus.SATISFIED
    if any(status is ControlCoverageStatus.PARTIAL for status in statuses):
        return ControlCoverageStatus.PARTIAL
    if any(status is ControlCoverageStatus.OUT_OF_SCOPE for status in statuses):
        return ControlCoverageStatus.OUT_OF_SCOPE
    if any(status is ControlCoverageStatus.MISSING for status in statuses):
        return ControlCoverageStatus.MISSING
    return ControlCoverageStatus.NOT_ASSESSED
