"""Independent verification engine for scenario-run assurance evidence.

The verification engine evaluates scenario-run output against the assurance case,
scenario catalog, acceptance criteria, evidence integrity, hazard coverage, and
optional traceability graph.

The scenario runner executes the runtime path. This module answers a separate
question: whether the generated run evidence is sufficient to support the
assurance claim under review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from ix_autonomy_assurance_case_runtime.assurance_case import AssuranceCase
from ix_autonomy_assurance_case_runtime.contracts import VerificationResult
from ix_autonomy_assurance_case_runtime.runner import ScenarioRunResult
from ix_autonomy_assurance_case_runtime.scenarios import AcceptanceCriterion, Scenario, ScenarioCatalog
from ix_autonomy_assurance_case_runtime.traceability import TraceabilityGraph


class VerificationEngineError(ValueError):
    """Raised when verification inputs are malformed."""


class VerificationIssueSeverity(StrEnum):
    """Severity assigned to a verification check result."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise VerificationEngineError(f"{field_name} must not be blank.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise VerificationEngineError(f"{field_name} must not contain duplicate values.")
    return normalized


@dataclass(frozen=True, slots=True)
class VerificationCheckResult:
    """Single verification check result."""

    check_id: str
    result: VerificationResult
    severity: VerificationIssueSeverity
    message: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "check_id", _require_text(self.check_id, "check_id"))
        object.__setattr__(self, "message", _require_text(self.message, "message"))
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_text_tuple(self.evidence_ids, "evidence_ids"),
        )

    def blocks_acceptance(self) -> bool:
        """Return whether this check blocks acceptance."""

        return self.result is VerificationResult.FAIL

    def requires_follow_up(self) -> bool:
        """Return whether this check requires reviewer follow-up."""

        return self.result.requires_follow_up()


@dataclass(frozen=True, slots=True)
class RuntimeVerificationSummary:
    """Verification summary for one scenario run."""

    run_id: str
    case_id: str
    scenario_id: str
    overall_result: VerificationResult
    checks: tuple[VerificationCheckResult, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", _require_text(self.run_id, "run_id"))
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "scenario_id", _require_text(self.scenario_id, "scenario_id"))

        if not self.checks:
            raise VerificationEngineError("checks must not be empty.")

    def accepted(self) -> bool:
        """Return whether every verification check supports acceptance."""

        return self.overall_result is VerificationResult.PASS

    def failed_check_ids(self) -> tuple[str, ...]:
        """Return check identifiers with failed results."""

        return tuple(check.check_id for check in self.checks if check.result is VerificationResult.FAIL)

    def follow_up_check_ids(self) -> tuple[str, ...]:
        """Return check identifiers that require follow-up."""

        return tuple(check.check_id for check in self.checks if check.requires_follow_up())

    def error_messages(self) -> tuple[str, ...]:
        """Return error-level messages."""

        return tuple(
            check.message
            for check in self.checks
            if check.severity is VerificationIssueSeverity.ERROR
        )

    def warning_messages(self) -> tuple[str, ...]:
        """Return warning-level messages."""

        return tuple(
            check.message
            for check in self.checks
            if check.severity is VerificationIssueSeverity.WARNING
        )


