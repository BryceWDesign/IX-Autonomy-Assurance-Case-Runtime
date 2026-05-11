"""Command-line interface for IX-Autonomy-Assurance-Case-Runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, cast

from ix_autonomy_assurance_case_runtime.assurance_case import (
    Assumption,
    AssuranceCase,
    AssuranceClaim,
    Control,
    EvidenceLink,
    Hazard,
    Mitigation,
    VerificationCriterion,
)
from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    AutonomyDecisionType,
    EvidenceStatus,
    HazardSeverity,
    RuntimeAuthorityState,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.degradation import (
    DegradationEngine,
    build_default_degradation_rules,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord, JSONValue
from ix_autonomy_assurance_case_runtime.ledger import LedgerEntry, LedgerRecordType, RunLedger
from ix_autonomy_assurance_case_runtime.reporting import AssuranceReportGenerator
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunInput, ScenarioRunner
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry, TelemetryValue
from ix_autonomy_assurance_case_runtime.scenarios import (
    AcceptanceCriterion,
    AutonomyFunction,
    ExpectedSafeBehavior,
    MissionThread,
    OperatingCondition,
    OperationalContext,
    Scenario,
    ScenarioCatalog,
    Stressor,
)
from ix_autonomy_assurance_case_runtime.traceability import (
    MissionNeed,
    Requirement,
    build_traceability_graph,
)
from ix_autonomy_assurance_case_runtime.verification import VerificationEngine

CommandHandler = Callable[[argparse.Namespace], int]


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ix-assurance command-line interface."""

    parser = build_parser()
    args = parser.parse_args(argv)
    command = getattr(args, "command", None)

    if not callable(command):
        parser.error("No command selected.")

    try:
        return cast(CommandHandler, command)(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="ix-assurance",
        description="Trusted Autonomy T&E assurance-case runtime CLI.",
    )
    subparsers = parser.add_subparsers(dest="command_name")

    validate_case = subparsers.add_parser(
        "validate-case",
        help="Validate an assurance-case JSON artifact.",
    )
    validate_case.add_argument("--case", required=True, help="Path to assurance-case JSON.")
    validate_case.set_defaults(command=_cmd_validate_case)

    verify_bundle = subparsers.add_parser(
        "verify-bundle",
        help="Verify an evidence-bundle JSON artifact.",
    )
    verify_bundle.add_argument("--bundle", required=True, help="Path to evidence-bundle JSON.")
    verify_bundle.set_defaults(command=_cmd_verify_bundle)

    validate_ledger = subparsers.add_parser(
        "validate-ledger",
        help="Validate a run-ledger JSON artifact.",
    )
    validate_ledger.add_argument("--ledger", required=True, help="Path to run-ledger JSON.")
    validate_ledger.add_argument(
        "--require-unique-run-ids",
        action="store_true",
        help="Fail when repeated run IDs appear in ledger entries.",
    )
    validate_ledger.set_defaults(command=_cmd_validate_ledger)

    run_scenario = subparsers.add_parser(
        "run-scenario",
        help="Run one scenario using catalog and telemetry JSON artifacts.",
    )
    run_scenario.add_argument("--catalog", required=True, help="Path to scenario-catalog JSON.")
    run_scenario.add_argument("--telemetry", required=True, help="Path to telemetry JSON.")
    run_scenario.add_argument("--case-id", required=True, help="Assurance case identifier.")
    run_scenario.add_argument("--scenario-id", required=True, help="Scenario identifier.")
    run_scenario.add_argument("--run-id", required=True, help="Runtime run identifier.")
    run_scenario.add_argument(
        "--default-degradation",
        action="store_true",
        help="Enable built-in degradation checks for common autonomy telemetry.",
    )
    run_scenario.set_defaults(command=_cmd_run_scenario)

    export_report = subparsers.add_parser(
        "export-report",
        help="Export a report JSON payload as JSON or Markdown.",
    )
    export_report.add_argument("--report", required=True, help="Path to report JSON.")
    export_report.add_argument(
        "--format",
        choices=("json", "markdown"),
        default="markdown",
        help="Output format.",
    )
    export_report.set_defaults(command=_cmd_export_report)

    audit_traceability = subparsers.add_parser(
        "audit-traceability",
        help="Build and validate traceability from case/catalog/mission artifacts.",
    )
    audit_traceability.add_argument("--case", required=True, help="Path to assurance-case JSON.")
    audit_traceability.add_argument(
        "--catalog", required=True, help="Path to scenario-catalog JSON."
    )
    audit_traceability.add_argument("--mission-need", required=True, help="Mission-need JSON.")
    audit_traceability.add_argument("--requirements", required=True, help="Requirements JSON list.")
    audit_traceability.add_argument("--scenario-id", help="Optional scenario path source.")
    audit_traceability.add_argument("--claim-id", help="Optional assurance claim path target.")
    audit_traceability.set_defaults(command=_cmd_audit_traceability)

    return parser


