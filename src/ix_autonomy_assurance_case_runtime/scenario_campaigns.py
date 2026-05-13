"""Scenario campaign domain records for autonomy T&E.

A single scenario run is not enough for serious autonomy assurance work. Campaigns
collect baseline, degraded-mode, adversarial, regression, and stress scenarios
under explicit objectives and acceptance thresholds so later commits can execute,
summarize, and evidence multi-scenario evaluation without claiming certification,
operational acceptance, or agency endorsement.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    RuntimeStrEnum,
    VerificationResult,
)


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable scenario-campaign identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank scenario-campaign text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized


def _normalize_identifier_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate identifier tuples and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _normalize_text_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate text tuples and reject duplicates."""

    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")
    return normalized


class ScenarioCampaignStatus(RuntimeStrEnum):
    """Lifecycle posture for a scenario campaign plan."""

    DRAFT = "draft"
    READY_FOR_RUN = "ready_for_run"
    RUNNING = "running"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"

    def can_execute(self) -> bool:
        """Return whether a campaign status permits local execution."""

        return self in {
            ScenarioCampaignStatus.READY_FOR_RUN,
            ScenarioCampaignStatus.RUNNING,
        }

    def is_terminal(self) -> bool:
        """Return whether a campaign status is terminal."""

        return self in {
            ScenarioCampaignStatus.COMPLETED,
            ScenarioCampaignStatus.SUPERSEDED,
        }


class ScenarioCampaignTag(RuntimeStrEnum):
    """Supported campaign tags for deterministic T&E grouping."""

    BASELINE = "baseline"
    ADVERSARIAL = "adversarial"
    DEGRADED_MODE = "degraded_mode"
    REGRESSION = "regression"
    STRESS = "stress"
    SAFETY_GATE = "safety_gate"
    SOURCE_TRUST = "source_trust"
    TELEMETRY_REPLAY = "telemetry_replay"

    def is_non_nominal(self) -> bool:
        """Return whether the tag represents non-nominal evaluation pressure."""

        return self in {
            ScenarioCampaignTag.ADVERSARIAL,
            ScenarioCampaignTag.DEGRADED_MODE,
            ScenarioCampaignTag.STRESS,
            ScenarioCampaignTag.SOURCE_TRUST,
            ScenarioCampaignTag.TELEMETRY_REPLAY,
        }


class ScenarioCampaignScenarioRole(RuntimeStrEnum):
    """Role of a scenario inside a campaign."""

    BASELINE = "baseline"
    ADVERSARIAL_PROBE = "adversarial_probe"
    DEGRADED_MODE = "degraded_mode"
    REGRESSION = "regression"
    STRESS = "stress"
    NEGATIVE_CONTROL = "negative_control"

    @property
    def required_tag(self) -> ScenarioCampaignTag:
        """Return the campaign tag that must accompany this role."""

        tags = {
            ScenarioCampaignScenarioRole.BASELINE: ScenarioCampaignTag.BASELINE,
            ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE: ScenarioCampaignTag.ADVERSARIAL,
            ScenarioCampaignScenarioRole.DEGRADED_MODE: ScenarioCampaignTag.DEGRADED_MODE,
            ScenarioCampaignScenarioRole.REGRESSION: ScenarioCampaignTag.REGRESSION,
            ScenarioCampaignScenarioRole.STRESS: ScenarioCampaignTag.STRESS,
            ScenarioCampaignScenarioRole.NEGATIVE_CONTROL: ScenarioCampaignTag.BASELINE,
        }
        return tags[self]

    def is_adversarial(self) -> bool:
        """Return whether this role is an adversarial probe."""

        return self is ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE

    def is_non_nominal(self) -> bool:
        """Return whether this role represents degraded, stress, or adversarial coverage."""

        return self in {
            ScenarioCampaignScenarioRole.ADVERSARIAL_PROBE,
            ScenarioCampaignScenarioRole.DEGRADED_MODE,
            ScenarioCampaignScenarioRole.STRESS,
        }


