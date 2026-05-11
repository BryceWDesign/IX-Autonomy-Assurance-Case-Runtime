from __future__ import annotations

import json
from pathlib import Path

import pytest

from ix_autonomy_assurance_case_runtime.cli import main
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.ledger import RunLedger


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def build_case_payload() -> dict[str, object]:
    return {
        "case_id": "CASE-001",
        "title": "Navigation Assurance Case",
        "system_name": "Reference Autonomy Stack",
        "mission_context": "Autonomous route execution under degraded navigation.",
        "status": "ready_for_review",
        "claims": [
            {
                "claim_id": "CLM-001",
                "statement": "Autonomy remains bounded during degraded navigation.",
                "argument": "Runtime gating prevents unsafe nominal behavior.",
                "evidence_ids": ["EV-001"],
                "verification_criterion_ids": ["VC-001"],
                "verification_result": "pass",
            }
        ],
        "hazards": [
            {
                "hazard_id": "HZ-001",
                "title": "Navigation confidence loss",
                "description": "Autonomy may continue after navigation confidence degrades.",
                "severity": "critical",
                "control_ids": ["CTRL-001"],
                "mitigation_ids": ["MIT-001"],
                "evidence_ids": ["EV-001"],
            }
        ],
        "controls": [
            {
                "control_id": "CTRL-001",
                "name": "Navigation confidence gate",
                "description": "Blocks nominal route execution under degraded navigation.",
                "mitigates_hazard_ids": ["HZ-001"],
                "evidence_ids": ["EV-001"],
            }
        ],
        "mitigations": [
            {
                "mitigation_id": "MIT-001",
                "hazard_id": "HZ-001",
                "control_id": "CTRL-001",
                "description": "Force safe-hold and require review.",
                "evidence_ids": ["EV-001"],
            }
        ],
        "evidence": [
            {
                "evidence_id": "EV-001",
                "description": "Scenario evidence showing safe-hold.",
                "source": "run-bundles/scn-001.json",
                "status": "accepted",
                "supports": ["CLM-001", "VC-001", "CTRL-001"],
                "content_hash": "sha256:0123456789abcdef",
            }
        ],
        "verification_criteria": [
            {
                "criterion_id": "VC-001",
                "statement": "Safe-hold occurs before mission boundary violation.",
                "verification_method": "fault-injection scenario",
                "expected_result": "safe_hold",
                "result": "pass",
                "evidence_ids": ["EV-001"],
            }
        ],
    }


def build_catalog_payload() -> dict[str, object]:
    return {
        "operational_contexts": [
            {
                "context_id": "CTX-001",
                "name": "Degraded navigation route execution",
                "environment": "controlled autonomy test range",
                "mission_phase": "route execution",
                "description": "Autonomy is evaluated under degraded navigation telemetry.",
            }
        ],
        "autonomy_functions": [
            {
                "function_id": "AF-001",
                "name": "Autonomous route manager",
                "description": "Manages bounded route execution.",
                "input_signals": ["navigation_confidence", "power_margin_pct"],
                "output_actions": ["continue_route", "enter_safe_hold"],
            }
        ],
        "operating_conditions": [
            {
                "condition_id": "COND-001",
                "name": "Navigation confidence available",
                "description": "Navigation confidence telemetry is evaluated.",
                "telemetry_key": "navigation_confidence",
                "expected_range": "0.0..1.0",
            }
        ],
        "stressors": [
            {
                "stressor_id": "STR-001",
                "name": "Navigation confidence degradation",
                "description": "Navigation confidence drops below expectations.",
                "severity": "critical",
                "affected_capabilities": ["navigation", "route_execution"],
                "trigger_condition": "navigation_confidence < 0.70",
            }
        ],
        "expected_behaviors": [
            {
                "behavior_id": "BEH-001",
                "description": "Expected safe behavior under degraded navigation.",
                "required_decision": "safe_hold",
                "required_authority_state": "emergency_safe_hold",
                "rationale": "Unsafe navigation confidence requires safe-hold.",
            }
        ],
        "acceptance_criteria": [
            {
                "criterion_id": "AC-001",
                "statement": "Runtime decision satisfies expected safe behavior.",
                "measurement": "runtime_decision",
                "expected_result": "safe_hold",
            }
        ],
        "mission_threads": [
            {
                "mission_thread_id": "MT-001",
                "name": "Navigation assurance mission thread",
                "objective": "Keep autonomy bounded during degraded navigation.",
                "operational_context_id": "CTX-001",
                "autonomy_function_ids": ["AF-001"],
                "scenario_ids": ["SCN-001"],
                "requirement_ids": ["REQ-001"],
                "hazard_ids": ["HZ-001"],
            }
        ],
        "scenarios": [
            {
                "scenario_id": "SCN-001",
                "mission_thread_id": "MT-001",
                "title": "Navigation degradation scenario",
                "description": "Evaluate runtime response to degraded navigation confidence.",
                "operational_context_id": "CTX-001",
                "autonomy_function_id": "AF-001",
                "operating_condition_ids": ["COND-001"],
                "stressor_ids": ["STR-001"],
                "expected_behavior_id": "BEH-001",
                "acceptance_criterion_ids": ["AC-001"],
                "hazard_ids": ["HZ-001"],
                "evidence_ids": ["EV-001"],
            }
        ],
    }


