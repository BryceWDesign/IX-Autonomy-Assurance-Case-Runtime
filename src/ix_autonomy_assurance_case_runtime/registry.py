"""Registry records for AI/autonomy systems, models, use cases, and deployments.

The serious prototype target needs an explicit inventory layer before it can make
credible claims about model registry readiness, lifecycle oversight, approved
uses, prohibited uses, ownership, risk tier, and deployment context. This module
adds the strict domain records. It deliberately remains local and vendor-neutral;
it does not claim connection to any official federal, IC, or DoD registry.
"""

from __future__ import annotations

from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import (
    ContractValueError,
    RuntimeAuthorityState,
    RuntimeStrEnum,
)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable registry identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate a human-readable registry text field."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _require_nonblank_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a tuple of nonblank string values."""

    if not values:
        raise ContractValueError(f"{field_name} must not be empty.")
    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")


def _require_optional_nonblank_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a tuple when it is allowed to be empty."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")


def _require_unique_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate tuple uniqueness without changing order."""

    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


class RegistryLifecycleState(RuntimeStrEnum):
    """Lifecycle state for registered systems, models, use cases, and deployments."""

    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    SUSPENDED = "suspended"
    RETIRED = "retired"

    def can_support_acceptance(self) -> bool:
        """Return whether this registry state may support acceptance claims."""

        return self is RegistryLifecycleState.APPROVED

    def blocks_runtime_use(self) -> bool:
        """Return whether this state blocks active runtime use."""

        return self in {
            RegistryLifecycleState.DRAFT,
            RegistryLifecycleState.UNDER_REVIEW,
            RegistryLifecycleState.SUSPENDED,
            RegistryLifecycleState.RETIRED,
        }


class RegistryRiskTier(RuntimeStrEnum):
    """Risk tier for registered AI/autonomy assets."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return an ordinal rank where larger values require stronger control."""

        ranks = {
            RegistryRiskTier.LOW: 1,
            RegistryRiskTier.MODERATE: 2,
            RegistryRiskTier.HIGH: 3,
            RegistryRiskTier.CRITICAL: 4,
        }
        return ranks[self]

    def requires_human_review(self) -> bool:
        """Return whether this tier requires explicit human review before acceptance."""

        return self.rank >= RegistryRiskTier.HIGH.rank

    def requires_evidence_for_approval(self) -> bool:
        """Return whether approval must be backed by evidence records."""

        return self.rank >= RegistryRiskTier.MODERATE.rank


class RegisteredUseCategory(RuntimeStrEnum):
    """Declared purpose category for a registered use case."""

    DECISION_SUPPORT = "decision_support"
    AUTONOMY_CONTROL = "autonomy_control"
    INTELLIGENCE_ANALYSIS = "intelligence_analysis"
    TEST_AND_EVALUATION = "test_and_evaluation"
    SAFETY_MONITORING = "safety_monitoring"

    def is_consequential(self) -> bool:
        """Return whether this use category affects consequential mission decisions."""

        return self in {
            RegisteredUseCategory.AUTONOMY_CONTROL,
            RegisteredUseCategory.INTELLIGENCE_ANALYSIS,
            RegisteredUseCategory.SAFETY_MONITORING,
        }


class DeploymentEnvironment(RuntimeStrEnum):
    """Environment where a registered deployment is evaluated or operated."""

    LAB = "lab"
    SIMULATION = "simulation"
    STAGING = "staging"
    OPERATIONAL_TEST = "operational_test"
    CONTROLLED_FIELD = "controlled_field"

    def needs_operational_evidence(self) -> bool:
        """Return whether the environment needs scenario evidence before live use."""

        return self in {
            DeploymentEnvironment.OPERATIONAL_TEST,
            DeploymentEnvironment.CONTROLLED_FIELD,
        }


