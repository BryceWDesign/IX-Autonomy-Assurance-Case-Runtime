from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord, EvidenceStatus
from ix_autonomy_assurance_case_runtime.framework_crosswalk import (
    AssuranceArtifactType,
    AssuranceFramework,
    ControlCoverageStatus,
    ControlMapping,
    ControlObjective,
    FrameworkCrosswalk,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk_readiness import (
    FrameworkCrosswalkLayerReadinessEvaluator,
    FrameworkCrosswalkReadinessDecision,
    FrameworkCrosswalkReadinessFinding,
    FrameworkCrosswalkReadinessFindingSeverity,
    FrameworkCrosswalkReadinessFindingSource,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)


def _objective(
    *,
    control_id: str = "odni-ai-auditability",
    framework: AssuranceFramework = AssuranceFramework.ODNI_AI_GOVERNANCE,
) -> ControlObjective:
    return ControlObjective(
        control_id=control_id,
        framework=framework,
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


def _mapping(
    *,
    mapping_id: str = "map-odni-auditability-registry",
    control_id: str = "odni-ai-auditability",
    status: ControlCoverageStatus = ControlCoverageStatus.SATISFIED,
    evidence_bundle_ids: tuple[str, ...] = ("ev-framework-crosswalk-001",),
) -> ControlMapping:
    return ControlMapping(
        mapping_id=mapping_id,
        control_id=control_id,
        artifact_type=AssuranceArtifactType.REGISTRY_RECORD,
        artifact_id="registry-layer",
        coverage_status=status,
        rationale="Registry readiness links systems, models, use cases, and deployments.",
        evidence_bundle_ids=evidence_bundle_ids,
    )


def _bundle(
    *,
    bundle_id: str = "ev-framework-crosswalk-001",
    kinds: tuple[str, ...] = ("registry-readiness", "policy-readiness"),
    status: EvidenceStatus = EvidenceStatus.ACCEPTED,
) -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id="case-framework-crosswalk-001",
        records=tuple(
            EvidenceRecord(
                evidence_id=f"record-{bundle_id}-{kind}",
                kind=kind,
                source="unit-test",
                payload={"supports": kind},
                status=status,
            )
            for kind in kinds
        ),
    ).with_computed_hashes()


def test_framework_crosswalk_readiness_completes_with_mapped_federal_evidence() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))
    report = FrameworkCrosswalkLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),)
    ).evaluate(crosswalk)

    assert report.decision is FrameworkCrosswalkReadinessDecision.COMPLETE
    assert report.is_complete()
    assert report.completed_capability_ids() == ("framework-crosswalks",)
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "framework-crosswalk-readiness: complete "
        "(0 blocker(s), 0 warning(s), capability=framework-crosswalks)"
    )


def test_framework_crosswalk_readiness_feeds_prototype_claim_gate() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))
    report = FrameworkCrosswalkLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),)
    ).evaluate(crosswalk)

    prototype_report = report.prototype_readiness_report(
        PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        existing_completed_capability_ids=("registry-layer", "policy-pack-engine"),
    )

    assert prototype_report.decision is PrototypeReadinessDecision.BLOCK
    assert prototype_report.achieved_percent == 54
    assert prototype_report.completed_capability_ids == (
        "registry-layer",
        "policy-pack-engine",
        "framework-crosswalks",
    )
    assert "signed-provenance" in prototype_report.remaining_capability_ids


def test_framework_crosswalk_readiness_blocks_empty_crosswalk() -> None:
    report = FrameworkCrosswalkLayerReadinessEvaluator(evidence_bundles=()).evaluate(
        FrameworkCrosswalk(objectives=(), mappings=())
    )

    assert report.decision is FrameworkCrosswalkReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "framework-crosswalk-no-objectives"
    assert report.findings[0].source is FrameworkCrosswalkReadinessFindingSource.READINESS


def test_framework_crosswalk_readiness_blocks_non_federal_only_crosswalk() -> None:
    crosswalk = FrameworkCrosswalk(
        objectives=(_objective(framework=AssuranceFramework.NIST_AI_RMF),),
        mappings=(_mapping(),),
    )

    report = FrameworkCrosswalkLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),)
    ).evaluate(crosswalk)

    assert report.decision is FrameworkCrosswalkReadinessDecision.BLOCKED
    assert any(
        finding.finding_id == "framework-crosswalk-no-federal-national-security-objective"
        for finding in report.findings
    )


def test_framework_crosswalk_readiness_blocks_missing_framework_evidence() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))

    report = FrameworkCrosswalkLayerReadinessEvaluator(evidence_bundles=()).evaluate(crosswalk)

    assert report.decision is FrameworkCrosswalkReadinessDecision.BLOCKED
    assert report.blocker_count == 1
    assert report.findings_for_mapping("map-odni-auditability-registry")[0].source is (
        FrameworkCrosswalkReadinessFindingSource.EVIDENCE
    )


def test_framework_crosswalk_readiness_is_limited_for_unmapped_objective() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=())

    report = FrameworkCrosswalkLayerReadinessEvaluator(evidence_bundles=()).evaluate(crosswalk)

    assert report.decision is FrameworkCrosswalkReadinessDecision.BLOCKED
    assert not report.is_complete()
    assert any(
        finding.finding_id == "framework-crosswalk-no-mappings"
        for finding in report.findings
    )


def test_framework_crosswalk_readiness_is_limited_for_partial_supported_mapping() -> None:
    crosswalk = FrameworkCrosswalk(
        objectives=(_objective(),),
        mappings=(
            _mapping(
                status=ControlCoverageStatus.PARTIAL,
                evidence_bundle_ids=("ev-framework-crosswalk-001",),
            ),
        ),
    )

    report = FrameworkCrosswalkLayerReadinessEvaluator(
        evidence_bundles=(_bundle(),)
    ).evaluate(crosswalk)

    assert report.decision is FrameworkCrosswalkReadinessDecision.LIMITED
    assert not report.is_complete()
    assert report.warning_count == 1
    assert report.findings_for_mapping("map-odni-auditability-registry")[0].source is (
        FrameworkCrosswalkReadinessFindingSource.CROSSWALK
    )


def test_framework_crosswalk_readiness_finding_validates_optional_ids() -> None:
    with pytest.raises(ContractValueError, match="needs a message"):
        FrameworkCrosswalkReadinessFinding(
            finding_id="bad-finding",
            severity=FrameworkCrosswalkReadinessFindingSeverity.BLOCKER,
            source=FrameworkCrosswalkReadinessFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank bundle ID"):
        FrameworkCrosswalkReadinessFinding(
            finding_id="bad-finding",
            severity=FrameworkCrosswalkReadinessFindingSeverity.BLOCKER,
            source=FrameworkCrosswalkReadinessFindingSource.EVIDENCE,
            message="Bad finding.",
            bundle_id="",
        )
