"""Scenario campaign validation against catalogs, evidence, and replay bounds.

Campaign records define the intended multi-scenario test plan. This validator
checks whether that plan is grounded in the local scenario catalog, evidence
bundles, and telemetry replay records before later commits execute campaign runs
or count the scenario-campaign capability as complete.

The checks are local prototype checks only. They do not claim operational test
approval, certification, deployment readiness, or agency acceptance.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    RuntimeStrEnum,
    VerificationResult,
)
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.scenario_campaigns import (
    ScenarioCampaign,
    ScenarioCampaignScenario,
)
from ix_autonomy_assurance_case_runtime.scenarios import ScenarioCatalog
from ix_autonomy_assurance_case_runtime.telemetry import TelemetryReplayRecord


class ScenarioCampaignFindingSeverity(RuntimeStrEnum):
    """Severity for scenario campaign validation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_execution(self) -> bool:
        """Return whether this finding blocks campaign execution readiness."""

        return self is ScenarioCampaignFindingSeverity.BLOCKER


class ScenarioCampaignFindingSource(RuntimeStrEnum):
    """Subsystem that produced a scenario campaign validation finding."""

    CAMPAIGN = "campaign"
    SCENARIO_CATALOG = "scenario_catalog"
    EVIDENCE = "evidence"
    REPLAY = "replay"


