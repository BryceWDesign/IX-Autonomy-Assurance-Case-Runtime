"""Scenario campaign execution and aggregate evidence reporting.

Scenario campaign records define the test plan and campaign validation proves the
plan is grounded. This module performs the first campaign-level execution pass:
it validates the campaign, executes each required scenario through the existing
scenario runner, aggregates pass/fail/inconclusive counts, applies the campaign
threshold, and emits a deterministic campaign evidence bundle.

The runner is local prototype infrastructure only. It does not claim operational
T&E approval, certification, deployment readiness, agency acceptance, or complete
adversarial-lab maturity.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    EvidenceStatus,
    RuntimeStrEnum,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord, JSONValue
from ix_autonomy_assurance_case_runtime.runner import (
    ScenarioRunInput,
    ScenarioRunner,
    ScenarioRunResult,
)
from ix_autonomy_assurance_case_runtime.safety_gate import RuntimeTelemetry
from ix_autonomy_assurance_case_runtime.scenario_campaign_validation import (
    ScenarioCampaignValidationReport,
    ScenarioCampaignValidator,
)
from ix_autonomy_assurance_case_runtime.scenario_campaigns import ScenarioCampaign
from ix_autonomy_assurance_case_runtime.scenarios import ScenarioCatalog
from ix_autonomy_assurance_case_runtime.telemetry import TelemetryReplayRecord


class ScenarioCampaignRunDecision(RuntimeStrEnum):
    """Aggregate decision emitted by a scenario campaign run."""

    ACCEPTED = "accepted"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    BLOCKED = "blocked"

    def supports_acceptance(self) -> bool:
        """Return whether the campaign run can support an acceptance claim."""

        return self is ScenarioCampaignRunDecision.ACCEPTED

    def requires_follow_up(self) -> bool:
        """Return whether the campaign needs investigation or another run."""

        return self in {
            ScenarioCampaignRunDecision.FAILED,
            ScenarioCampaignRunDecision.INCONCLUSIVE,
            ScenarioCampaignRunDecision.BLOCKED,
        }


@dataclass(frozen=True, slots=True)
class ScenarioCampaignRunInput:
    """Input required to execute a scenario campaign."""

    campaign_run_id: str
    case_id: str
    campaign_id: str
    telemetry_by_scenario_id: dict[str, RuntimeTelemetry]
    prior_evidence_bundles: tuple[EvidenceBundle, ...] = field(default_factory=tuple)
    operator_id: str = "unassigned-operator"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate campaign run input."""

        object.__setattr__(
            self,
            "campaign_run_id",
            _require_identifier(self.campaign_run_id, "campaign_run_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(
            self,
            "campaign_id",
            _require_identifier(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(self, "operator_id", _require_text(self.operator_id, "operator_id"))
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        if not self.telemetry_by_scenario_id:
            raise ContractValueError("telemetry_by_scenario_id must not be empty.")
        normalized_telemetry: dict[str, RuntimeTelemetry] = {}
        for scenario_id, telemetry in self.telemetry_by_scenario_id.items():
            normalized_id = _require_identifier(scenario_id, "telemetry scenario_id")
            normalized_telemetry[normalized_id] = telemetry
        object.__setattr__(
            self,
            "telemetry_by_scenario_id",
            dict(sorted(normalized_telemetry.items())),
        )


@dataclass(frozen=True, slots=True)
class ScenarioCampaignRunReport:
    """Aggregate report for one executed scenario campaign."""

    campaign_run_id: str
    case_id: str
    campaign_id: str
    decision: ScenarioCampaignRunDecision
    validation_report: ScenarioCampaignValidationReport
    scenario_results: tuple[ScenarioRunResult, ...]
    evidence_bundle: EvidenceBundle
    rationale: str

    def __post_init__(self) -> None:
        """Validate campaign run report fields."""

        object.__setattr__(
            self,
            "campaign_run_id",
            _require_identifier(self.campaign_run_id, "campaign_run_id"),
        )
        object.__setattr__(self, "case_id", _require_identifier(self.case_id, "case_id"))
        object.__setattr__(
            self,
            "campaign_id",
            _require_identifier(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))

    @property
    def total_count(self) -> int:
        """Return the number of executed scenario runs."""

        return len(self.scenario_results)

    @property
    def pass_count(self) -> int:
        """Return the number of scenario runs that passed."""

        return self._count_result(VerificationResult.PASS)

    @property
    def fail_count(self) -> int:
        """Return the number of scenario runs that failed."""

        return self._count_result(VerificationResult.FAIL)

    @property
    def inconclusive_count(self) -> int:
        """Return the number of inconclusive or not-run scenario outcomes."""

        return sum(
            1
            for result in self.scenario_results
            if result.verification_result in {
                VerificationResult.INCONCLUSIVE,
                VerificationResult.NOT_RUN,
            }
        )

    def is_accepted(self) -> bool:
        """Return whether the campaign was accepted by its threshold."""

        return self.decision.supports_acceptance()

    def requires_follow_up(self) -> bool:
        """Return whether the campaign run requires follow-up."""

        return self.decision.requires_follow_up()

    def failed_scenario_ids(self) -> tuple[str, ...]:
        """Return scenario IDs that produced failed verification results."""

        return tuple(
            result.scenario_id
            for result in self.scenario_results
            if result.verification_result is VerificationResult.FAIL
        )

    def scenario_result_for_run_id(self, run_id: str) -> ScenarioRunResult | None:
        """Return a scenario result by run ID."""

        normalized_run_id = _require_identifier(run_id, "run_id")
        for result in self.scenario_results:
            if result.run_id == normalized_run_id:
                return result
        return None

    def summary(self) -> str:
        """Return a deterministic campaign run summary."""

        return (
            f"scenario-campaign-run: {self.decision.value} "
            f"({self.pass_count} pass, {self.fail_count} fail, "
            f"{self.inconclusive_count} inconclusive, total={self.total_count})"
        )

    def to_evidence_payload(self) -> dict[str, JSONValue]:
        """Return a JSON-compatible campaign run payload."""

        return {
            "campaign_id": self.campaign_id,
            "campaign_run_id": self.campaign_run_id,
            "case_id": self.case_id,
            "decision": self.decision.value,
            "failed_scenario_ids": list(self.failed_scenario_ids()),
            "inconclusive_count": self.inconclusive_count,
            "pass_count": self.pass_count,
            "fail_count": self.fail_count,
            "rationale": self.rationale,
            "scenario_results": [
                {
                    "authority_state": result.final_authority_state.value,
                    "decision": result.final_decision.value,
                    "evidence_bundle_id": result.evidence_bundle.bundle_id,
                    "operator_review_required": result.operator_review_required,
                    "run_id": result.run_id,
                    "scenario_id": result.scenario_id,
                    "verification_result": result.verification_result.value,
                }
                for result in self.scenario_results
            ],
            "total_count": self.total_count,
            "validation_blocker_count": self.validation_report.blocker_count,
            "validation_warning_count": self.validation_report.warning_count,
        }

    def _count_result(self, verification_result: VerificationResult) -> int:
        """Return count for one verification result."""

        return sum(
            1
            for result in self.scenario_results
            if result.verification_result is verification_result
        )


@dataclass(frozen=True, slots=True)
class ScenarioCampaignRunner:
    """Run validated scenario campaigns through the scenario runner."""

    scenario_runner: ScenarioRunner = field(default_factory=ScenarioRunner)
    evidence_created_by: str = "ix-scenario-campaign-runner"

    def __post_init__(self) -> None:
        """Validate campaign runner settings."""

        object.__setattr__(
            self,
            "evidence_created_by",
            _require_text(self.evidence_created_by, "evidence_created_by"),
        )

    def run(
        self,
        *,
        campaign: ScenarioCampaign,
        scenario_catalog: ScenarioCatalog,
        run_input: ScenarioCampaignRunInput,
        evidence_bundles: tuple[EvidenceBundle, ...] = (),
        replay_records: tuple[TelemetryReplayRecord, ...] = (),
    ) -> ScenarioCampaignRunReport:
        """Execute a scenario campaign and return aggregate evidence."""

        if run_input.campaign_id != campaign.campaign_id:
            raise ContractValueError(
                "campaign run input campaign_id must match campaign.campaign_id."
            )

        validation_report = ScenarioCampaignValidator(
            scenario_catalog,
            evidence_bundles=evidence_bundles,
            replay_records=replay_records,
        ).validate(campaign)
        if not validation_report.is_execution_ready():
            return self._blocked_report(
                campaign=campaign,
                run_input=run_input,
                validation_report=validation_report,
                rationale=(
                    "Campaign validation contains blockers; scenario execution was not started."
                ),
            )

        missing_telemetry_ids = tuple(
            scenario.scenario_id
            for scenario in campaign.scenarios
            if scenario.scenario_id not in run_input.telemetry_by_scenario_id
        )
        if missing_telemetry_ids:
            return self._blocked_report(
                campaign=campaign,
                run_input=run_input,
                validation_report=validation_report,
                rationale=(
                    "Campaign run input is missing telemetry for scenario(s): "
                    + ", ".join(missing_telemetry_ids)
                ),
            )

        scenario_results: list[ScenarioRunResult] = []
        for campaign_scenario in campaign.scenarios:
            telemetry = run_input.telemetry_by_scenario_id[campaign_scenario.scenario_id]
            for run_index in range(1, campaign_scenario.minimum_runs + 1):
                scenario_results.append(
                    self.scenario_runner.run(
                        catalog=scenario_catalog,
                        run_input=ScenarioRunInput(
                            run_id=(
                                f"{run_input.campaign_run_id}-"
                                f"{campaign_scenario.scenario_id}-{run_index}"
                            ),
                            case_id=run_input.case_id,
                            scenario_id=campaign_scenario.scenario_id,
                            telemetry=telemetry,
                            prior_evidence_bundles=run_input.prior_evidence_bundles,
                            operator_id=run_input.operator_id,
                            notes=run_input.notes,
                        ),
                    )
                )

        decision, rationale = _decide_campaign_run(campaign, tuple(scenario_results))
        return self._build_report(
            campaign=campaign,
            run_input=run_input,
            validation_report=validation_report,
            scenario_results=tuple(scenario_results),
            decision=decision,
            rationale=rationale,
        )

    def _blocked_report(
        self,
        *,
        campaign: ScenarioCampaign,
        run_input: ScenarioCampaignRunInput,
        validation_report: ScenarioCampaignValidationReport,
        rationale: str,
    ) -> ScenarioCampaignRunReport:
        """Build a blocked campaign report with deterministic evidence."""

        return self._build_report(
            campaign=campaign,
            run_input=run_input,
            validation_report=validation_report,
            scenario_results=(),
            decision=ScenarioCampaignRunDecision.BLOCKED,
            rationale=rationale,
        )

    def _build_report(
        self,
        *,
        campaign: ScenarioCampaign,
        run_input: ScenarioCampaignRunInput,
        validation_report: ScenarioCampaignValidationReport,
        scenario_results: tuple[ScenarioRunResult, ...],
        decision: ScenarioCampaignRunDecision,
        rationale: str,
    ) -> ScenarioCampaignRunReport:
        """Build a campaign report and attach a hashed evidence bundle."""

        provisional = ScenarioCampaignRunReport(
            campaign_run_id=run_input.campaign_run_id,
            case_id=run_input.case_id,
            campaign_id=campaign.campaign_id,
            decision=decision,
            validation_report=validation_report,
            scenario_results=scenario_results,
            evidence_bundle=EvidenceBundle(
                bundle_id=f"BND-{run_input.campaign_run_id}",
                case_id=run_input.case_id,
                records=(
                    EvidenceRecord(
                        evidence_id=f"EV-CAMPAIGN-RUN-{run_input.campaign_run_id}",
                        kind="scenario-campaign-run",
                        source=f"campaign:{campaign.campaign_id}",
                        payload={},
                        status=EvidenceStatus.ACCEPTED,
                        created_by=self.evidence_created_by,
                        tags=("scenario-campaign-run", campaign.campaign_id),
                    ),
                ),
                created_by=self.evidence_created_by,
            ),
            rationale=rationale,
        )
        evidence_bundle = EvidenceBundle(
            bundle_id=f"BND-{run_input.campaign_run_id}",
            case_id=run_input.case_id,
            records=(
                EvidenceRecord(
                    evidence_id=f"EV-CAMPAIGN-RUN-{run_input.campaign_run_id}",
                    kind="scenario-campaign-run",
                    source=f"campaign:{campaign.campaign_id}",
                    payload=provisional.to_evidence_payload(),
                    status=EvidenceStatus.ACCEPTED,
                    created_by=self.evidence_created_by,
                    tags=("scenario-campaign-run", campaign.campaign_id),
                ),
            ),
            created_by=self.evidence_created_by,
        ).with_computed_hashes()
        return ScenarioCampaignRunReport(
            campaign_run_id=provisional.campaign_run_id,
            case_id=provisional.case_id,
            campaign_id=provisional.campaign_id,
            decision=provisional.decision,
            validation_report=provisional.validation_report,
            scenario_results=provisional.scenario_results,
            evidence_bundle=evidence_bundle,
            rationale=provisional.rationale,
        )


def _decide_campaign_run(
    campaign: ScenarioCampaign,
    scenario_results: tuple[ScenarioRunResult, ...],
) -> tuple[ScenarioCampaignRunDecision, str]:
    """Return the aggregate decision and rationale for campaign results."""

    if not scenario_results:
        return ScenarioCampaignRunDecision.BLOCKED, "Campaign executed zero scenario runs."

    pass_count = sum(
        1 for result in scenario_results if result.verification_result is VerificationResult.PASS
    )
    fail_count = sum(
        1 for result in scenario_results if result.verification_result is VerificationResult.FAIL
    )
    inconclusive_count = sum(
        1
        for result in scenario_results
        if result.verification_result
        in {VerificationResult.INCONCLUSIVE, VerificationResult.NOT_RUN}
    )
    total_count = len(scenario_results)
    threshold_accepts = campaign.acceptance_threshold.accepts_counts(
        pass_count=pass_count,
        fail_count=fail_count,
        inconclusive_count=inconclusive_count,
        total_count=total_count,
    )
    if not threshold_accepts:
        return (
            ScenarioCampaignRunDecision.FAILED,
            "Campaign results failed the configured acceptance threshold.",
        )

    if campaign.acceptance_threshold.require_all_critical_scenarios_pass:
        non_passing_critical_ids = tuple(
            result.scenario_id
            for result in scenario_results
            if _campaign_scenario_requires_critical_pass(campaign, result.scenario_id)
            and result.verification_result is not VerificationResult.PASS
        )
        if non_passing_critical_ids:
            return (
                ScenarioCampaignRunDecision.FAILED,
                "Critical campaign scenario(s) did not pass: "
                + ", ".join(non_passing_critical_ids),
            )

    if inconclusive_count:
        return (
            ScenarioCampaignRunDecision.INCONCLUSIVE,
            "Campaign threshold allowed execution, but at least one scenario was inconclusive.",
        )

    return (
        ScenarioCampaignRunDecision.ACCEPTED,
        "Campaign scenario results satisfy the configured acceptance threshold.",
    )


def _campaign_scenario_requires_critical_pass(
    campaign: ScenarioCampaign,
    scenario_id: str,
) -> bool:
    """Return whether a campaign scenario must pass under critical-scenario policy."""

    return any(
        campaign_scenario.scenario_id == scenario_id and campaign_scenario.role.is_non_nominal()
        for campaign_scenario in campaign.scenarios
    )


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Normalize text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != normalized:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized
