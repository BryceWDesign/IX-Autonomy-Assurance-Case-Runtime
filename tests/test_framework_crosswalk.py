from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.framework_crosswalk import (
    AssuranceArtifactType,
    AssuranceFramework,
    ControlCoverageStatus,
    ControlMapping,
    ControlObjective,
    FrameworkCrosswalk,
    FrameworkCrosswalkFinding,
    FrameworkCrosswalkFindingSeverity,
)


def _objective(control_id: str = "odni-ai-auditability") -> ControlObjective:
    return ControlObjective(
        control_id=control_id,
        framework=AssuranceFramework.ODNI_AI_GOVERNANCE,
        title="AI auditability and provenance",
        objective=(
            "Map registry, policy, evidence, and run-ledger artifacts to a reviewable "
            "auditability objective."
        ),
        artifact_types=(
            AssuranceArtifactType.REGISTRY_RECORD,
            AssuranceArtifactType.POLICY_RULE,
            AssuranceArtifactType.EVIDENCE_BUNDLE,
            AssuranceArtifactType.RUN_LEDGER,
        ),
        expected_evidence_kinds=("registry-readiness", "policy-readiness"),
        source_reference="public ODNI AI governance concept",
    )


def _satisfied_mapping() -> ControlMapping:
    return ControlMapping(
        mapping_id="map-odni-auditability-registry",
        control_id="odni-ai-auditability",
        artifact_type=AssuranceArtifactType.REGISTRY_RECORD,
        artifact_id="registry-layer",
        coverage_status=ControlCoverageStatus.SATISFIED,
        rationale="Registry readiness links systems, models, use cases, and deployments.",
        evidence_bundle_ids=("ev-registry-readiness-001",),
    )


def test_control_objective_preserves_framework_artifacts_and_evidence_expectations() -> None:
    objective = _objective()

    assert objective.framework is AssuranceFramework.ODNI_AI_GOVERNANCE
    assert AssuranceFramework.ODNI_AI_GOVERNANCE.is_federal_or_national_security_facing()
    assert objective.expects_artifact_type(AssuranceArtifactType.REGISTRY_RECORD)
    assert objective.requires_audit_artifact()
    assert AssuranceArtifactType.RUN_LEDGER.is_audit_artifact()


def test_control_objective_rejects_blank_duplicate_or_missing_artifact_data() -> None:
    with pytest.raises(ContractValueError, match="needs artifacts"):
        ControlObjective(
            control_id="bad-control",
            framework=AssuranceFramework.NIST_AI_RMF,
            title="Bad control",
            objective="Missing artifacts.",
            artifact_types=(),
            expected_evidence_kinds=("evidence",),
        )

    with pytest.raises(ContractValueError, match="duplicate artifact types"):
        ControlObjective(
            control_id="bad-control",
            framework=AssuranceFramework.NIST_AI_RMF,
            title="Bad control",
            objective="Duplicate artifacts.",
            artifact_types=(
                AssuranceArtifactType.REPORT,
                AssuranceArtifactType.REPORT,
            ),
            expected_evidence_kinds=("evidence",),
        )

    with pytest.raises(ContractValueError, match="duplicate values"):
        ControlObjective(
            control_id="bad-control",
            framework=AssuranceFramework.NIST_AI_RMF,
            title="Bad control",
            objective="Duplicate evidence kinds.",
            artifact_types=(AssuranceArtifactType.REPORT,),
            expected_evidence_kinds=("evidence", "evidence"),
        )


def test_control_mapping_requires_evidence_for_satisfied_coverage() -> None:
    mapping = _satisfied_mapping()

    assert mapping.supports_alignment_claim()
    assert mapping.coverage_status is ControlCoverageStatus.SATISFIED

    with pytest.raises(ContractValueError, match="must reference evidence bundles"):
        ControlMapping(
            mapping_id="bad-satisfied-mapping",
            control_id="odni-ai-auditability",
            artifact_type=AssuranceArtifactType.REGISTRY_RECORD,
            artifact_id="registry-layer",
            coverage_status=ControlCoverageStatus.SATISFIED,
            rationale="Claims satisfaction without evidence.",
        )


def test_framework_crosswalk_reports_satisfied_control_mapping() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_satisfied_mapping(),))

    report = crosswalk.build_coverage_report()
    coverage = report.coverage_for_control("odni-ai-auditability")

    assert report.is_alignment_ready()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert coverage is not None
    assert coverage.status is ControlCoverageStatus.SATISFIED
    assert coverage.supports_alignment_claim()
    assert report.summary() == (
        "framework-crosswalk: 1 control(s), 1 satisfied, 0 partial, "
        "0 missing/not assessed, 0 blocker(s), 0 warning(s)"
    )


def test_framework_crosswalk_warns_for_unmapped_objective() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=())

    report = crosswalk.build_coverage_report()
    coverage = report.coverage_for_control("odni-ai-auditability")

    assert report.is_alignment_ready()
    assert report.warning_count == 1
    assert coverage is not None
    assert coverage.status is ControlCoverageStatus.NOT_ASSESSED
    assert coverage.finding_ids == ("control-odni-ai-auditability-not-assessed",)


def test_framework_crosswalk_blocks_mapping_to_missing_objective() -> None:
    mapping = ControlMapping(
        mapping_id="map-missing-control",
        control_id="missing-control",
        artifact_type=AssuranceArtifactType.REPORT,
        artifact_id="report-001",
        coverage_status=ControlCoverageStatus.PARTIAL,
        rationale="This mapping references a missing control objective.",
    )
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(mapping,))

    report = crosswalk.build_coverage_report()

    assert not report.is_alignment_ready()
    assert report.blocker_count == 1
    assert report.warning_count == 1
    assert {finding.finding_id for finding in report.findings} >= {
        "mapping-map-missing-control-missing-control",
        "control-odni-ai-auditability-not-assessed",
    }


def test_framework_crosswalk_warns_for_unexpected_artifact_type_and_partial_mapping() -> None:
    mapping = ControlMapping(
        mapping_id="map-odni-auditability-scenario",
        control_id="odni-ai-auditability",
        artifact_type=AssuranceArtifactType.SCENARIO,
        artifact_id="scenario-degraded-nav",
        coverage_status=ControlCoverageStatus.PARTIAL,
        rationale="Scenario coverage is relevant but not an expected direct artifact.",
    )
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(mapping,))

    report = crosswalk.build_coverage_report()
    coverage = report.coverage_for_control("odni-ai-auditability")

    assert report.is_alignment_ready()
    assert report.warning_count == 2
    assert coverage is not None
    assert coverage.status is ControlCoverageStatus.PARTIAL
    assert ControlCoverageStatus.PARTIAL.requires_follow_up()


def test_framework_crosswalk_rejects_duplicate_objectives_and_mappings() -> None:
    with pytest.raises(ContractValueError, match="objectives must have unique IDs"):
        FrameworkCrosswalk(objectives=(_objective(), _objective()))

    with pytest.raises(ContractValueError, match="mappings must have unique IDs"):
        FrameworkCrosswalk(
            objectives=(_objective(),),
            mappings=(_satisfied_mapping(), _satisfied_mapping()),
        )


def test_framework_crosswalk_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        FrameworkCrosswalkFinding(
            finding_id="bad-finding",
            severity=FrameworkCrosswalkFindingSeverity.WARNING,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank mapping ID"):
        FrameworkCrosswalkFinding(
            finding_id="bad-finding",
            severity=FrameworkCrosswalkFindingSeverity.WARNING,
            message="Bad finding.",
            mapping_id="",
        )