def test_cli_validate_case_outputs_valid_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_path = tmp_path / "case.json"
    write_json(case_path, build_case_payload())

    exit_code = main(["validate-case", "--case", str(case_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["case_id"] == "CASE-001"
    assert payload["valid"] is True
    assert payload["errors"] == []


def test_cli_run_scenario_outputs_hashed_evidence_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    catalog_path = tmp_path / "catalog.json"
    telemetry_path = tmp_path / "telemetry.json"
    write_json(catalog_path, build_catalog_payload())
    write_json(
        telemetry_path,
        {
            "source": "simulated-runtime",
            "values": {
                "navigation_confidence": 0.62,
                "power_margin_pct": 80.0,
            },
        },
    )

    exit_code = main(
        [
            "run-scenario",
            "--catalog",
            str(catalog_path),
            "--telemetry",
            str(telemetry_path),
            "--case-id",
            "CASE-001",
            "--scenario-id",
            "SCN-001",
            "--run-id",
            "RUN-001",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["final_decision"] == "safe_hold"
    assert payload["verification_result"] == "pass"
    assert payload["evidence_bundle"]["bundle_hash"].startswith("sha256:")


def test_cli_verify_bundle_accepts_valid_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = EvidenceRecord(
        evidence_id="EV-001",
        kind="scenario-run",
        source="scenario:SCN-001",
        payload={"verification_result": "pass"},
        status="accepted",
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-001",
        case_id="CASE-001",
        scenario_id="SCN-001",
        records=(record,),
    ).with_computed_hashes()
    bundle_path = tmp_path / "bundle.json"
    write_json(bundle_path, bundle.to_dict())

    exit_code = main(["verify-bundle", "--bundle", str(bundle_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["bundle_id"] == "BND-001"


def test_cli_validate_ledger_accepts_valid_hash_chain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    record = EvidenceRecord(
        evidence_id="EV-001",
        kind="scenario-run",
        source="scenario:SCN-001",
        payload={"verification_result": "pass"},
        status="accepted",
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-001",
        case_id="CASE-001",
        scenario_id="SCN-001",
        records=(record,),
    ).with_computed_hashes()
    ledger = RunLedger(ledger_id="LEDGER-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=bundle,
        run_id="RUN-001",
    )
    ledger_path = tmp_path / "ledger.json"
    write_json(ledger_path, ledger.to_dict())

    exit_code = main(["validate-ledger", "--ledger", str(ledger_path)])

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["entry_count"] == 1


def test_cli_export_report_markdown(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report_path = tmp_path / "report.json"
    write_json(
        report_path,
        {
            "accepted": True,
            "case_id": "CASE-001",
            "generated_by": "ix-assurance-report-generator",
            "overall_result": "pass",
            "report_id": "RPT-001",
            "run_id": "RUN-001",
            "scenario_id": "SCN-001",
            "sections": [
                {
                    "title": "Executive Summary",
                    "severity": "info",
                    "lines": ["Verification passed."],
                }
            ],
        },
    )

    exit_code = main(["export-report", "--report", str(report_path), "--format", "markdown"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "# Assurance Report: RPT-001" in captured.out
    assert "## Executive Summary" in captured.out


def test_cli_audit_traceability_reports_connected_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_path = tmp_path / "case.json"
    catalog_path = tmp_path / "catalog.json"
    mission_need_path = tmp_path / "mission-need.json"
    requirements_path = tmp_path / "requirements.json"

    write_json(case_path, build_case_payload())
    write_json(catalog_path, build_catalog_payload())
    write_json(
        mission_need_path,
        {
            "need_id": "MN-001",
            "statement": "Autonomy remains bounded under degraded navigation.",
            "operational_driver": "trusted autonomy T&E",
        },
    )
    write_json(
        requirements_path,
        [
            {
                "requirement_id": "REQ-001",
                "statement": "The autonomy shall enter safe-hold under degraded navigation.",
                "verification_method": "fault-injection scenario",
                "source": "system safety requirement",
            }
        ],
    )

    exit_code = main(
        [
            "audit-traceability",
            "--case",
            str(case_path),
            "--catalog",
            str(catalog_path),
            "--mission-need",
            str(mission_need_path),
            "--requirements",
            str(requirements_path),
            "--scenario-id",
            "SCN-001",
            "--claim-id",
            "CLM-001",
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["valid"] is True
    assert payload["connected_path"] is True
    assert payload["node_count"] > 0
    assert payload["edge_count"] > 0


def test_cli_returns_error_code_for_invalid_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_path = tmp_path / "broken-case.json"
    payload = build_case_payload()
    payload["claims"] = []
    write_json(case_path, payload)

    exit_code = main(["validate-case", "--case", str(case_path)])

    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert exit_code == 1
    assert result["valid"] is False
    assert "Assurance case must contain at least one claim." in result["errors"]


def test_cli_returns_error_code_for_malformed_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_path = tmp_path / "bad.json"
    bad_path.write_text("{not-valid-json", encoding="utf-8")

    exit_code = main(["validate-case", "--case", str(bad_path)])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "error:" in captured.err
