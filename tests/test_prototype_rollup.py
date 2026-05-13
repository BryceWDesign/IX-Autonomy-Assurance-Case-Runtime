from __future__ import annotations

from dataclasses import dataclass

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.export_package_readiness import (
    EXPORT_PACKAGE_CAPABILITY_ID,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk_readiness import (
    FRAMEWORK_CROSSWALK_CAPABILITY_ID,
)
from ix_autonomy_assurance_case_runtime.monitoring_readiness import MONITORING_CAPABILITY_ID
from ix_autonomy_assurance_case_runtime.policy_readiness import POLICY_CAPABILITY_ID
from ix_autonomy_assurance_case_runtime.prototype_rollup import (
    CapabilityLayerRollupEntry,
    PrototypeCapabilityRollupEvaluator,
    PrototypeRollupFinding,
    PrototypeRollupFindingSeverity,
    PrototypeRollupFindingSource,
)
from ix_autonomy_assurance_case_runtime.provenance_readiness import PROVENANCE_CAPABILITY_ID
from ix_autonomy_assurance_case_runtime.registry_readiness import REGISTRY_CAPABILITY_ID
from ix_autonomy_assurance_case_runtime.review_workflow_readiness import (
    REVIEW_WORKFLOW_CAPABILITY_ID,
)
from ix_autonomy_assurance_case_runtime.scenario_campaign_readiness import (
    SCENARIO_CAMPAIGN_CAPABILITY_ID,
)
from ix_autonomy_assurance_case_runtime.telemetry_readiness import TELEMETRY_CAPABILITY_ID


@dataclass(frozen=True, slots=True)
class FakeCapabilityReport:
    capability_id: str
    complete: bool = True
    warning_count: int = 0
    blocker_count: int = 0
    emitted_capability_ids: tuple[str, ...] | None = None

    def is_complete(self) -> bool:
        return self.complete

    def completed_capability_ids(self) -> tuple[str, ...]:
        if not self.complete:
            return ()
        if self.emitted_capability_ids is not None:
            return self.emitted_capability_ids
        return (self.capability_id,)

    def summary(self) -> str:
        return f"fake-capability-report: {self.capability_id}"


def _serious_target_reports() -> tuple[FakeCapabilityReport, ...]:
    return (
        FakeCapabilityReport(REGISTRY_CAPABILITY_ID),
        FakeCapabilityReport(POLICY_CAPABILITY_ID),
        FakeCapabilityReport(FRAMEWORK_CROSSWALK_CAPABILITY_ID),
        FakeCapabilityReport(PROVENANCE_CAPABILITY_ID),
        FakeCapabilityReport(TELEMETRY_CAPABILITY_ID),
        FakeCapabilityReport(SCENARIO_CAMPAIGN_CAPABILITY_ID),
        FakeCapabilityReport(MONITORING_CAPABILITY_ID),
        FakeCapabilityReport(REVIEW_WORKFLOW_CAPABILITY_ID),
        FakeCapabilityReport(EXPORT_PACKAGE_CAPABILITY_ID),
    )


def test_prototype_rollup_reaches_serious_prototype_target_with_completed_layers() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(_serious_target_reports())

    assert report.target_percent_met()
    assert report.is_rollup_clean()
    assert report.achieved_percent >= 80
    assert report.blocker_count == 0
    assert report.duplicate_capability_ids == ()
    assert EXPORT_PACKAGE_CAPABILITY_ID in report.completed_capability_ids()
    assert report.summary().startswith("prototype-rollup:")


def test_prototype_rollup_blocks_when_no_layer_reports_are_supplied() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(())

    assert not report.target_percent_met()
    assert not report.is_rollup_clean()
    assert report.blocker_count == 2
    assert any(
        finding.finding_id == "prototype-rollup-no-layer-reports"
        for finding in report.findings
    )
    assert any(
        finding.finding_id == "prototype-rollup-target-percent-not-met"
        for finding in report.findings
    )


def test_prototype_rollup_blocks_incomplete_layer_report() -> None:
    reports = _serious_target_reports()[:-1] + (
        FakeCapabilityReport(EXPORT_PACKAGE_CAPABILITY_ID, complete=False),
    )

    report = PrototypeCapabilityRollupEvaluator().evaluate(reports)

    assert not report.is_rollup_clean()
    assert report.findings_for_capability(EXPORT_PACKAGE_CAPABILITY_ID)
    assert any(
        finding.finding_id.endswith("-not-complete")
        for finding in report.findings_for_capability(EXPORT_PACKAGE_CAPABILITY_ID)
    )


def test_prototype_rollup_blocks_duplicate_completed_capability_ids() -> None:
    duplicate_reports = _serious_target_reports() + (
        FakeCapabilityReport(
            capability_id="duplicate-export-layer",
            emitted_capability_ids=(EXPORT_PACKAGE_CAPABILITY_ID,),
        ),
    )

    report = PrototypeCapabilityRollupEvaluator().evaluate(duplicate_reports)

    assert not report.is_rollup_clean()
    assert report.duplicate_capability_ids == (EXPORT_PACKAGE_CAPABILITY_ID,)
    assert any(
        finding.finding_id
        == f"prototype-rollup-duplicate-completed-{EXPORT_PACKAGE_CAPABILITY_ID}"
        for finding in report.findings_for_capability(EXPORT_PACKAGE_CAPABILITY_ID)
    )


def test_prototype_rollup_warns_for_unexpected_completed_capability_id() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(
        _serious_target_reports()
        + (FakeCapabilityReport("experimental-extra-capability"),)
    )

    assert report.warning_count >= 1
    assert "experimental-extra-capability" in report.unexpected_completed_capability_ids
    assert any(
        finding.severity is PrototypeRollupFindingSeverity.WARNING
        for finding in report.findings_for_capability("experimental-extra-capability")
    )


def test_prototype_rollup_blocks_complete_layer_that_emits_wrong_capability_id() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(
        (
            FakeCapabilityReport(
                capability_id=EXPORT_PACKAGE_CAPABILITY_ID,
                emitted_capability_ids=("some-other-capability",),
            ),
        ),
        expected_capability_ids=(EXPORT_PACKAGE_CAPABILITY_ID,),
    )

    assert not report.is_rollup_clean()
    assert any(
        finding.finding_id.endswith("-missing-own-capability-id")
        for finding in report.findings_for_capability(EXPORT_PACKAGE_CAPABILITY_ID)
    )


def test_prototype_rollup_entry_validates_counts_and_ids() -> None:
    with pytest.raises(ContractValueError, match="blocker_count"):
        CapabilityLayerRollupEntry(
            layer_id="layer-export",
            capability_id=EXPORT_PACKAGE_CAPABILITY_ID,
            is_complete=True,
            completed_capability_ids=(EXPORT_PACKAGE_CAPABILITY_ID,),
            layer_summary="export layer",
            blocker_count=-1,
        )

    with pytest.raises(ContractValueError, match="duplicate identifiers"):
        CapabilityLayerRollupEntry(
            layer_id="layer-export",
            capability_id=EXPORT_PACKAGE_CAPABILITY_ID,
            is_complete=True,
            completed_capability_ids=(
                EXPORT_PACKAGE_CAPABILITY_ID,
                EXPORT_PACKAGE_CAPABILITY_ID,
            ),
            layer_summary="export layer",
        )


def test_prototype_rollup_finding_validates_optional_identifiers() -> None:
    with pytest.raises(ContractValueError, match="message"):
        PrototypeRollupFinding(
            finding_id="finding-rollup-001",
            severity=PrototypeRollupFindingSeverity.BLOCKER,
            source=PrototypeRollupFindingSource.READINESS,
            message="",
        )

    with pytest.raises(ContractValueError, match="capability_id must not be blank"):
        PrototypeRollupFinding(
            finding_id="finding-rollup-001",
            severity=PrototypeRollupFindingSeverity.BLOCKER,
            source=PrototypeRollupFindingSource.CAPABILITY,
            message="Bad capability.",
            capability_id="",
        )