@dataclass(frozen=True, slots=True)
class ScenarioCampaignValidationFinding:
    """One scenario campaign validation finding."""

    finding_id: str
    severity: ScenarioCampaignFindingSeverity
    source: ScenarioCampaignFindingSource
    message: str
    campaign_id: str | None = None
    scenario_id: str | None = None
    requirement_id: str | None = None
    hazard_id: str | None = None
    evidence_bundle_id: str | None = None
    replay_record_id: str | None = None

    def __post_init__(self) -> None:
        """Validate finding fields."""

        _require_identifier(self.finding_id, "scenario campaign finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Scenario campaign finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("campaign_id", self.campaign_id),
            ("scenario_id", self.scenario_id),
            ("requirement_id", self.requirement_id),
            ("hazard_id", self.hazard_id),
            ("evidence_bundle_id", self.evidence_bundle_id),
            ("replay_record_id", self.replay_record_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class ScenarioCampaignValidationReport:
    """Validation report for one scenario campaign."""

    campaign_id: str
    scenario_count: int
    evidence_bundle_count: int
    replay_record_count: int
    findings: tuple[ScenarioCampaignValidationFinding, ...]

    def __post_init__(self) -> None:
        """Validate report counters."""

        _require_identifier(self.campaign_id, "campaign_id")
        for field_name, value in (
            ("scenario_count", self.scenario_count),
            ("evidence_bundle_count", self.evidence_bundle_count),
            ("replay_record_count", self.replay_record_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

    @property
    def blocker_count(self) -> int:
        """Return blocker finding count."""

        return sum(finding.severity.blocks_execution() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return warning finding count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is ScenarioCampaignFindingSeverity.WARNING
        )

    def is_execution_ready(self) -> bool:
        """Return whether campaign validation has no execution blockers."""

        return self.blocker_count == 0

    def findings_for_scenario(
        self,
        scenario_id: str,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Return findings for a scenario ID."""

        return tuple(finding for finding in self.findings if finding.scenario_id == scenario_id)

    def findings_for_evidence_bundle(
        self,
        evidence_bundle_id: str,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Return findings for an evidence bundle ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.evidence_bundle_id == evidence_bundle_id
        )

    def findings_for_replay_record(
        self,
        replay_record_id: str,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Return findings for a replay record ID."""

        return tuple(
            finding for finding in self.findings if finding.replay_record_id == replay_record_id
        )

    def findings_for_requirement(
        self,
        requirement_id: str,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Return findings for a requirement ID."""

        return tuple(
            finding for finding in self.findings if finding.requirement_id == requirement_id
        )

    def findings_for_hazard(self, hazard_id: str) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Return findings for a hazard ID."""

        return tuple(finding for finding in self.findings if finding.hazard_id == hazard_id)

    def summary(self) -> str:
        """Return a deterministic campaign-validation summary."""

        return (
            f"scenario-campaign-validation: {self.campaign_id} "
            f"({self.scenario_count} scenario(s), "
            f"{self.evidence_bundle_count} evidence bundle(s), "
            f"{self.replay_record_count} replay record(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class ScenarioCampaignValidator:
    """Validate scenario campaigns against local catalogs and evidence."""

    def __init__(
        self,
        scenario_catalog: ScenarioCatalog,
        evidence_bundles: Iterable[EvidenceBundle] = (),
        replay_records: Iterable[TelemetryReplayRecord] = (),
    ) -> None:
        """Create a campaign validator."""

        self._scenario_catalog = scenario_catalog
        self._bundle_by_id = self._index_evidence_bundles(evidence_bundles)
        self._replay_by_id = self._index_replay_records(replay_records)

    def validate(self, campaign: ScenarioCampaign) -> ScenarioCampaignValidationReport:
        """Validate a scenario campaign plan."""

        findings = (
            self._validate_campaign_posture(campaign)
            + self._validate_scenario_catalog(campaign)
            + self._validate_evidence(campaign)
            + self._validate_replay_records(campaign)
        )
        return ScenarioCampaignValidationReport(
            campaign_id=campaign.campaign_id,
            scenario_count=len(campaign.scenarios),
            evidence_bundle_count=len(campaign.required_evidence_bundle_ids()),
            replay_record_count=len(campaign.required_replay_record_ids()),
            findings=findings,
        )

    @staticmethod
    def _index_evidence_bundles(
        bundles: Iterable[EvidenceBundle],
    ) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate bundle IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(
                    f"Duplicate scenario campaign evidence bundle ID {bundle.bundle_id!r}."
                )
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _index_replay_records(
        replay_records: Iterable[TelemetryReplayRecord],
    ) -> dict[str, TelemetryReplayRecord]:
        """Index replay records and reject duplicate replay record IDs."""

        indexed: dict[str, TelemetryReplayRecord] = {}
        for replay_record in replay_records:
            if replay_record.replay_record_id in indexed:
                raise ContractValueError(
                    "Duplicate scenario campaign replay record ID "
                    f"{replay_record.replay_record_id!r}."
                )
            indexed[replay_record.replay_record_id] = replay_record
        return indexed

    @staticmethod
    def _validate_campaign_posture(
        campaign: ScenarioCampaign,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Validate campaign-level execution posture."""

        findings: list[ScenarioCampaignValidationFinding] = []
        if not campaign.status.can_execute():
            findings.append(
                ScenarioCampaignValidationFinding(
                    finding_id=f"campaign-{campaign.campaign_id}-not-executable",
                    severity=ScenarioCampaignFindingSeverity.BLOCKER,
                    source=ScenarioCampaignFindingSource.CAMPAIGN,
                    message="Scenario campaign status does not permit local execution.",
                    campaign_id=campaign.campaign_id,
                )
            )
        if not campaign.has_non_nominal_coverage():
            findings.append(
                ScenarioCampaignValidationFinding(
                    finding_id=f"campaign-{campaign.campaign_id}-no-non-nominal-coverage",
                    severity=ScenarioCampaignFindingSeverity.WARNING,
                    source=ScenarioCampaignFindingSource.CAMPAIGN,
                    message=(
                        "Scenario campaign has no adversarial, degraded-mode, or stress "
                        "coverage."
                    ),
                    campaign_id=campaign.campaign_id,
                )
            )
        for campaign_scenario in campaign.scenarios:
            if (
                campaign_scenario.role.is_non_nominal()
                and campaign_scenario.expected_result is not VerificationResult.PASS
            ):
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=(
                            f"scenario-{campaign_scenario.scenario_id}-non-nominal-"
                            "expected-not-pass"
                        ),
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.CAMPAIGN,
                        message=(
                            "Non-nominal campaign scenarios must expect PASS for the safe "
                            "behavior check, not false acceptance of unsafe behavior."
                        ),
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                    )
                )
            if (
                campaign.acceptance_threshold.require_evidence_for_each_scenario
                and not campaign_scenario.evidence_bundle_ids
            ):
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"scenario-{campaign_scenario.scenario_id}-missing-evidence",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.CAMPAIGN,
                        message="Campaign threshold requires evidence for each scenario.",
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                    )
                )
        return tuple(findings)

    def _validate_scenario_catalog(
        self,
        campaign: ScenarioCampaign,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Validate campaign references against the scenario catalog."""

        findings: list[ScenarioCampaignValidationFinding] = []
        catalog_report = self._scenario_catalog.validate_references()
        findings.extend(
            ScenarioCampaignValidationFinding(
                finding_id=f"scenario-catalog-error-{index}",
                severity=ScenarioCampaignFindingSeverity.BLOCKER,
                source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                message=error,
                campaign_id=campaign.campaign_id,
            )
            for index, error in enumerate(catalog_report.errors, start=1)
        )
        findings.extend(
            ScenarioCampaignValidationFinding(
                finding_id=f"scenario-catalog-warning-{index}",
                severity=ScenarioCampaignFindingSeverity.WARNING,
                source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                message=warning,
                campaign_id=campaign.campaign_id,
            )
            for index, warning in enumerate(catalog_report.warnings, start=1)
        )

        mission_threads = self._scenario_catalog.mission_thread_index()
        scenarios = self._scenario_catalog.scenario_index()
        mission_thread = mission_threads.get(campaign.mission_thread_id)
        if mission_thread is None:
            findings.append(
                ScenarioCampaignValidationFinding(
                    finding_id=f"campaign-{campaign.campaign_id}-missing-mission-thread",
                    severity=ScenarioCampaignFindingSeverity.BLOCKER,
                    source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                    message="Scenario campaign references a missing mission thread.",
                    campaign_id=campaign.campaign_id,
                )
            )
        for campaign_scenario in campaign.scenarios:
            scenario = scenarios.get(campaign_scenario.scenario_id)
            if scenario is None:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"scenario-{campaign_scenario.scenario_id}-missing",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                        message="Campaign scenario is missing from the scenario catalog.",
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                    )
                )
                continue
            if scenario.mission_thread_id != campaign.mission_thread_id:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"scenario-{scenario.scenario_id}-mission-thread-mismatch",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                        message="Campaign scenario does not belong to the campaign mission thread.",
                        campaign_id=campaign.campaign_id,
                        scenario_id=scenario.scenario_id,
                    )
                )
            findings.extend(
                self._validate_scenario_trace_links(
                    campaign=campaign,
                    campaign_scenario=campaign_scenario,
                    mission_requirement_ids=mission_thread.requirement_ids
                    if mission_thread is not None
                    else (),
                    mission_hazard_ids=(
                        mission_thread.hazard_ids if mission_thread is not None else ()
                    ),
                    scenario_hazard_ids=scenario.hazard_ids,
                )
            )
        return tuple(findings)

    @staticmethod
    def _validate_scenario_trace_links(
        *,
        campaign: ScenarioCampaign,
        campaign_scenario: ScenarioCampaignScenario,
        mission_requirement_ids: tuple[str, ...],
        mission_hazard_ids: tuple[str, ...],
        scenario_hazard_ids: tuple[str, ...],
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Validate requirement and hazard links for one campaign scenario."""

        findings: list[ScenarioCampaignValidationFinding] = []
        for requirement_id in campaign_scenario.requirement_ids:
            if requirement_id not in mission_requirement_ids:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=(
                            f"scenario-{campaign_scenario.scenario_id}-requirement-"
                            f"{requirement_id}-not-in-mission-thread"
                        ),
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                        message=(
                            "Campaign scenario requirement is not declared on the mission "
                            "thread."
                        ),
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                        requirement_id=requirement_id,
                    )
                )
        known_hazard_ids = set(mission_hazard_ids) | set(scenario_hazard_ids)
        for hazard_id in campaign_scenario.hazard_ids:
            if hazard_id not in known_hazard_ids:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=(
                            f"scenario-{campaign_scenario.scenario_id}-hazard-"
                            f"{hazard_id}-not-in-catalog-trace"
                        ),
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.SCENARIO_CATALOG,
                        message=(
                            "Campaign scenario hazard is not declared on the mission thread "
                            "or scenario."
                        ),
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                        hazard_id=hazard_id,
                    )
                )
        return tuple(findings)

    def _validate_evidence(
        self,
        campaign: ScenarioCampaign,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Validate referenced campaign evidence bundles."""

        findings: list[ScenarioCampaignValidationFinding] = []
        for bundle_id in campaign.required_evidence_bundle_ids():
            bundle = self._bundle_by_id.get(bundle_id)
            if bundle is None:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"evidence-{bundle_id}-missing",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.EVIDENCE,
                        message="Scenario campaign references a missing evidence bundle.",
                        campaign_id=campaign.campaign_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
                continue
            validation = bundle.validate_integrity()
            if validation.errors:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-error",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.EVIDENCE,
                        message="; ".join(validation.errors),
                        campaign_id=campaign.campaign_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
            for warning_index, warning in enumerate(validation.warnings, start=1):
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"evidence-{bundle_id}-integrity-warning-{warning_index}",
                        severity=ScenarioCampaignFindingSeverity.WARNING,
                        source=ScenarioCampaignFindingSource.EVIDENCE,
                        message=warning,
                        campaign_id=campaign.campaign_id,
                        evidence_bundle_id=bundle_id,
                    )
                )
        return tuple(findings)

    def _validate_replay_records(
        self,
        campaign: ScenarioCampaign,
    ) -> tuple[ScenarioCampaignValidationFinding, ...]:
        """Validate campaign replay record references."""

        findings: list[ScenarioCampaignValidationFinding] = []
        for campaign_scenario in campaign.scenarios:
            if campaign_scenario.uses_replay() and not campaign_scenario.replay_record_ids:
                findings.append(
                    ScenarioCampaignValidationFinding(
                        finding_id=f"scenario-{campaign_scenario.scenario_id}-missing-replay-id",
                        severity=ScenarioCampaignFindingSeverity.BLOCKER,
                        source=ScenarioCampaignFindingSource.REPLAY,
                        message="Replay-tagged campaign scenario needs a replay record ID.",
                        campaign_id=campaign.campaign_id,
                        scenario_id=campaign_scenario.scenario_id,
                    )
                )
            for replay_record_id in campaign_scenario.replay_record_ids:
                replay_record = self._replay_by_id.get(replay_record_id)
                if replay_record is None:
                    findings.append(
                        ScenarioCampaignValidationFinding(
                            finding_id=f"replay-{replay_record_id}-missing",
                            severity=ScenarioCampaignFindingSeverity.BLOCKER,
                            source=ScenarioCampaignFindingSource.REPLAY,
                            message="Scenario campaign references a missing replay record.",
                            campaign_id=campaign.campaign_id,
                            scenario_id=campaign_scenario.scenario_id,
                            replay_record_id=replay_record_id,
                        )
                    )
                    continue
                if campaign_scenario.scenario_id not in replay_record.scenario_ids:
                    findings.append(
                        ScenarioCampaignValidationFinding(
                            finding_id=(
                                f"replay-{replay_record_id}-missing-scenario-"
                                f"{campaign_scenario.scenario_id}"
                            ),
                            severity=ScenarioCampaignFindingSeverity.BLOCKER,
                            source=ScenarioCampaignFindingSource.REPLAY,
                            message="Replay record does not cover the campaign scenario ID.",
                            campaign_id=campaign.campaign_id,
                            scenario_id=campaign_scenario.scenario_id,
                            replay_record_id=replay_record_id,
                        )
                    )
                if not replay_record.evidence_bundle_ids:
                    findings.append(
                        ScenarioCampaignValidationFinding(
                            finding_id=f"replay-{replay_record_id}-missing-evidence",
                            severity=ScenarioCampaignFindingSeverity.WARNING,
                            source=ScenarioCampaignFindingSource.REPLAY,
                            message="Replay record has no evidence bundle references.",
                            campaign_id=campaign.campaign_id,
                            scenario_id=campaign_scenario.scenario_id,
                            replay_record_id=replay_record_id,
                        )
                    )
        return tuple(findings)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable scenario campaign validation identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
