from __future__ import annotations

import json
from pathlib import Path

from ix_autonomy_assurance_case_runtime.cli import (
    load_assurance_case,
    load_mission_need,
    load_requirements,
    load_scenario_catalog,
)
from ix_autonomy_assurance_case_runtime.contracts import VerificationResult
from ix_autonomy_assurance_case_runtime.ledger import RunLedger
from ix_autonomy_assurance_case_runtime.reporting import AssuranceReportGenerator
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunInput, ScenarioRunner
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry
from ix_autonomy_assurance_case_runtime.traceability import build_traceability_graph
from ix_autonomy_assurance_case_runtime.verification import VerificationEngine

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SCHEMAS = ROOT / "schemas"


def test_schema_files_are_valid_json_objects() -> None:
    schema_paths = (
        SCHEMAS / "assurance-case.schema.json",
        SCHEMAS / "scenario-catalog.schema.json",
        SCHEMAS / "evidence-bundle.schema.json",
        SCHEMAS / "run-ledger.schema.json",
        SCHEMAS / "report.schema.json",
    )

    for schema_path in schema_paths:
        payload = json.loads(schema_path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict)
        assert payload["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert payload["type"] == "object"


def test_example_assurance_case_and_catalog_load_and_validate() -> None:
    assurance_case = load_assurance_case(EXAMPLES / "degraded-navigation-case.json")
    scenario_catalog = load_scenario_catalog(EXAMPLES / "degraded-navigation-catalog.json")

    case_report = assurance_case.validate_references()
    catalog_report = scenario_catalog.validate_references()

    assert case_report.is_valid is True
    assert case_report.errors == ()
    assert catalog_report.is_valid is True
    assert catalog_report.errors == ()


def test_end_to_end_runtime_verification_report_and_ledger() -> None:
    assurance_case = load_assurance_case(EXAMPLES / "degraded-navigation-case.json")
    scenario_catalog = load_scenario_catalog(EXAMPLES / "degraded-navigation-catalog.json")
    mission_need = load_mission_need(EXAMPLES / "mission-need.json")
    requirements = load_requirements(EXAMPLES / "requirements.json")

    traceability_graph = build_traceability_graph(
        mission_need=mission_need,
        requirements=requirements,
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
    )
    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-ACCEPTANCE-001",
            case_id=assurance_case.case_id,
            scenario_id="SCN-NAV-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.92,
                    "power_margin_pct": 76.0,
                    "comms_link_active": True,
                    "sensor_drift_sigma": 0.4,
                    "control_loop_latency_ms": 22.0,
                },
                source="acceptance-test-telemetry",
            ),
        ),
    )
    verification_summary = VerificationEngine(require_traceability=True).verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        traceability_graph=traceability_graph,
    )
    report = AssuranceReportGenerator().generate(
        report_id="RPT-ACCEPTANCE-001",
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
        verification_summary=verification_summary,
        traceability_graph=traceability_graph,
    )
    ledger = RunLedger(ledger_id="LEDGER-ACCEPTANCE-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=run_result.evidence_bundle,
        run_id=run_result.run_id,
    )

    assert run_result.verification_result is VerificationResult.PASS
    assert run_result.expected_behavior_satisfied is True
    assert verification_summary.overall_result is VerificationResult.PASS
    assert verification_summary.accepted() is True
    assert report.accepted() is True
    assert report.to_dict()["overall_result"] == "pass"
    assert "# Assurance Report: RPT-ACCEPTANCE-001" in report.to_markdown()
    assert ledger.validate_chain().is_valid is True
    assert ledger.latest_entry_hash() is not None


def test_example_failure_path_remains_reviewable_not_silent() -> None:
    assurance_case = load_assurance_case(EXAMPLES / "degraded-navigation-case.json")
    scenario_catalog = load_scenario_catalog(EXAMPLES / "degraded-navigation-catalog.json")

    run_result = ScenarioRunner().run(
        catalog=scenario_catalog,
        run_input=ScenarioRunInput(
            run_id="RUN-FAILURE-001",
            case_id=assurance_case.case_id,
            scenario_id="SCN-NAV-001",
            telemetry=RuntimeTelemetry(
                values={
                    "navigation_confidence": 0.99,
                    "power_margin_pct": 90.0,
                    "comms_link_active": True,
                    "sensor_drift_sigma": 0.1,
                    "control_loop_latency_ms": 18.0,
                },
                source="acceptance-test-clean-telemetry",
            ),
        ),
    )
    verification_summary = VerificationEngine(require_traceability=False).verify_run(
        assurance_case=assurance_case,
        scenario_catalog=scenario_catalog,
        run_result=run_result,
    )

    assert run_result.expected_behavior_satisfied is False
    assert run_result.verification_result is VerificationResult.FAIL
    assert verification_summary.overall_result is VerificationResult.FAIL
    assert "expected-safe-behavior" in verification_summary.failed_check_ids()
