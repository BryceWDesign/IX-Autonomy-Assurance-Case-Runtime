from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.framework_crosswalk import (
    AssuranceArtifactType,
    AssuranceFramework,
    ControlCoverageStatus,
    ControlMapping,
    ControlObjective,
    FrameworkCrosswalk,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk_evidence import (
    FrameworkEvidenceFinding,
    FrameworkEvidenceFindingSeverity,
    FrameworkEvidenceReference,
    FrameworkEvidenceValidator,
    collect_framework_evidence_references,
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
    bundle_id: str = "ev-framework-crosswalk-001",
    *,
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


def test_collect_framework_evidence_references_preserves_mapping_context() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))

    references = collect_framework_evidence_references(crosswalk)

    assert references == (
        FrameworkEvidenceReference(
            control_id="odni-ai-auditability",
            mapping_id="map-odni-auditability-registry",
            bundle_id="ev-framework-crosswalk-001",
            expected_evidence_kinds=("registry-readiness", "policy-readiness"),
            coverage_status=ControlCoverageStatus.SATISFIED,
        ),
    )


def test_framework_evidence_validator_accepts_complete_evidence_coverage() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))

    report = FrameworkEvidenceValidator(bundles=(_bundle(),)).validate(crosswalk)

    assert report.is_coverage_ready()
    assert report.referenced_bundle_count == 1
    assert report.provided_bundle_count == 1
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.summary() == (
        "framework-evidence: 1 referenced bundle(s), 1 provided bundle(s), "
        "0 blocker(s), 0 warning(s)"
    )


def test_framework_evidence_validator_blocks_missing_referenced_bundle() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))

    report = FrameworkEvidenceValidator(bundles=()).validate(crosswalk)

    assert not report.is_coverage_ready()
    assert report.blocker_count == 1
    assert report.findings_for_mapping("map-odni-auditability-registry")[0].finding_id == (
        "mapping-map-odni-auditability-registry-missing-evidence-ev-framework-crosswalk-001"
    )


def test_framework_evidence_validator_blocks_satisfied_mapping_missing_expected_kind() -> None:
    crosswalk = FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))

    report = FrameworkEvidenceValidator(
        bundles=(_bundle(kinds=("registry-readiness",)),)
    ).validate(crosswalk)

    assert report.blocker_count == 1
    assert report.findings_for_control("odni-ai-auditability")[0].finding_id == (
        "mapping-map-odni-auditability-registry-evidence-"
        "ev-framework-crosswalk-001-missing-kind-policy-readiness"
    )


def test_framework_evidence_validator_warns_partial_mapping_missing_expected_kind() -> None:
    crosswalk = FrameworkCrosswalk(
        objectives=(_objective(),),
        mappings=(
            _mapping(
                status=ControlCoverageStatus.PARTIAL,
                evidence_bundle_ids=("ev-framework-crosswalk-001",),
            ),
        ),
    )

    report = FrameworkEvidenceValidator(
        bundles=(_bundle(kinds=("registry-readiness",)),)
    ).validate(crosswalk)

    assert report.is_coverage_ready()
    assert report.warning_count == 1
    assert report.findings[0].severity is FrameworkEvidenceFindingSeverity.WARNING


def test_framework_evidence_validator_warns_partial_mapping_without_evidence() -> None:
    crosswalk = FrameworkCrosswalk(
        objectives=(_objective(),),
        mappings=(
            _mapping(
                status=ControlCoverageStatus.PARTIAL,
                evidence_bundle_ids=(),
            ),
        ),
    )

    report = FrameworkEvidenceValidator(bundles=()).validate(crosswalk)

    assert report.is_coverage_ready()
    assert report.warning_count == 1
    assert report.findings[0].finding_id == (
        "mapping-map-odni-auditability-registry-partial-without-evidence"
    )


def test_framework_evidence_validator_blocks_mapping_to_missing_control() -> None:
    crosswalk = FrameworkCrosswalk(
        objectives=(_objective(),),
        mappings=(_mapping(control_id="missing-control"),),
    )

    report = FrameworkEvidenceValidator(bundles=(_bundle(),)).validate(crosswalk)

    assert report.blocker_count == 1
    assert report.findings[0].finding_id == "mapping-map-odni-auditability-registry-missing-control"


def test_framework_evidence_validator_reports_integrity_errors_and_warnings() -> None:
    invalid_report = FrameworkEvidenceValidator(
        bundles=(_bundle(status=EvidenceStatus.INVALID),)
    ).validate(FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),)))

    assert invalid_report.blocker_count == 2
    assert "is marked invalid" in invalid_report.findings[-1].message

    unhashed_bundle = EvidenceBundle(
        bundle_id="ev-framework-crosswalk-001",
        case_id="case-framework-crosswalk-001",
        records=(
            EvidenceRecord(
                evidence_id="record-ev-framework-crosswalk-001-registry-readiness",
                kind="registry-readiness",
                source="unit-test",
                payload={"supports": "registry-readiness"},
                status=EvidenceStatus.ACCEPTED,
            ),
            EvidenceRecord(
                evidence_id="record-ev-framework-crosswalk-001-policy-readiness",
                kind="policy-readiness",
                source="unit-test",
                payload={"supports": "policy-readiness"},
                status=EvidenceStatus.ACCEPTED,
            ),
        ),
    )
    warning_report = FrameworkEvidenceValidator(bundles=(unhashed_bundle,)).validate(
        FrameworkCrosswalk(objectives=(_objective(),), mappings=(_mapping(),))
    )

    assert warning_report.is_coverage_ready()
    assert warning_report.warning_count == 3


def test_framework_evidence_validator_rejects_duplicate_provided_bundle_ids() -> None:
    with pytest.raises(ContractValueError, match="Duplicate evidence bundle ID"):
        FrameworkEvidenceValidator(bundles=(_bundle(), _bundle()))


def test_framework_evidence_reference_and_finding_validate_blank_fields() -> None:
    with pytest.raises(ContractValueError, match="bundle_id must not be blank"):
        FrameworkEvidenceReference(
            control_id="odni-ai-auditability",
            mapping_id="map-odni-auditability-registry",
            bundle_id="",
            expected_evidence_kinds=("registry-readiness",),
            coverage_status=ControlCoverageStatus.SATISFIED,
        )

    with pytest.raises(ContractValueError, match="blank mapping ID"):
        FrameworkEvidenceFinding(
            finding_id="bad-finding",
            severity=FrameworkEvidenceFindingSeverity.BLOCKER,
            message="Bad finding.",
            mapping_id="",
        )