def _cmd_validate_case(args: argparse.Namespace) -> int:
    assurance_case = load_assurance_case(_arg_path(args, "case"))
    report = assurance_case.validate_references()
    _print_json(
        {
            "case_id": assurance_case.case_id,
            "errors": list(report.errors),
            "valid": report.is_valid,
            "warnings": list(report.warnings),
        }
    )
    return 0 if report.is_valid else 1


def _cmd_verify_bundle(args: argparse.Namespace) -> int:
    bundle = load_evidence_bundle(_arg_path(args, "bundle"))
    report = bundle.validate_integrity()
    _print_json(
        {
            "bundle_hash": bundle.bundle_hash,
            "bundle_id": bundle.bundle_id,
            "errors": list(report.errors),
            "record_count": len(bundle.records),
            "valid": report.is_valid,
            "warnings": list(report.warnings),
        }
    )
    return 0 if report.is_valid else 1


def _cmd_validate_ledger(args: argparse.Namespace) -> int:
    ledger = load_run_ledger(_arg_path(args, "ledger"))
    report = ledger.validate_chain(
        require_unique_run_ids=bool(args.require_unique_run_ids),
    )
    _print_json(
        {
            "entry_count": len(ledger.entries),
            "errors": list(report.errors),
            "latest_entry_hash": ledger.latest_entry_hash(),
            "ledger_id": ledger.ledger_id,
            "valid": report.is_valid,
            "warnings": list(report.warnings),
        }
    )
    return 0 if report.is_valid else 1


def _cmd_run_scenario(args: argparse.Namespace) -> int:
    catalog = load_scenario_catalog(_arg_path(args, "catalog"))
    telemetry = load_telemetry(_arg_path(args, "telemetry"))
    degradation_engine = DegradationEngine(
        rules=build_default_degradation_rules() if bool(args.default_degradation) else (),
    )
    runner = ScenarioRunner(degradation_engine=degradation_engine)
    result = runner.run(
        catalog=catalog,
        run_input=ScenarioRunInput(
            run_id=_arg_str(args, "run_id"),
            case_id=_arg_str(args, "case_id"),
            scenario_id=_arg_str(args, "scenario_id"),
            telemetry=telemetry,
        ),
    )
    _print_json(
        {
            "case_id": result.case_id,
            "degraded_mode": result.degraded_mode,
            "evidence_bundle": result.evidence_bundle.to_dict(),
            "expected_behavior_satisfied": result.expected_behavior_satisfied,
            "final_authority_state": result.final_authority_state.value,
            "final_decision": result.final_decision.value,
            "operator_review_required": result.operator_review_required,
            "run_id": result.run_id,
            "scenario_id": result.scenario_id,
            "verification_result": result.verification_result.value,
        }
    )
    return 0 if result.verification_result is VerificationResult.PASS else 1


def _cmd_export_report(args: argparse.Namespace) -> int:
    report_payload = _load_json_object(_arg_path(args, "report"))

    if _arg_str(args, "format") == "json":
        _print_json(report_payload)
        return 0

    print(_report_payload_to_markdown(report_payload))
    return 0


def _cmd_audit_traceability(args: argparse.Namespace) -> int:
    assurance_case = load_assurance_case(_arg_path(args, "case"))
    catalog = load_scenario_catalog(_arg_path(args, "catalog"))
    mission_need = load_mission_need(_arg_path(args, "mission_need"))
    requirements = load_requirements(_arg_path(args, "requirements"))
    graph = build_traceability_graph(
        mission_need=mission_need,
        requirements=requirements,
        assurance_case=assurance_case,
        scenario_catalog=catalog,
    )
    report = graph.validate()
    scenario_id = _arg_optional_str(args, "scenario_id")
    claim_id = _arg_optional_str(args, "claim_id")
    connected_path = None

    if scenario_id is not None and claim_id is not None:
        connected_path = graph.has_connected_path(scenario_id, claim_id)

    _print_json(
        {
            "connected_path": connected_path,
            "errors": list(report.errors),
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
            "valid": report.is_valid,
            "warnings": list(report.warnings),
        }
    )
    return 0 if report.is_valid else 1


def load_assurance_case(path: Path) -> AssuranceCase:
    """Load an assurance case from JSON."""

    data = _load_json_object(path)
    return AssuranceCase(
        case_id=_get_str(data, "case_id"),
        title=_get_str(data, "title"),
        system_name=_get_str(data, "system_name"),
        mission_context=_get_str(data, "mission_context"),
        status=AssuranceCaseStatus.from_value(_get_str(data, "status", default="draft")),
        claims=tuple(_build_claim(item) for item in _get_list_of_dicts(data, "claims")),
        hazards=tuple(_build_hazard(item) for item in _get_list_of_dicts(data, "hazards")),
        controls=tuple(_build_control(item) for item in _get_list_of_dicts(data, "controls")),
        mitigations=tuple(
            _build_mitigation(item) for item in _get_list_of_dicts(data, "mitigations")
        ),
        assumptions=tuple(
            _build_assumption(item) for item in _get_list_of_dicts(data, "assumptions")
        ),
        evidence=tuple(_build_evidence_link(item) for item in _get_list_of_dicts(data, "evidence")),
        verification_criteria=tuple(
            _build_verification_criterion(item)
            for item in _get_list_of_dicts(data, "verification_criteria")
        ),
    )


def load_scenario_catalog(path: Path) -> ScenarioCatalog:
    """Load a scenario catalog from JSON."""

    data = _load_json_object(path)
    return ScenarioCatalog(
        operational_contexts=tuple(
            _build_operational_context(item)
            for item in _get_list_of_dicts(data, "operational_contexts")
        ),
        autonomy_functions=tuple(
            _build_autonomy_function(item)
            for item in _get_list_of_dicts(data, "autonomy_functions")
        ),
        operating_conditions=tuple(
            _build_operating_condition(item)
            for item in _get_list_of_dicts(data, "operating_conditions")
        ),
        stressors=tuple(_build_stressor(item) for item in _get_list_of_dicts(data, "stressors")),
        expected_behaviors=tuple(
            _build_expected_behavior(item)
            for item in _get_list_of_dicts(data, "expected_behaviors")
        ),
        acceptance_criteria=tuple(
            _build_acceptance_criterion(item)
            for item in _get_list_of_dicts(data, "acceptance_criteria")
        ),
        mission_threads=tuple(
            _build_mission_thread(item) for item in _get_list_of_dicts(data, "mission_threads")
        ),
        scenarios=tuple(_build_scenario(item) for item in _get_list_of_dicts(data, "scenarios")),
    )


def load_telemetry(path: Path) -> RuntimeTelemetry:
    """Load runtime telemetry from JSON."""

    data = _load_json_object(path)
    values = _get_telemetry_values(data, "values")
    return RuntimeTelemetry(
        values=values, source=_get_str(data, "source", default="json-telemetry")
    )


def load_evidence_bundle(path: Path) -> EvidenceBundle:
    """Load an evidence bundle from JSON."""

    data = _load_json_object(path)
    return EvidenceBundle(
        bundle_id=_get_str(data, "bundle_id"),
        case_id=_get_str(data, "case_id"),
        records=tuple(_build_evidence_record(item) for item in _get_list_of_dicts(data, "records")),
        scenario_id=_get_optional_str(data, "scenario_id"),
        created_by=_get_str(data, "created_by", default="ix-assurance-runtime"),
        bundle_hash=_get_optional_str(data, "bundle_hash"),
    )


def load_run_ledger(path: Path) -> RunLedger:
    """Load a run ledger from JSON."""

    data = _load_json_object(path)
    return RunLedger(
        ledger_id=_get_str(data, "ledger_id"),
        entries=tuple(_build_ledger_entry(item) for item in _get_list_of_dicts(data, "entries")),
        created_by=_get_str(data, "created_by", default="ix-run-ledger"),
    )