@dataclass(frozen=True, slots=True)
class VerificationEngine:
    """Verifies scenario-run evidence against assurance and T&E artifacts."""

    require_traceability: bool = False

    def verify_run(
        self,
        *,
        assurance_case: AssuranceCase,
        scenario_catalog: ScenarioCatalog,
        run_result: ScenarioRunResult,
        traceability_graph: TraceabilityGraph | None = None,
    ) -> RuntimeVerificationSummary:
        """Verify one scenario run and return an acceptance summary."""

        checks: list[VerificationCheckResult] = []

        checks.extend(self._verify_assurance_case(assurance_case))
        checks.extend(self._verify_scenario_catalog(scenario_catalog))
        scenario = self._scenario_for_run(scenario_catalog=scenario_catalog, run_result=run_result)

        if scenario is None:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-present",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message=(
                        f"Run references scenario {run_result.scenario_id!r}, but the "
                        "scenario is not present in the catalog."
                    ),
                )
            )
        else:
            checks.extend(self._verify_acceptance_criteria(scenario, scenario_catalog, run_result))
            checks.extend(self._verify_required_evidence(scenario, scenario_catalog, run_result))
            checks.extend(self._verify_scenario_hazard_coverage(scenario, assurance_case))

        checks.extend(self._verify_run_result(run_result))
        checks.extend(self._verify_evidence_bundle(run_result))
        checks.extend(
            self._verify_traceability(
                assurance_case=assurance_case,
                run_result=run_result,
                traceability_graph=traceability_graph,
            )
        )

        return RuntimeVerificationSummary(
            run_id=run_result.run_id,
            case_id=run_result.case_id,
            scenario_id=run_result.scenario_id,
            overall_result=self._overall_result(checks),
            checks=tuple(checks),
        )

    @staticmethod
    def _overall_result(checks: list[VerificationCheckResult]) -> VerificationResult:
        if any(check.result is VerificationResult.FAIL for check in checks):
            return VerificationResult.FAIL
        if any(
            check.result in {
                VerificationResult.INCONCLUSIVE,
                VerificationResult.NOT_RUN,
            }
            for check in checks
        ):
            return VerificationResult.INCONCLUSIVE
        return VerificationResult.PASS

    @staticmethod
    def _verify_assurance_case(
        assurance_case: AssuranceCase,
    ) -> tuple[VerificationCheckResult, ...]:
        report = assurance_case.validate_references()
        checks: list[VerificationCheckResult] = []

        if report.errors:
            checks.append(
                VerificationCheckResult(
                    check_id="assurance-case-valid",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Assurance case validation failed: " + "; ".join(report.errors),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="assurance-case-valid",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Assurance case references are valid.",
                )
            )

        if report.warnings:
            checks.append(
                VerificationCheckResult(
                    check_id="assurance-case-warnings",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Assurance case warnings require review: " + "; ".join(report.warnings),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="assurance-case-warnings",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Assurance case has no validation warnings.",
                )
            )

        unresolved_hazard_ids = assurance_case.unresolved_hazard_ids()
        if unresolved_hazard_ids:
            checks.append(
                VerificationCheckResult(
                    check_id="severe-hazards-resolved",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message=(
                        "Severe hazards lack control or mitigation paths: "
                        + ", ".join(unresolved_hazard_ids)
                    ),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="severe-hazards-resolved",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Severe hazards have control or mitigation paths.",
                )
            )

        return tuple(checks)

    @staticmethod
    def _verify_scenario_catalog(
        scenario_catalog: ScenarioCatalog,
    ) -> tuple[VerificationCheckResult, ...]:
        report = scenario_catalog.validate_references()
        checks: list[VerificationCheckResult] = []

        if report.errors:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-catalog-valid",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Scenario catalog validation failed: " + "; ".join(report.errors),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-catalog-valid",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Scenario catalog references are valid.",
                )
            )

        if report.warnings:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-catalog-warnings",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Scenario catalog warnings require review: " + "; ".join(report.warnings),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-catalog-warnings",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Scenario catalog has no validation warnings.",
                )
            )

        return tuple(checks)

    @staticmethod
    def _scenario_for_run(
        *,
        scenario_catalog: ScenarioCatalog,
        run_result: ScenarioRunResult,
    ) -> Scenario | None:
        return scenario_catalog.scenario_index().get(run_result.scenario_id)

    @staticmethod
    def _verify_acceptance_criteria(
        scenario: Scenario,
        scenario_catalog: ScenarioCatalog,
        run_result: ScenarioRunResult,
    ) -> tuple[VerificationCheckResult, ...]:
        criteria = scenario_catalog.acceptance_criterion_index()
        checks: list[VerificationCheckResult] = []

        for criterion_id in scenario.acceptance_criterion_ids:
            criterion = criteria.get(criterion_id)
            if criterion is None:
                checks.append(
                    VerificationCheckResult(
                        check_id=f"acceptance-criterion-present:{criterion_id}",
                        result=VerificationResult.FAIL,
                        severity=VerificationIssueSeverity.ERROR,
                        message=f"Acceptance criterion {criterion_id!r} is missing.",
                    )
                )
                continue

            result = VerificationResult.PASS
            severity = VerificationIssueSeverity.INFO
            message = f"Acceptance criterion {criterion.criterion_id!r} is satisfied."

            if not criterion.accepts_result(run_result.verification_result):
                result = VerificationResult.FAIL
                severity = VerificationIssueSeverity.ERROR
                message = (
                    f"Acceptance criterion {criterion.criterion_id!r} requires "
                    f"{criterion.required_verification_result.value!r}, but the run "
                    f"produced {run_result.verification_result.value!r}."
                )

            checks.append(
                VerificationCheckResult(
                    check_id=f"acceptance-criterion:{criterion.criterion_id}",
                    result=result,
                    severity=severity,
                    message=message,
                    evidence_ids=tuple(record.evidence_id for record in run_result.evidence_bundle.records),
                )
            )

        return tuple(checks)

    @staticmethod
    def _verify_required_evidence(
        scenario: Scenario,
        scenario_catalog: ScenarioCatalog,
        run_result: ScenarioRunResult,
    ) -> tuple[VerificationCheckResult, ...]:
        criteria_by_id: dict[str, AcceptanceCriterion] = scenario_catalog.acceptance_criterion_index()
        referenced_criteria = tuple(
            criteria_by_id[criterion_id]
            for criterion_id in scenario.acceptance_criterion_ids
            if criterion_id in criteria_by_id
        )
        requires_evidence = any(criterion.requires_evidence for criterion in referenced_criteria)
        record_ids = tuple(record.evidence_id for record in run_result.evidence_bundle.records)

        if requires_evidence and not record_ids:
            return (
                VerificationCheckResult(
                    check_id="required-evidence-present",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Scenario acceptance criteria require evidence, but no records exist.",
                ),
            )

        if requires_evidence and any(record.content_hash is None for record in run_result.evidence_bundle.records):
            return (
                VerificationCheckResult(
                    check_id="required-evidence-present",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Scenario evidence exists but one or more records lack content hashes.",
                    evidence_ids=record_ids,
                ),
            )

        return (
            VerificationCheckResult(
                check_id="required-evidence-present",
                result=VerificationResult.PASS,
                severity=VerificationIssueSeverity.INFO,
                message="Required scenario evidence is present.",
                evidence_ids=record_ids,
            ),
        )

    @staticmethod
    def _verify_scenario_hazard_coverage(
        scenario: Scenario,
        assurance_case: AssuranceCase,
    ) -> tuple[VerificationCheckResult, ...]:
        hazards = assurance_case.hazard_index()
        missing_hazard_ids = tuple(
            hazard_id for hazard_id in scenario.hazard_ids if hazard_id not in hazards
        )

        if missing_hazard_ids:
            return (
                VerificationCheckResult(
                    check_id="scenario-hazard-coverage",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message=(
                        "Scenario references hazards missing from assurance case: "
                        + ", ".join(missing_hazard_ids)
                    ),
                ),
            )

        severe_hazards = tuple(
            hazards[hazard_id]
            for hazard_id in scenario.hazard_ids
            if hazard_id in hazards and hazards[hazard_id].requires_control()
        )
        uncovered_severe_hazard_ids = tuple(
            hazard.hazard_id for hazard in severe_hazards if not hazard.has_control_path()
        )

        if uncovered_severe_hazard_ids:
            return (
                VerificationCheckResult(
                    check_id="scenario-hazard-coverage",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message=(
                        "Scenario-covered severe hazards lack controls: "
                        + ", ".join(uncovered_severe_hazard_ids)
                    ),
                ),
            )

        return (
            VerificationCheckResult(
                check_id="scenario-hazard-coverage",
                result=VerificationResult.PASS,
                severity=VerificationIssueSeverity.INFO,
                message="Scenario hazard references are covered by the assurance case.",
            ),
        )

    @staticmethod
    def _verify_run_result(
        run_result: ScenarioRunResult,
    ) -> tuple[VerificationCheckResult, ...]:
        checks: list[VerificationCheckResult] = []

        if run_result.expected_behavior_satisfied:
            checks.append(
                VerificationCheckResult(
                    check_id="expected-safe-behavior",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Run result satisfies the expected safe behavior.",
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="expected-safe-behavior",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Run result does not satisfy the expected safe behavior.",
                )
            )

        if run_result.operator_review_required and run_result.final_decision.permits_nominal_execution():
            checks.append(
                VerificationCheckResult(
                    check_id="operator-review-consistency",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message=(
                        "Operator review is required even though the final decision permits "
                        "nominal execution; human authority evidence should be reviewed."
                    ),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="operator-review-consistency",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Operator review requirement is consistent with the run result.",
                )
            )

        return tuple(checks)

    @staticmethod
    def _verify_evidence_bundle(
        run_result: ScenarioRunResult,
    ) -> tuple[VerificationCheckResult, ...]:
        report = run_result.evidence_bundle.validate_integrity()
        record_ids = tuple(record.evidence_id for record in run_result.evidence_bundle.records)

        if report.errors:
            return (
                VerificationCheckResult(
                    check_id="evidence-bundle-integrity",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Evidence bundle integrity failed: " + "; ".join(report.errors),
                    evidence_ids=record_ids,
                ),
            )

        if report.warnings:
            return (
                VerificationCheckResult(
                    check_id="evidence-bundle-integrity",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Evidence bundle warnings require review: " + "; ".join(report.warnings),
                    evidence_ids=record_ids,
                ),
            )

        return (
            VerificationCheckResult(
                check_id="evidence-bundle-integrity",
                result=VerificationResult.PASS,
                severity=VerificationIssueSeverity.INFO,
                message="Evidence bundle integrity verified.",
                evidence_ids=record_ids,
            ),
        )

    def _verify_traceability(
        self,
        *,
        assurance_case: AssuranceCase,
        run_result: ScenarioRunResult,
        traceability_graph: TraceabilityGraph | None,
    ) -> tuple[VerificationCheckResult, ...]:
        if traceability_graph is None:
            if self.require_traceability:
                return (
                    VerificationCheckResult(
                        check_id="traceability-graph-present",
                        result=VerificationResult.FAIL,
                        severity=VerificationIssueSeverity.ERROR,
                        message="Traceability graph is required but was not provided.",
                    ),
                )

            return (
                VerificationCheckResult(
                    check_id="traceability-graph-present",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Traceability graph was not provided.",
                ),
            )

        checks: list[VerificationCheckResult] = []
        report = traceability_graph.validate()

        if report.errors:
            checks.append(
                VerificationCheckResult(
                    check_id="traceability-graph-valid",
                    result=VerificationResult.FAIL,
                    severity=VerificationIssueSeverity.ERROR,
                    message="Traceability graph validation failed: " + "; ".join(report.errors),
                )
            )
        elif report.warnings:
            checks.append(
                VerificationCheckResult(
                    check_id="traceability-graph-valid",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message="Traceability graph warnings require review: " + "; ".join(report.warnings),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="traceability-graph-valid",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message="Traceability graph is valid.",
                )
            )

        claim_ids = tuple(claim.claim_id for claim in assurance_case.claims)
        connected_claim_ids = tuple(
            claim_id
            for claim_id in claim_ids
            if traceability_graph.has_connected_path(run_result.scenario_id, claim_id)
        )

        if not connected_claim_ids:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-to-claim-trace",
                    result=VerificationResult.INCONCLUSIVE,
                    severity=VerificationIssueSeverity.WARNING,
                    message=(
                        f"Scenario {run_result.scenario_id!r} has no connected "
                        "traceability path to an assurance claim."
                    ),
                )
            )
        else:
            checks.append(
                VerificationCheckResult(
                    check_id="scenario-to-claim-trace",
                    result=VerificationResult.PASS,
                    severity=VerificationIssueSeverity.INFO,
                    message=(
                        "Scenario is connected to assurance claim(s): "
                        + ", ".join(connected_claim_ids)
                    ),
                )
            )

        return tuple(checks)
