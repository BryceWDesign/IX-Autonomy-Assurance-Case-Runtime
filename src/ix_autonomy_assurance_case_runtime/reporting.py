"""Assurance report generation for runtime verification outputs.

The report generator turns assurance-case, scenario-run, evidence, verification,
and traceability outputs into deterministic machine-readable and Markdown
reports.

The goal is not to create a polished compliance binder. The goal is to produce a
reviewable assurance record that clearly states what passed, what failed, what
requires follow-up, which hazards remain unresolved, which claims are supported,
and whether evidence integrity survived validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ix_autonomy_assurance_case_runtime.assurance_case import AssuranceCase
from ix_autonomy_assurance_case_runtime.contracts import VerificationResult
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunResult
from ix_autonomy_assurance_case_runtime.scenarios import ScenarioCatalog
from ix_autonomy_assurance_case_runtime.traceability import TraceabilityGraph
from ix_autonomy_assurance_case_runtime.verification import RuntimeVerificationSummary


class ReportGenerationError(ValueError):
    """Raised when an assurance report cannot be generated safely."""


class ReportSeverity(StrEnum):
    """Severity of a report section."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ReportGenerationError(f"{field_name} must not be blank.")
    return normalized


def _normalize_lines(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, "section line") for value in values)
    if not normalized:
        raise ReportGenerationError("section lines must not be empty.")
    return normalized


def _severity_from_result(result: VerificationResult) -> ReportSeverity:
    if result is VerificationResult.FAIL:
        return ReportSeverity.ERROR
    if result in {VerificationResult.INCONCLUSIVE, VerificationResult.NOT_RUN}:
        return ReportSeverity.WARNING
    return ReportSeverity.INFO


