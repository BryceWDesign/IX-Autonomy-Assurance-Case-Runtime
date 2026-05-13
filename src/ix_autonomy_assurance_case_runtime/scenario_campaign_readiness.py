"""Scenario campaign runner readiness decision surface.

Campaign records, validation, and execution reports are only enough to support
prototype maturity when the campaign evidence proves clean execution, accepted
threshold outcomes, adversarial or otherwise non-nominal coverage, and valid
hashed campaign evidence. This module turns those checks into a capability gate
for the ``scenario-campaign-runner`` target.

The checks are local prototype checks only. They do not claim operational T&E
approval, certification, authority to operate, deployment readiness, or agency
acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.scenario_campaign_runner import (
    ScenarioCampaignRunDecision,
    ScenarioCampaignRunReport,
)
from ix_autonomy_assurance_case_runtime.scenario_campaigns import ScenarioCampaign

SCENARIO_CAMPAIGN_CAPABILITY_ID = "scenario-campaign-runner"


class ScenarioCampaignReadinessDecision(RuntimeStrEnum):
    """Decision for whether scenario campaigns can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the scenario-campaign capability."""

        return self is ScenarioCampaignReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks campaign-based maturity progress."""

        return self is ScenarioCampaignReadinessDecision.BLOCKED


class ScenarioCampaignReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized scenario-campaign readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks campaign capability completion."""

        return self is ScenarioCampaignReadinessFindingSeverity.BLOCKER


class ScenarioCampaignReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a scenario-campaign readiness finding."""

    CAMPAIGN = "campaign"
    RUN_REPORT = "run_report"
    EVIDENCE = "evidence"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class ScenarioCampaignReadinessFinding:
    """One normalized scenario-campaign readiness finding."""

    finding_id: str
    severity: ScenarioCampaignReadinessFindingSeverity
    source: ScenarioCampaignReadinessFindingSource
    message: str
    campaign_id: str | None = None
    campaign_run_id: str | None = None
    scenario_id: str | None = None
    evidence_bundle_id: str | None = None

    def __post_init__(self) -> None:
        """Validate readiness finding fields."""

        _require_identifier(self.finding_id, "scenario campaign readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Scenario campaign readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("campaign_id", self.campaign_id),
            ("campaign_run_id", self.campaign_run_id),
            ("scenario_id", self.scenario_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ScenarioCampaignLayerReadinessReport:
    """Combined readiness report for the scenario-campaign capability layer."""

    decision: ScenarioCampaignReadinessDecision
    campaign_count: int
    run_report_count: int
    findings: tuple[ScenarioCampaignReadinessFinding, ...]
    capability_id: str = SCENARIO_CAMPAIGN_CAPABILITY_ID

    def __post_init__(self) -> None:
        """Validate report counters."""

        if self.campaign_count < 0:
            raise ContractValueError("campaign_count must not be negative.")
        if self.run_report_count < 0:
            raise ContractValueError("run_report_count must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return normalized blocker count."""

        return sum(finding.severity.blocks_completion() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return normalized warning count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ScenarioCampaignReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether scenario campaigns can count as complete."""

        return self.decision.supports_capability_completion()

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this readiness report can honestly mark complete."""

        if not self.is_complete():
            return ()
        return (self.capability_id,)

    def prototype_readiness_report(
        self,
        requested_claim_level: PrototypeClaimLevel,
        existing_completed_capability_ids: Iterable[str] = (),
    ) -> PrototypeReadinessReport:
        """Evaluate prototype claim readiness with campaign completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_campaign(
        self,
        campaign_id: str,
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Return findings for a campaign ID."""

        return tuple(finding for finding in self.findings if finding.campaign_id == campaign_id)

    def findings_for_run(
        self,
        campaign_run_id: str,
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Return findings for a campaign run ID."""

        return tuple(
            finding for finding in self.findings if finding.campaign_run_id == campaign_run_id
        )

    def findings_for_scenario(
        self,
        scenario_id: str,
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Return findings for a scenario ID."""

        return tuple(finding for finding in self.findings if finding.scenario_id == scenario_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def summary(self) -> str:
        """Return a deterministic scenario-campaign readiness summary."""

        return (
            f"scenario-campaign-readiness: {self.decision.value} "
            f"({self.campaign_count} campaign(s), {self.run_report_count} run report(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class ScenarioCampaignLayerReadinessEvaluator:
    """Evaluate whether scenario campaigns can count toward prototype maturity."""

    def evaluate(
        self,
        campaigns: Iterable[ScenarioCampaign],
        run_reports: Iterable[ScenarioCampaignRunReport],
    ) -> ScenarioCampaignLayerReadinessReport:
        """Evaluate campaign plans and run reports as one completion surface."""

        campaign_tuple = tuple(campaigns)
        run_report_tuple = tuple(run_reports)
        campaign_by_id = _index_campaigns(campaign_tuple)
        run_reports_by_campaign = _group_run_reports_by_campaign(run_report_tuple)
        findings = (
            self._build_readiness_findings(campaign_tuple, run_report_tuple)
            + self._build_campaign_coverage_findings(campaign_by_id, run_reports_by_campaign)
            + self._build_run_report_findings(campaign_by_id, run_report_tuple)
        )
        return ScenarioCampaignLayerReadinessReport(
            decision=self._decide(findings),
            campaign_count=len(campaign_tuple),
            run_report_count=len(run_report_tuple),
            findings=findings,
        )

    @staticmethod
    def _build_readiness_findings(
        campaigns: tuple[ScenarioCampaign, ...],
        run_reports: tuple[ScenarioCampaignRunReport, ...],
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Build direct readiness findings."""

        findings: list[ScenarioCampaignReadinessFinding] = []
        if not campaigns:
            findings.append(
                ScenarioCampaignReadinessFinding(
                    finding_id="scenario-campaign-readiness-no-campaigns",
                    severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                    source=ScenarioCampaignReadinessFindingSource.READINESS,
                    message="Scenario campaign readiness requires at least one campaign plan.",
                )
            )
        if not run_reports:
            findings.append(
                ScenarioCampaignReadinessFinding(
                    finding_id="scenario-campaign-readiness-no-run-reports",
                    severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                    source=ScenarioCampaignReadinessFindingSource.READINESS,
                    message=(
                        "Scenario campaign readiness requires at least one "
                        "campaign run report."
                    ),
                )
            )
        if campaigns and not any(campaign.has_non_nominal_coverage() for campaign in campaigns):
            findings.append(
                ScenarioCampaignReadinessFinding(
                    finding_id="scenario-campaign-readiness-no-non-nominal-coverage",
                    severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                    source=ScenarioCampaignReadinessFindingSource.READINESS,
                    message=(
                        "Scenario campaign readiness requires adversarial, degraded-mode, "
                        "or stress coverage."
                    ),
                )
            )
        if campaigns and not any(campaign.has_adversarial_coverage() for campaign in campaigns):
            findings.append(
                ScenarioCampaignReadinessFinding(
                    finding_id="scenario-campaign-readiness-no-adversarial-coverage",
                    severity=ScenarioCampaignReadinessFindingSeverity.WARNING,
                    source=ScenarioCampaignReadinessFindingSource.READINESS,
                    message=(
                        "Scenario campaign layer has non-nominal coverage but lacks explicit "
                        "adversarial probe coverage."
                    ),
                )
            )
        return tuple(findings)

    @staticmethod
    def _build_campaign_coverage_findings(
        campaign_by_id: dict[str, ScenarioCampaign],
        run_reports_by_campaign: dict[str, tuple[ScenarioCampaignRunReport, ...]],
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Validate that each campaign has an accepted run report."""

        findings: list[ScenarioCampaignReadinessFinding] = []
        for campaign_id, campaign in campaign_by_id.items():
            reports = run_reports_by_campaign.get(campaign_id, ())
            if not reports:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"campaign-{campaign_id}-missing-run-report",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.CAMPAIGN,
                        message="Scenario campaign has no run report.",
                        campaign_id=campaign_id,
                    )
                )
                continue
            if not any(report.is_accepted() for report in reports):
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"campaign-{campaign_id}-no-accepted-run",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.CAMPAIGN,
                        message="Scenario campaign has no accepted run report.",
                        campaign_id=campaign_id,
                    )
                )
            for campaign_scenario in campaign.scenarios:
                if not any(
                    _run_report_covers_scenario(report, campaign_scenario.scenario_id)
                    for report in reports
                ):
                    findings.append(
                        ScenarioCampaignReadinessFinding(
                            finding_id=(
                                f"campaign-{campaign_id}-scenario-"
                                f"{campaign_scenario.scenario_id}-not-run"
                            ),
                            severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                            source=ScenarioCampaignReadinessFindingSource.CAMPAIGN,
                            message=(
                                "Campaign scenario is not represented by any campaign run report."
                            ),
                            campaign_id=campaign_id,
                            scenario_id=campaign_scenario.scenario_id,
                        )
                    )
        return tuple(findings)

    @staticmethod
    def _build_run_report_findings(
        campaign_by_id: dict[str, ScenarioCampaign],
        run_reports: tuple[ScenarioCampaignRunReport, ...],
    ) -> tuple[ScenarioCampaignReadinessFinding, ...]:
        """Validate campaign run report decisions, validation posture, and evidence."""

        findings: list[ScenarioCampaignReadinessFinding] = []
        seen_run_ids: set[str] = set()
        for report in run_reports:
            if report.campaign_run_id in seen_run_ids:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-duplicate",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Duplicate campaign run report ID.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            seen_run_ids.add(report.campaign_run_id)

            if report.campaign_id not in campaign_by_id:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-unknown-campaign",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Campaign run report references an unknown campaign.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            if report.decision is not ScenarioCampaignRunDecision.ACCEPTED:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-decision-{report.decision.value}",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Campaign run report is not accepted by its threshold.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            if report.total_count <= 0:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-no-scenario-results",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Campaign run report has no executed scenario results.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            if report.validation_report.blocker_count:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-validation-blockers",
                        severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Campaign run report contains validation blockers.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            if report.validation_report.warning_count:
                findings.append(
                    ScenarioCampaignReadinessFinding(
                        finding_id=f"run-{report.campaign_run_id}-validation-warnings",
                        severity=ScenarioCampaignReadinessFindingSeverity.WARNING,
                        source=ScenarioCampaignReadinessFindingSource.RUN_REPORT,
                        message="Campaign run report contains validation warnings.",
                        campaign_id=report.campaign_id,
                        campaign_run_id=report.campaign_run_id,
                    )
                )
            findings.extend(_evidence_findings_for_report(report))
        return tuple(findings)

    @staticmethod
    def _decide(
        findings: tuple[ScenarioCampaignReadinessFinding, ...],
    ) -> ScenarioCampaignReadinessDecision:
        """Return the combined scenario-campaign readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return ScenarioCampaignReadinessDecision.BLOCKED
        if any(
            finding.severity is ScenarioCampaignReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return ScenarioCampaignReadinessDecision.LIMITED
        return ScenarioCampaignReadinessDecision.COMPLETE


def _index_campaigns(campaigns: tuple[ScenarioCampaign, ...]) -> dict[str, ScenarioCampaign]:
    """Index campaigns and reject duplicate campaign IDs."""

    indexed: dict[str, ScenarioCampaign] = {}
    for campaign in campaigns:
        if campaign.campaign_id in indexed:
            raise ContractValueError(
                f"Duplicate scenario campaign readiness campaign ID {campaign.campaign_id!r}."
            )
        indexed[campaign.campaign_id] = campaign
    return indexed


def _group_run_reports_by_campaign(
    run_reports: tuple[ScenarioCampaignRunReport, ...],
) -> dict[str, tuple[ScenarioCampaignRunReport, ...]]:
    """Group run reports by campaign ID."""

    grouped: dict[str, list[ScenarioCampaignRunReport]] = {}
    for report in run_reports:
        grouped.setdefault(report.campaign_id, []).append(report)
    return {campaign_id: tuple(items) for campaign_id, items in grouped.items()}


def _run_report_covers_scenario(report: ScenarioCampaignRunReport, scenario_id: str) -> bool:
    """Return whether a campaign run report includes a scenario result."""

    return any(result.scenario_id == scenario_id for result in report.scenario_results)


def _evidence_findings_for_report(
    report: ScenarioCampaignRunReport,
) -> tuple[ScenarioCampaignReadinessFinding, ...]:
    """Validate campaign run evidence bundle integrity."""

    validation = report.evidence_bundle.validate_integrity()
    findings: list[ScenarioCampaignReadinessFinding] = []
    if validation.errors:
        findings.append(
            ScenarioCampaignReadinessFinding(
                finding_id=f"run-{report.campaign_run_id}-evidence-integrity-error",
                severity=ScenarioCampaignReadinessFindingSeverity.BLOCKER,
                source=ScenarioCampaignReadinessFindingSource.EVIDENCE,
                message="; ".join(validation.errors),
                campaign_id=report.campaign_id,
                campaign_run_id=report.campaign_run_id,
                evidence_bundle_id=report.evidence_bundle.bundle_id,
            )
        )
    for warning_index, warning in enumerate(validation.warnings, start=1):
        findings.append(
            ScenarioCampaignReadinessFinding(
                finding_id=f"run-{report.campaign_run_id}-evidence-warning-{warning_index}",
                severity=ScenarioCampaignReadinessFindingSeverity.WARNING,
                source=ScenarioCampaignReadinessFindingSource.EVIDENCE,
                message=warning,
                campaign_id=report.campaign_id,
                campaign_run_id=report.campaign_run_id,
                evidence_bundle_id=report.evidence_bundle.bundle_id,
            )
        )
    return tuple(findings)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable scenario-campaign readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