def load_mission_need(path: Path) -> MissionNeed:
    """Load a mission need from JSON."""

    data = _load_json_object(path)
    return MissionNeed(
        need_id=_get_str(data, "need_id"),
        statement=_get_str(data, "statement"),
        operational_driver=_get_str(data, "operational_driver"),
    )


def load_requirements(path: Path) -> tuple[Requirement, ...]:
    """Load requirements from a JSON list or wrapper object."""

    data = _load_json(path)
    if isinstance(data, list):
        items = [_as_json_object(item, "requirement") for item in data]
    else:
        wrapper = _as_json_object(data, "requirements payload")
        items = _get_list_of_dicts(wrapper, "requirements")

    return tuple(
        Requirement(
            requirement_id=_get_str(item, "requirement_id"),
            statement=_get_str(item, "statement"),
            verification_method=_get_str(item, "verification_method"),
            source=_get_str(item, "source"),
        )
        for item in items
    )


def _build_claim(data: dict[str, Any]) -> AssuranceClaim:
    return AssuranceClaim(
        claim_id=_get_str(data, "claim_id"),
        statement=_get_str(data, "statement"),
        argument=_get_str(data, "argument"),
        subclaim_ids=_get_tuple_str(data, "subclaim_ids"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
        assumption_ids=_get_tuple_str(data, "assumption_ids"),
        verification_criterion_ids=_get_tuple_str(data, "verification_criterion_ids"),
        verification_result=VerificationResult.from_value(
            _get_str(data, "verification_result", default="not_run")
        ),
    )


def _build_hazard(data: dict[str, Any]) -> Hazard:
    return Hazard(
        hazard_id=_get_str(data, "hazard_id"),
        title=_get_str(data, "title"),
        description=_get_str(data, "description"),
        severity=HazardSeverity.from_value(_get_str(data, "severity")),
        control_ids=_get_tuple_str(data, "control_ids"),
        mitigation_ids=_get_tuple_str(data, "mitigation_ids"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_control(data: dict[str, Any]) -> Control:
    return Control(
        control_id=_get_str(data, "control_id"),
        name=_get_str(data, "name"),
        description=_get_str(data, "description"),
        mitigates_hazard_ids=_get_tuple_str(data, "mitigates_hazard_ids"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_mitigation(data: dict[str, Any]) -> Mitigation:
    return Mitigation(
        mitigation_id=_get_str(data, "mitigation_id"),
        hazard_id=_get_str(data, "hazard_id"),
        control_id=_get_str(data, "control_id"),
        description=_get_str(data, "description"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_assumption(data: dict[str, Any]) -> Assumption:
    return Assumption(
        assumption_id=_get_str(data, "assumption_id"),
        statement=_get_str(data, "statement"),
        rationale=_get_str(data, "rationale"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_evidence_link(data: dict[str, Any]) -> EvidenceLink:
    return EvidenceLink(
        evidence_id=_get_str(data, "evidence_id"),
        description=_get_str(data, "description"),
        source=_get_str(data, "source"),
        status=EvidenceStatus.from_value(_get_str(data, "status", default="provided")),
        supports=_get_tuple_str(data, "supports"),
        content_hash=_get_optional_str(data, "content_hash"),
    )


def _build_verification_criterion(data: dict[str, Any]) -> VerificationCriterion:
    return VerificationCriterion(
        criterion_id=_get_str(data, "criterion_id"),
        statement=_get_str(data, "statement"),
        verification_method=_get_str(data, "verification_method"),
        expected_result=_get_str(data, "expected_result"),
        result=VerificationResult.from_value(_get_str(data, "result", default="not_run")),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_operational_context(data: dict[str, Any]) -> OperationalContext:
    return OperationalContext(
        context_id=_get_str(data, "context_id"),
        name=_get_str(data, "name"),
        environment=_get_str(data, "environment"),
        mission_phase=_get_str(data, "mission_phase"),
        description=_get_str(data, "description"),
        constraints=_get_tuple_str(data, "constraints"),
    )


def _build_autonomy_function(data: dict[str, Any]) -> AutonomyFunction:
    return AutonomyFunction(
        function_id=_get_str(data, "function_id"),
        name=_get_str(data, "name"),
        description=_get_str(data, "description"),
        input_signals=_get_tuple_str(data, "input_signals"),
        output_actions=_get_tuple_str(data, "output_actions"),
        nominal_authority_state=RuntimeAuthorityState.from_value(
            _get_str(data, "nominal_authority_state", default="autonomous_allowed")
        ),
    )


def _build_operating_condition(data: dict[str, Any]) -> OperatingCondition:
    return OperatingCondition(
        condition_id=_get_str(data, "condition_id"),
        name=_get_str(data, "name"),
        description=_get_str(data, "description"),
        telemetry_key=_get_str(data, "telemetry_key"),
        expected_range=_get_str(data, "expected_range"),
    )


def _build_stressor(data: dict[str, Any]) -> Stressor:
    return Stressor(
        stressor_id=_get_str(data, "stressor_id"),
        name=_get_str(data, "name"),
        description=_get_str(data, "description"),
        severity=HazardSeverity.from_value(_get_str(data, "severity")),
        affected_capabilities=_get_tuple_str(data, "affected_capabilities"),
        trigger_condition=_get_str(data, "trigger_condition"),
    )


def _build_expected_behavior(data: dict[str, Any]) -> ExpectedSafeBehavior:
    return ExpectedSafeBehavior(
        behavior_id=_get_str(data, "behavior_id"),
        description=_get_str(data, "description"),
        required_decision=AutonomyDecisionType.from_value(_get_str(data, "required_decision")),
        required_authority_state=RuntimeAuthorityState.from_value(
            _get_str(data, "required_authority_state")
        ),
        rationale=_get_str(data, "rationale"),
    )


def _build_acceptance_criterion(data: dict[str, Any]) -> AcceptanceCriterion:
    return AcceptanceCriterion(
        criterion_id=_get_str(data, "criterion_id"),
        statement=_get_str(data, "statement"),
        measurement=_get_str(data, "measurement"),
        expected_result=_get_str(data, "expected_result"),
        required_verification_result=VerificationResult.from_value(
            _get_str(data, "required_verification_result", default="pass")
        ),
        requires_evidence=_get_bool(data, "requires_evidence", default=True),
    )


def _build_mission_thread(data: dict[str, Any]) -> MissionThread:
    return MissionThread(
        mission_thread_id=_get_str(data, "mission_thread_id"),
        name=_get_str(data, "name"),
        objective=_get_str(data, "objective"),
        operational_context_id=_get_str(data, "operational_context_id"),
        autonomy_function_ids=_get_tuple_str(data, "autonomy_function_ids"),
        scenario_ids=_get_tuple_str(data, "scenario_ids"),
        requirement_ids=_get_tuple_str(data, "requirement_ids"),
        hazard_ids=_get_tuple_str(data, "hazard_ids"),
    )


def _build_scenario(data: dict[str, Any]) -> Scenario:
    return Scenario(
        scenario_id=_get_str(data, "scenario_id"),
        mission_thread_id=_get_str(data, "mission_thread_id"),
        title=_get_str(data, "title"),
        description=_get_str(data, "description"),
        operational_context_id=_get_str(data, "operational_context_id"),
        autonomy_function_id=_get_str(data, "autonomy_function_id"),
        operating_condition_ids=_get_tuple_str(data, "operating_condition_ids"),
        stressor_ids=_get_tuple_str(data, "stressor_ids"),
        expected_behavior_id=_get_str(data, "expected_behavior_id"),
        acceptance_criterion_ids=_get_tuple_str(data, "acceptance_criterion_ids"),
        hazard_ids=_get_tuple_str(data, "hazard_ids"),
        evidence_ids=_get_tuple_str(data, "evidence_ids"),
    )


def _build_evidence_record(data: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=_get_str(data, "evidence_id"),
        kind=_get_str(data, "kind"),
        source=_get_str(data, "source"),
        payload=_get_json_object(data, "payload"),
        status=EvidenceStatus.from_value(_get_str(data, "status", default="provided")),
        created_by=_get_str(data, "created_by", default="ix-assurance-runtime"),
        tags=_get_tuple_str(data, "tags"),
        content_hash=_get_optional_str(data, "content_hash"),
    )


def _build_ledger_entry(data: dict[str, Any]) -> LedgerEntry:
    return LedgerEntry(
        entry_id=_get_str(data, "entry_id"),
        sequence_number=_get_int(data, "sequence_number"),
        record_type=LedgerRecordType(_get_str(data, "record_type")),
        case_id=_get_str(data, "case_id"),
        artifact_id=_get_str(data, "artifact_id"),
        artifact_hash=_get_str(data, "artifact_hash"),
        payload=_get_json_object(data, "payload"),
        run_id=_get_optional_str(data, "run_id"),
        scenario_id=_get_optional_str(data, "scenario_id"),
        previous_entry_hash=_get_optional_str(data, "previous_entry_hash"),
        created_by=_get_str(data, "created_by", default="ix-run-ledger"),
        tags=_get_tuple_str(data, "tags"),
        entry_hash=_get_optional_str(data, "entry_hash"),
    )


def _report_payload_to_markdown(payload: dict[str, Any]) -> str:
    report_id = _get_str(payload, "report_id")
    lines = [
        f"# Assurance Report: {report_id}",
        "",
        f"- Case ID: `{_get_str(payload, 'case_id')}`",
        f"- Scenario ID: `{_get_str(payload, 'scenario_id')}`",
        f"- Run ID: `{_get_str(payload, 'run_id')}`",
        f"- Overall Result: `{_get_str(payload, 'overall_result')}`",
        f"- Accepted: `{str(_get_bool(payload, 'accepted')).lower()}`",
        f"- Generated By: `{_get_str(payload, 'generated_by')}`",
        "",
    ]

    for section in _get_list_of_dicts(payload, "sections"):
        lines.append(f"## {_get_str(section, 'title')}")
        lines.append(f"Severity: `{_get_str(section, 'severity')}`")
        lines.append("")
        for line in _get_tuple_str(section, "lines"):
            lines.append(f"- {line}")
        lines.append("")

    return "\n".join(lines).strip()


def _arg_path(args: argparse.Namespace, name: str) -> Path:
    return Path(_arg_str(args, name))


def _arg_str(args: argparse.Namespace, name: str) -> str:
    value = getattr(args, name)
    if not isinstance(value, str):
        raise ValueError(f"argument {name!r} must be a string")
    return value


def _arg_optional_str(args: argparse.Namespace, name: str) -> str | None:
    value = getattr(args, name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"argument {name!r} must be a string when provided")
    return value


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_object(path: Path) -> dict[str, Any]:
    return _as_json_object(_load_json(path), str(path))


def _as_json_object(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field_name} must be a JSON object.")
    return cast(dict[str, Any], value)


def _get_str(data: dict[str, Any], key: str, *, default: str | None = None) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string.")
    return value


def _get_optional_str(data: dict[str, Any], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key!r} must be a string when provided.")
    return value


def _get_int(data: dict[str, Any], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key!r} must be an integer.")
    return value


def _get_bool(data: dict[str, Any], key: str, *, default: bool | None = None) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key!r} must be a boolean.")
    return value


def _get_tuple_str(data: dict[str, Any], key: str) -> tuple[str, ...]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key!r} must be a JSON array of strings.")
    strings: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{key!r} must contain only strings.")
        strings.append(item)
    return tuple(strings)


def _get_json_object(data: dict[str, Any], key: str) -> dict[str, JSONValue]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key!r} must be a JSON object.")
    return cast(dict[str, JSONValue], value)


def _get_telemetry_values(data: dict[str, Any], key: str) -> dict[str, TelemetryValue]:
    value = data.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{key!r} must be a JSON object.")

    values: dict[str, TelemetryValue] = {}
    for item_key, item_value in value.items():
        if not isinstance(item_key, str):
            raise ValueError(f"{key!r} must contain only string keys.")
        if not (item_value is None or isinstance(item_value, str | int | float | bool)):
            raise ValueError(f"{key!r} values must be strings, numbers, booleans, or null.")
        values[item_key] = item_value
    return values


def _get_list_of_dicts(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key, [])
    if not isinstance(value, list):
        raise ValueError(f"{key!r} must be a JSON array.")
    return [_as_json_object(item, key) for item in value]


def _print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


__all__ = [
    "AssuranceReportGenerator",
    "VerificationEngine",
    "build_parser",
    "load_assurance_case",
    "load_evidence_bundle",
    "load_mission_need",
    "load_requirements",
    "load_run_ledger",
    "load_scenario_catalog",
    "load_telemetry",
    "main",
]