@dataclass(frozen=True, slots=True)
class RegisteredModel:
    """Registered model or analytic component used by an AI/autonomy system."""

    model_id: str
    name: str
    version: str
    owner: str
    lifecycle_state: RegistryLifecycleState
    risk_tier: RegistryRiskTier
    intended_uses: tuple[str, ...]
    prohibited_uses: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...] = ()
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate model registry records."""

        _require_identifier(self.model_id, "model_id")
        _require_text(self.name, "model name")
        _require_text(self.version, "model version")
        _require_text(self.owner, "model owner")
        _require_nonblank_tuple(self.intended_uses, "model intended_uses")
        _require_nonblank_tuple(self.prohibited_uses, "model prohibited_uses")
        _require_optional_nonblank_tuple(self.evidence_bundle_ids, "model evidence_bundle_ids")
        _require_unique_tuple(self.intended_uses, "model intended_uses")
        _require_unique_tuple(self.prohibited_uses, "model prohibited_uses")
        _require_unique_tuple(self.evidence_bundle_ids, "model evidence_bundle_ids")
        if self.notes and not self.notes.strip():
            raise ContractValueError("model notes must not be whitespace only.")
        if self.lifecycle_state.can_support_acceptance() and not self.evidence_bundle_ids:
            message = "approved registered models must reference at least one evidence bundle."
            raise ContractValueError(message)

    def requires_human_review(self) -> bool:
        """Return whether this model needs explicit human review."""

        return self.risk_tier.requires_human_review()


@dataclass(frozen=True, slots=True)
class RegisteredSystem:
    """Registered AI/autonomy system under assurance review."""

    system_id: str
    name: str
    owner: str
    lifecycle_state: RegistryLifecycleState
    risk_tier: RegistryRiskTier
    mission_thread_ids: tuple[str, ...]
    model_ids: tuple[str, ...] = ()
    assurance_case_id: str | None = None
    description: str = ""

    def __post_init__(self) -> None:
        """Validate system registry records."""

        _require_identifier(self.system_id, "system_id")
        _require_text(self.name, "system name")
        _require_text(self.owner, "system owner")
        _require_nonblank_tuple(self.mission_thread_ids, "system mission_thread_ids")
        _require_optional_nonblank_tuple(self.model_ids, "system model_ids")
        _require_unique_tuple(self.mission_thread_ids, "system mission_thread_ids")
        _require_unique_tuple(self.model_ids, "system model_ids")
        if self.assurance_case_id is not None:
            _require_identifier(self.assurance_case_id, "system assurance_case_id")
        if self.description and not self.description.strip():
            raise ContractValueError("system description must not be whitespace only.")
        if self.lifecycle_state.can_support_acceptance() and self.assurance_case_id is None:
            message = "approved registered systems must reference an assurance case."
            raise ContractValueError(message)

    def can_reference_models(self) -> bool:
        """Return whether the system has model/component references."""

        return bool(self.model_ids)


@dataclass(frozen=True, slots=True)
class RegisteredUseCase:
    """Registered use case tying mission need and requirements to a system."""

    use_case_id: str
    name: str
    system_id: str
    category: RegisteredUseCategory
    lifecycle_state: RegistryLifecycleState
    risk_tier: RegistryRiskTier
    mission_need_ids: tuple[str, ...]
    requirement_ids: tuple[str, ...]
    prohibited_conditions: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate use-case registry records."""

        _require_identifier(self.use_case_id, "use_case_id")
        _require_text(self.name, "use-case name")
        _require_identifier(self.system_id, "use-case system_id")
        _require_nonblank_tuple(self.mission_need_ids, "use-case mission_need_ids")
        _require_nonblank_tuple(self.requirement_ids, "use-case requirement_ids")
        _require_nonblank_tuple(self.prohibited_conditions, "use-case prohibited_conditions")
        _require_optional_nonblank_tuple(self.evidence_bundle_ids, "use-case evidence_bundle_ids")
        _require_unique_tuple(self.mission_need_ids, "use-case mission_need_ids")
        _require_unique_tuple(self.requirement_ids, "use-case requirement_ids")
        _require_unique_tuple(self.prohibited_conditions, "use-case prohibited_conditions")
        _require_unique_tuple(self.evidence_bundle_ids, "use-case evidence_bundle_ids")
        if self.lifecycle_state.can_support_acceptance() and not self.evidence_bundle_ids:
            message = "approved registered use cases must reference at least one evidence bundle."
            raise ContractValueError(message)

    def requires_authority_review(self) -> bool:
        """Return whether this use case needs explicit authority review."""

        return self.category.is_consequential() or self.risk_tier.requires_human_review()


@dataclass(frozen=True, slots=True)
class RegisteredDeployment:
    """Registered deployment context for an assured system."""

    deployment_id: str
    system_id: str
    environment: DeploymentEnvironment
    lifecycle_state: RegistryLifecycleState
    authority_state: RuntimeAuthorityState
    scenario_ids: tuple[str, ...]
    evidence_bundle_ids: tuple[str, ...]
    telemetry_source_ids: tuple[str, ...] = ()
    approved_for_live_operation: bool = False

    def __post_init__(self) -> None:
        """Validate deployment registry records."""

        _require_identifier(self.deployment_id, "deployment_id")
        _require_identifier(self.system_id, "deployment system_id")
        _require_nonblank_tuple(self.scenario_ids, "deployment scenario_ids")
        _require_nonblank_tuple(self.evidence_bundle_ids, "deployment evidence_bundle_ids")
        _require_optional_nonblank_tuple(
            self.telemetry_source_ids, "deployment telemetry_source_ids"
        )
        _require_unique_tuple(self.scenario_ids, "deployment scenario_ids")
        _require_unique_tuple(self.evidence_bundle_ids, "deployment evidence_bundle_ids")
        _require_unique_tuple(self.telemetry_source_ids, "deployment telemetry_source_ids")
        if self.approved_for_live_operation:
            self._validate_live_operation_approval()

    def _validate_live_operation_approval(self) -> None:
        """Validate the stricter live-operation approval boundary."""

        if not self.lifecycle_state.can_support_acceptance():
            raise ContractValueError(
                "live operation requires an approved deployment lifecycle state."
            )
        if self.authority_state.blocks_autonomous_execution():
            raise ContractValueError(
                "live operation cannot be approved under blocking authority state."
            )
        if self.environment.needs_operational_evidence() and not self.telemetry_source_ids:
            raise ContractValueError(
                "operational-test or controlled-field live operation requires telemetry sources."
            )

    def needs_revalidation_before_use(self) -> bool:
        """Return whether this deployment needs revalidation before active use."""

        return (
            self.lifecycle_state.blocks_runtime_use()
            or self.authority_state.blocks_autonomous_execution()
        )