@dataclass(frozen=True, slots=True)
class ReportSection:
    """One human-readable and machine-readable report section."""

    title: str
    severity: ReportSeverity
    lines: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "lines", _normalize_lines(self.lines))

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-compatible section dictionary."""

        return {
            "lines": list(self.lines),
            "severity": self.severity.value,
            "title": self.title,
        }

    def to_markdown(self) -> str:
        """Return this section as Markdown."""

        lines = [f"## {self.title}", f"Severity: `{self.severity.value}`", ""]
        lines.extend(f"- {line}" for line in self.lines)
        return "\n".join(lines)


@dataclass(frozen=True, slots=True)
class AssuranceReport:
    """Generated assurance report for one scenario run and verification summary."""

    report_id: str
    case_id: str
    scenario_id: str
    run_id: str
    overall_result: VerificationResult
    generated_by: str
    sections: tuple[ReportSection, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", _require_text(self.report_id, "report_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(self, "generated_by", _require_text(self.generated_by, "generated_by"))

        if not self.sections:
            raise ReportGenerationError("sections must not be empty.")

    def accepted(self) -> bool:
        """Return whether the report supports acceptance."""

        return self.overall_result is VerificationResult.PASS

    def section_titles(self) -> tuple[str, ...]:
        """Return section titles in report order."""

        return tuple(section.title for section in self.sections)

    def error_section_titles(self) -> tuple[str, ...]:
        """Return section titles marked as errors."""

        return tuple(
            section.title for section in self.sections if section.severity is ReportSeverity.ERROR
        )

    def warning_section_titles(self) -> tuple[str, ...]:
        """Return section titles marked as warnings."""

        return tuple(
            section.title for section in self.sections if section.severity is ReportSeverity.WARNING
        )

    def to_dict(self) -> dict[str, object]:
        """Return a deterministic machine-readable report dictionary."""

        return {
            "accepted": self.accepted(),
            "case_id": self.case_id,
            "generated_by": self.generated_by,
            "overall_result": self.overall_result.value,
            "report_id": self.report_id,
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "sections": [section.to_dict() for section in self.sections],
        }

    def to_markdown(self) -> str:
        """Return a deterministic human-readable Markdown report."""

        lines = [
            f"# Assurance Report: {self.report_id}",
            "",
            f"- Case ID: `{self.case_id}`",
            f"- Scenario ID: `{self.scenario_id}`",
            f"- Run ID: `{self.run_id}`",
            f"- Overall Result: `{self.overall_result.value}`",
            f"- Accepted: `{str(self.accepted()).lower()}`",
            f"- Generated By: `{self.generated_by}`",
            "",
        ]

        lines.extend(section.to_markdown() for section in self.sections)
        return "\n\n".join(lines)


@dataclass(frozen=True, slots=True)
class AssuranceReportGenerator:
    """Generates assurance reports from runtime and verification artifacts."""

    generated_by: str = "ix-assurance-report-generator"

    def __post_init__(self) -> None:
        object.__setattr__(self, "generated_by", _require_text(self.generated_by, "generated_by"))

    def generate(
        self,
        *,
        report_id: str,
        assurance_case: AssuranceCase,
        scenario_catalog: ScenarioCatalog,
        run_result: ScenarioRunResult,
        verification_summary: RuntimeVerificationSummary,
        traceability_graph: TraceabilityGraph | None = None,
    ) -> AssuranceReport:
        """Generate an assurance report from runtime and verification artifacts."""

        normalized_report_id = _require_text(report_id, "report_id")
        self._validate_identity_alignment(
            assurance_case=assurance_case,
            run_result=run_result,
            verification_summary=verification_summary,
        )

        sections = (
            self._summary_section(
                assurance_case=assurance_case,
                run_result=run_result,
                verification_summary=verification_summary,
            ),
            self._runtime_outcome_section(run_result),
            self._verification_check_section(verification_summary),
            self._assurance_gap_section(assurance_case),
            self._claim_posture_section(assurance_case),
            self._acceptance_criteria_section(
                scenario_catalog=scenario_catalog,
                verification_summary=verification_summary,
            ),
            self._evidence_integrity_section(run_result),
            self._traceability_section(
                run_result=run_result,
                verification_summary=verification_summary,
                traceability_graph=traceability_graph,
            ),
        )

        return AssuranceReport(
            report_id=normalized_report_id,
            case_id=run_result.case_id,
            scenario_id=run_result.scenario_id,
            run_id=run_result.run_id,
            overall_result=verification_summary.overall_result,
            generated_by=self.generated_by,
            sections=sections,
        )

    @staticmethod
    def _validate_identity_alignment(
        *,
        assurance_case: AssuranceCase,
        run_result: ScenarioRunResult,
        verification_summary: RuntimeVerificationSummary,
    ) -> None:
        if assurance_case.case_id != run_result.case_id:
            raise ReportGenerationError(
                f"Assurance case {assurance_case.case_id!r} does not match run case "
                f"{run_result.case_id!r}."
            )

        if verification_summary.case_id != run_result.case_id:
            raise ReportGenerationError(
                f"Verification summary case {verification_summary.case_id!r} does not "
                f"match run case {run_result.case_id!r}."
            )

        if verification_summary.scenario_id != run_result.scenario_id:
            raise ReportGenerationError(
                f"Verification summary scenario {verification_summary.scenario_id!r} "
                f"does not match run scenario {run_result.scenario_id!r}."
            )

        if verification_summary.run_id != run_result.run_id:
            raise ReportGenerationError(
                f"Verification summary run {verification_summary.run_id!r} does not "
                f"match run {run_result.run_id!r}."
            )

    @staticmethod
    def _summary_section(
        *,
        assurance_case: AssuranceCase,
        run_result: ScenarioRunResult,
        verification_summary: RuntimeVerificationSummary,
    ) -> ReportSection:
        failed = verification_summary.failed_check_ids()
        follow_up = verification_summary.follow_up_check_ids()

        lines = [
            f"Assurance case `{assurance_case.case_id}` covers `{assurance_case.system_name}`.",
            f"Scenario `{run_result.scenario_id}` produced `{run_result.final_decision.value}`.",
            f"Final authority state is `{run_result.final_authority_state.value}`.",
            f"Verification overall result is `{verification_summary.overall_result.value}`.",
            f"Failed checks: `{', '.join(failed) if failed else 'none'}`.",
            f"Follow-up checks: `{', '.join(follow_up) if follow_up else 'none'}`.",
        ]

        return ReportSection(
            title="Executive Summary",
            severity=_severity_from_result(verification_summary.overall_result),
            lines=tuple(lines),
        )

    @staticmethod
    def _runtime_outcome_section(run_result: ScenarioRunResult) -> ReportSection:
        lines = (
            f"Runtime decision: `{run_result.final_decision.value}`.",
            f"Runtime authority state: `{run_result.final_authority_state.value}`.",
            "Expected behavior satisfied: "
            f"`{str(run_result.expected_behavior_satisfied).lower()}`.",
            f"Operator review required: `{str(run_result.operator_review_required).lower()}`.",
            f"Degraded mode: `{str(run_result.degraded_mode).lower()}`.",
            f"Degradation worst level: `{run_result.degradation_assessment.worst_level().value}`.",
            f"Runtime rationale: {run_result.rationale}",
        )

        severity = ReportSeverity.INFO
        if not run_result.expected_behavior_satisfied:
            severity = ReportSeverity.ERROR
        elif run_result.operator_review_required or run_result.degraded_mode:
            severity = ReportSeverity.WARNING

        return ReportSection(
            title="Runtime Outcome",
            severity=severity,
            lines=lines,
        )

    @staticmethod
    def _verification_check_section(
        verification_summary: RuntimeVerificationSummary,
    ) -> ReportSection:
        lines = tuple(
            f"`{check.check_id}` → `{check.result.value}` / `{check.severity.value}`: "
            f"{check.message}"
            for check in verification_summary.checks
        )

        return ReportSection(
            title="Verification Checks",
            severity=_severity_from_result(verification_summary.overall_result),
            lines=lines,
        )

    @staticmethod
    def _assurance_gap_section(assurance_case: AssuranceCase) -> ReportSection:
        unresolved_hazards = assurance_case.unresolved_hazard_ids()
        unsupported_claims = assurance_case.unsupported_claim_ids()
        missing_evidence = _missing_evidence_ids(assurance_case)

        unresolved_text = ", ".join(unresolved_hazards) if unresolved_hazards else "none"
        unsupported_text = ", ".join(unsupported_claims) if unsupported_claims else "none"
        missing_text = ", ".join(missing_evidence) if missing_evidence else "none"
        lines = (
            f"Unresolved severe hazards: `{unresolved_text}`.",
            f"Unsupported claims: `{unsupported_text}`.",
            f"Missing evidence references: `{missing_text}`.",
        )

        severity = ReportSeverity.INFO
        if unresolved_hazards or missing_evidence:
            severity = ReportSeverity.ERROR
        elif unsupported_claims:
            severity = ReportSeverity.WARNING

        return ReportSection(
            title="Assurance Gaps",
            severity=severity,
            lines=lines,
        )

    @staticmethod
    def _claim_posture_section(assurance_case: AssuranceCase) -> ReportSection:
        accepted_claim_ids = tuple(
            claim.claim_id
            for claim in assurance_case.claims
            if claim.verification_result is VerificationResult.PASS and claim.has_support_path()
        )
        blocked_claim_ids = tuple(
            claim.claim_id
            for claim in assurance_case.claims
            if claim.verification_result.requires_follow_up() or not claim.has_support_path()
        )

        accepted_text = ", ".join(accepted_claim_ids) if accepted_claim_ids else "none"
        blocked_text = ", ".join(blocked_claim_ids) if blocked_claim_ids else "none"
        lines = (
            f"Accepted claims: `{accepted_text}`.",
            f"Blocked or follow-up claims: `{blocked_text}`.",
        )

        return ReportSection(
            title="Claim Posture",
            severity=ReportSeverity.WARNING if blocked_claim_ids else ReportSeverity.INFO,
            lines=lines,
        )

    @staticmethod
    def _acceptance_criteria_section(
        *,
        scenario_catalog: ScenarioCatalog,
        verification_summary: RuntimeVerificationSummary,
    ) -> ReportSection:
        criteria_ids = tuple(
            criterion.criterion_id for criterion in scenario_catalog.acceptance_criteria
        )
        failed_criteria = tuple(
            check.check_id.removeprefix("acceptance-criterion:")
            for check in verification_summary.checks
            if (
                check.check_id.startswith("acceptance-criterion:")
                and check.result is VerificationResult.FAIL
            )
        )

        criteria_text = ", ".join(criteria_ids) if criteria_ids else "none"
        failed_text = ", ".join(failed_criteria) if failed_criteria else "none"
        lines = (
            f"Acceptance criteria in catalog: `{criteria_text}`.",
            f"Failed acceptance criteria: `{failed_text}`.",
        )

        return ReportSection(
            title="Acceptance Criteria",
            severity=ReportSeverity.ERROR if failed_criteria else ReportSeverity.INFO,
            lines=lines,
        )

    @staticmethod
    def _evidence_integrity_section(run_result: ScenarioRunResult) -> ReportSection:
        integrity_report = run_result.evidence_bundle.validate_integrity()
        record_ids = tuple(record.evidence_id for record in run_result.evidence_bundle.records)

        bundle_hash_present = str(run_result.evidence_bundle.bundle_hash is not None).lower()
        record_text = ", ".join(record_ids) if record_ids else "none"
        error_text = "; ".join(integrity_report.errors) if integrity_report.errors else "none"
        warning_text = "; ".join(integrity_report.warnings) if integrity_report.warnings else "none"
        lines = (
            f"Evidence bundle: `{run_result.evidence_bundle.bundle_id}`.",
            f"Bundle hash present: `{bundle_hash_present}`.",
            f"Evidence records: `{record_text}`.",
            f"Integrity errors: `{error_text}`.",
            f"Integrity warnings: `{warning_text}`.",
        )

        severity = ReportSeverity.INFO
        if integrity_report.errors:
            severity = ReportSeverity.ERROR
        elif integrity_report.warnings:
            severity = ReportSeverity.WARNING

        return ReportSection(
            title="Evidence Integrity",
            severity=severity,
            lines=lines,
        )

    @staticmethod
    def _traceability_section(
        *,
        run_result: ScenarioRunResult,
        verification_summary: RuntimeVerificationSummary,
        traceability_graph: TraceabilityGraph | None,
    ) -> ReportSection:
        trace_checks = tuple(
            check
            for check in verification_summary.checks
            if check.check_id.startswith("traceability")
            or check.check_id == "scenario-to-claim-trace"
        )

        graph_line = "Traceability graph provided: `false`."
        graph_warning_line = "Traceability graph warnings: `not evaluated`."
        graph_error_line = "Traceability graph errors: `not evaluated`."

        if traceability_graph is not None:
            graph_report = traceability_graph.validate()
            graph_line = "Traceability graph provided: `true`."
            graph_warning_line = (
                "Traceability graph warnings: "
                f"`{'; '.join(graph_report.warnings) if graph_report.warnings else 'none'}`."
            )
            graph_error_line = (
                "Traceability graph errors: "
                f"`{'; '.join(graph_report.errors) if graph_report.errors else 'none'}`."
            )

        trace_check_lines = tuple(
            f"`{check.check_id}` → `{check.result.value}`: {check.message}"
            for check in trace_checks
        )
        lines = (
            graph_line,
            graph_error_line,
            graph_warning_line,
            f"Scenario traced: `{run_result.scenario_id}`.",
            *(trace_check_lines or ("Traceability checks: `none`.",)),
        )

        severity = ReportSeverity.INFO
        if any(check.result is VerificationResult.FAIL for check in trace_checks):
            severity = ReportSeverity.ERROR
        elif traceability_graph is None or any(
            check.result in {VerificationResult.INCONCLUSIVE, VerificationResult.NOT_RUN}
            for check in trace_checks
        ):
            severity = ReportSeverity.WARNING

        return ReportSection(
            title="Traceability",
            severity=severity,
            lines=lines,
        )


def _missing_evidence_ids(assurance_case: AssuranceCase) -> tuple[str, ...]:
    known_evidence_ids = set(assurance_case.evidence_index())
    referenced_ids: set[str] = set()

    for claim in assurance_case.claims:
        referenced_ids.update(claim.evidence_ids)

    for hazard in assurance_case.hazards:
        referenced_ids.update(hazard.evidence_ids)

    for control in assurance_case.controls:
        referenced_ids.update(control.evidence_ids)

    for mitigation in assurance_case.mitigations:
        referenced_ids.update(mitigation.evidence_ids)

    for assumption in assurance_case.assumptions:
        referenced_ids.update(assumption.evidence_ids)

    for criterion in assurance_case.verification_criteria:
        referenced_ids.update(criterion.evidence_ids)

    return tuple(sorted(referenced_ids - known_evidence_ids))