@dataclass(frozen=True, slots=True)
class ScenarioCampaignObjective:
    """One reviewable objective for a scenario campaign."""

    objective_id: str
    statement: str
    success_criteria: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate scenario-campaign objective records."""

        object.__setattr__(
            self,
            "objective_id",
            _require_identifier(self.objective_id, "objective_id"),
        )
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(
            self,
            "success_criteria",
            _normalize_text_tuple(self.success_criteria, "success_criteria"),
        )
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_identifier_tuple(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        if not self.success_criteria:
            raise ContractValueError("Scenario campaign objective needs success criteria.")
        if not self.requirement_ids:
            raise ContractValueError("Scenario campaign objective needs requirement links.")

    def traces_to_hazard(self) -> bool:
        """Return whether the objective is tied to one or more hazard IDs."""

        return bool(self.hazard_ids)


@dataclass(frozen=True, slots=True)
class ScenarioCampaignAcceptanceThreshold:
    """Deterministic threshold policy for campaign acceptance."""

    threshold_id: str
    minimum_pass_rate: float
    maximum_failed_runs: int = 0
    maximum_inconclusive_runs: int = 0
    require_all_critical_scenarios_pass: bool = True
    require_evidence_for_each_scenario: bool = True

    def __post_init__(self) -> None:
        """Validate campaign threshold settings."""

        object.__setattr__(
            self,
            "threshold_id",
            _require_identifier(self.threshold_id, "threshold_id"),
        )
        if self.minimum_pass_rate <= 0.0 or self.minimum_pass_rate > 1.0:
            raise ContractValueError("minimum_pass_rate must be > 0.0 and <= 1.0.")
        if self.maximum_failed_runs < 0:
            raise ContractValueError("maximum_failed_runs must not be negative.")
        if self.maximum_inconclusive_runs < 0:
            raise ContractValueError("maximum_inconclusive_runs must not be negative.")

    def accepts_counts(
        self,
        *,
        pass_count: int,
        fail_count: int,
        inconclusive_count: int,
        total_count: int,
    ) -> bool:
        """Return whether aggregate run counts satisfy this threshold."""

        for field_name, count in (
            ("pass_count", pass_count),
            ("fail_count", fail_count),
            ("inconclusive_count", inconclusive_count),
            ("total_count", total_count),
        ):
            if count < 0:
                raise ContractValueError(f"{field_name} must not be negative.")
        if total_count <= 0:
            raise ContractValueError("total_count must be positive.")
        if pass_count + fail_count + inconclusive_count != total_count:
            raise ContractValueError("Campaign result counts must add up to total_count.")
        pass_rate = pass_count / total_count
        return (
            pass_rate >= self.minimum_pass_rate
            and fail_count <= self.maximum_failed_runs
            and inconclusive_count <= self.maximum_inconclusive_runs
        )


@dataclass(frozen=True, slots=True)
class ScenarioCampaignScenario:
    """Scenario membership record inside a campaign plan."""

    campaign_scenario_id: str
    scenario_id: str
    role: ScenarioCampaignScenarioRole
    expected_result: VerificationResult
    minimum_runs: int = 1
    tags: tuple[ScenarioCampaignTag, ...] = field(default_factory=tuple)
    requirement_ids: tuple[str, ...] = field(default_factory=tuple)
    hazard_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    replay_record_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate campaign scenario membership records."""

        object.__setattr__(
            self,
            "campaign_scenario_id",
            _require_identifier(self.campaign_scenario_id, "campaign_scenario_id"),
        )
        object.__setattr__(
            self,
            "scenario_id",
            _require_identifier(self.scenario_id, "scenario_id"),
        )
        object.__setattr__(
            self,
            "requirement_ids",
            _normalize_identifier_tuple(self.requirement_ids, "requirement_ids"),
        )
        object.__setattr__(
            self,
            "hazard_ids",
            _normalize_identifier_tuple(self.hazard_ids, "hazard_ids"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(
            self,
            "replay_record_ids",
            _normalize_identifier_tuple(self.replay_record_ids, "replay_record_ids"),
        )
        if self.minimum_runs <= 0:
            raise ContractValueError("minimum_runs must be positive.")
        if len(self.tags) != len(set(self.tags)):
            raise ContractValueError("Scenario campaign scenario tags must not contain duplicates.")
        if self.role.required_tag not in self.tags:
            raise ContractValueError(
                f"Scenario role {self.role.value!r} requires tag {self.role.required_tag.value!r}."
            )
        if self.role.is_non_nominal() and not self.hazard_ids:
            raise ContractValueError(
                "Non-nominal campaign scenarios require hazard IDs for review traceability."
            )

    def is_adversarial_probe(self) -> bool:
        """Return whether this campaign scenario is an adversarial probe."""

        return self.role.is_adversarial()

    def uses_replay(self) -> bool:
        """Return whether this campaign scenario depends on replay evidence."""

        return bool(self.replay_record_ids) or ScenarioCampaignTag.TELEMETRY_REPLAY in self.tags


@dataclass(frozen=True, slots=True)
class ScenarioCampaignStopRule:
    """Stop condition that prevents false campaign acceptance."""

    stop_rule_id: str
    description: str
    trigger_condition: str
    blocks_acceptance: bool = True
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate scenario-campaign stop rules."""

        object.__setattr__(
            self,
            "stop_rule_id",
            _require_identifier(self.stop_rule_id, "stop_rule_id"),
        )
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "trigger_condition",
            _require_text(self.trigger_condition, "trigger_condition"),
        )
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )


@dataclass(frozen=True, slots=True)
class ScenarioCampaign:
    """A deterministic multi-scenario campaign plan."""

    campaign_id: str
    name: str
    purpose: str
    status: ScenarioCampaignStatus
    mission_thread_id: str
    objectives: tuple[ScenarioCampaignObjective, ...]
    scenarios: tuple[ScenarioCampaignScenario, ...]
    acceptance_threshold: ScenarioCampaignAcceptanceThreshold
    tags: tuple[ScenarioCampaignTag, ...]
    stop_rules: tuple[ScenarioCampaignStopRule, ...] = field(default_factory=tuple)
    evidence_bundle_ids: tuple[str, ...] = field(default_factory=tuple)
    owner: str = "unassigned-owner"
    version: str = "0.1"
    notes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate a scenario campaign plan."""

        object.__setattr__(
            self,
            "campaign_id",
            _require_identifier(self.campaign_id, "campaign_id"),
        )
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "purpose", _require_text(self.purpose, "purpose"))
        object.__setattr__(
            self,
            "mission_thread_id",
            _require_identifier(self.mission_thread_id, "mission_thread_id"),
        )
        object.__setattr__(self, "owner", _require_text(self.owner, "owner"))
        object.__setattr__(self, "version", _require_text(self.version, "version"))
        object.__setattr__(
            self,
            "evidence_bundle_ids",
            _normalize_identifier_tuple(self.evidence_bundle_ids, "evidence_bundle_ids"),
        )
        object.__setattr__(self, "notes", _normalize_text_tuple(self.notes, "notes"))
        self._validate_collection_shape()
        self._validate_tag_coverage()

    def scenario_ids(self) -> tuple[str, ...]:
        """Return scenario IDs in campaign order."""

        return tuple(campaign_scenario.scenario_id for campaign_scenario in self.scenarios)

    def adversarial_scenario_ids(self) -> tuple[str, ...]:
        """Return adversarial probe scenario IDs in campaign order."""

        return tuple(
            campaign_scenario.scenario_id
            for campaign_scenario in self.scenarios
            if campaign_scenario.is_adversarial_probe()
        )

    def required_requirement_ids(self) -> tuple[str, ...]:
        """Return unique requirement IDs referenced by campaign objectives and scenarios."""

        requirement_ids: list[str] = []
        for objective in self.objectives:
            requirement_ids.extend(objective.requirement_ids)
        for campaign_scenario in self.scenarios:
            requirement_ids.extend(campaign_scenario.requirement_ids)
        return tuple(dict.fromkeys(requirement_ids))

    def required_hazard_ids(self) -> tuple[str, ...]:
        """Return unique hazard IDs referenced by objectives and campaign scenarios."""

        hazard_ids: list[str] = []
        for objective in self.objectives:
            hazard_ids.extend(objective.hazard_ids)
        for campaign_scenario in self.scenarios:
            hazard_ids.extend(campaign_scenario.hazard_ids)
        return tuple(dict.fromkeys(hazard_ids))

    def required_evidence_bundle_ids(self) -> tuple[str, ...]:
        """Return unique evidence bundle IDs referenced by the campaign."""

        bundle_ids: list[str] = list(self.evidence_bundle_ids)
        for campaign_scenario in self.scenarios:
            bundle_ids.extend(campaign_scenario.evidence_bundle_ids)
        for stop_rule in self.stop_rules:
            bundle_ids.extend(stop_rule.evidence_bundle_ids)
        return tuple(dict.fromkeys(bundle_ids))

    def required_replay_record_ids(self) -> tuple[str, ...]:
        """Return unique replay record IDs referenced by campaign scenarios."""

        replay_record_ids: list[str] = []
        for campaign_scenario in self.scenarios:
            replay_record_ids.extend(campaign_scenario.replay_record_ids)
        return tuple(dict.fromkeys(replay_record_ids))

    def has_adversarial_coverage(self) -> bool:
        """Return whether the campaign includes adversarial probe coverage."""

        return any(campaign_scenario.is_adversarial_probe() for campaign_scenario in self.scenarios)

    def has_non_nominal_coverage(self) -> bool:
        """Return whether the campaign includes degraded, stress, or adversarial coverage."""

        return any(campaign_scenario.role.is_non_nominal() for campaign_scenario in self.scenarios)

    def can_execute_locally(self) -> bool:
        """Return whether this campaign plan is locally executable in principle."""

        return self.status.can_execute() and bool(self.scenarios) and bool(self.objectives)

    def _validate_collection_shape(self) -> None:
        """Validate campaign collection shape and duplicate identifiers."""

        if not self.objectives:
            raise ContractValueError("Scenario campaign needs at least one objective.")
        if not self.scenarios:
            raise ContractValueError("Scenario campaign needs at least one scenario.")
        if not self.tags:
            raise ContractValueError("Scenario campaign needs at least one tag.")
        objective_ids = tuple(objective.objective_id for objective in self.objectives)
        if len(objective_ids) != len(set(objective_ids)):
            raise ContractValueError("Scenario campaign objectives must not duplicate IDs.")
        campaign_scenario_ids = tuple(
            campaign_scenario.campaign_scenario_id for campaign_scenario in self.scenarios
        )
        if len(campaign_scenario_ids) != len(set(campaign_scenario_ids)):
            raise ContractValueError("Scenario campaign scenario entries must not duplicate IDs.")
        scenario_ids = self.scenario_ids()
        if len(scenario_ids) != len(set(scenario_ids)):
            raise ContractValueError("Scenario campaign scenario IDs must not duplicate IDs.")
        stop_rule_ids = tuple(stop_rule.stop_rule_id for stop_rule in self.stop_rules)
        if len(stop_rule_ids) != len(set(stop_rule_ids)):
            raise ContractValueError("Scenario campaign stop rules must not duplicate IDs.")
        if len(self.tags) != len(set(self.tags)):
            raise ContractValueError("Scenario campaign tags must not contain duplicates.")

    def _validate_tag_coverage(self) -> None:
        """Validate that campaign-level tags cover scenario-level roles."""

        required_tags = {
            campaign_scenario.role.required_tag for campaign_scenario in self.scenarios
        }
        missing_tags = sorted(tag.value for tag in required_tags if tag not in self.tags)
        if missing_tags:
            raise ContractValueError(
                "Scenario campaign tags missing required role coverage: "
                + ", ".join(missing_tags)
            )


@dataclass(frozen=True, slots=True)
class ScenarioCampaignCatalog:
    """Collection of deterministic scenario campaigns."""

    campaigns: tuple[ScenarioCampaign, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate campaign catalog identifiers."""

        campaign_ids = tuple(campaign.campaign_id for campaign in self.campaigns)
        if len(campaign_ids) != len(set(campaign_ids)):
            raise ContractValueError("Scenario campaign catalog must not duplicate campaign IDs.")

    def campaign_by_id(self, campaign_id: str) -> ScenarioCampaign | None:
        """Return a campaign by ID."""

        normalized_id = _require_identifier(campaign_id, "campaign_id")
        for campaign in self.campaigns:
            if campaign.campaign_id == normalized_id:
                return campaign
        return None

    def executable_campaign_ids(self) -> tuple[str, ...]:
        """Return campaign IDs that are locally executable in principle."""

        return tuple(
            campaign.campaign_id for campaign in self.campaigns if campaign.can_execute_locally()
        )

    def adversarial_campaign_ids(self) -> tuple[str, ...]:
        """Return campaign IDs that include adversarial probe coverage."""

        return tuple(
            campaign.campaign_id
            for campaign in self.campaigns
            if campaign.has_adversarial_coverage()
        )
