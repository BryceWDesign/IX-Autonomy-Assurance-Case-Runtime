"""Policy-pack domain records for bounded AI/autonomy assurance decisions.

The serious prototype needs a policy-as-code layer before it can make credible
claims about governance, delegated risk acceptance, authority requirements, and
waiver control. This module adds strict policy records only. The actual policy
evaluator is intentionally left for a later commit so policy data contracts stay
small, reviewable, and independently testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable policy identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate a nonblank policy text field."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _require_nonblank_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a tuple of nonblank strings."""

    if not values:
        raise ContractValueError(f"{field_name} must not be empty.")
    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _require_optional_nonblank_tuple(values: tuple[str, ...], field_name: str) -> None:
    """Validate a tuple that may be empty but may not contain blanks or duplicates."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


class PolicyLifecycleState(RuntimeStrEnum):
    """Lifecycle state for a policy pack."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    SUPERSEDED = "superseded"
    RETIRED = "retired"

    def is_evaluable(self) -> bool:
        """Return whether the policy pack may be used for runtime evaluation."""

        return self is PolicyLifecycleState.ACTIVE

    def blocks_policy_claims(self) -> bool:
        """Return whether this state blocks active policy governance claims."""

        return self in {
            PolicyLifecycleState.DRAFT,
            PolicyLifecycleState.SUSPENDED,
            PolicyLifecycleState.SUPERSEDED,
            PolicyLifecycleState.RETIRED,
        }


class PolicyDecision(RuntimeStrEnum):
    """Decision a policy rule can impose on a requested action."""

    ALLOW = "allow"
    REQUIRE_REVIEW = "require_review"
    REQUIRE_WAIVER = "require_waiver"
    BLOCK = "block"

    def permits_without_intervention(self) -> bool:
        """Return whether the decision allows action without extra intervention."""

        return self is PolicyDecision.ALLOW

    def blocks_action(self) -> bool:
        """Return whether the decision blocks the requested action."""

        return self is PolicyDecision.BLOCK

    def needs_authority(self) -> bool:
        """Return whether the decision requires an authority-bearing actor."""

        return self in {PolicyDecision.REQUIRE_REVIEW, PolicyDecision.REQUIRE_WAIVER}


class PolicyActionCategory(RuntimeStrEnum):
    """Action category covered by a policy rule."""

    AUTONOMY_EXECUTION = "autonomy_execution"
    DECISION_SUPPORT = "decision_support"
    MODEL_REGISTRY_CHANGE = "model_registry_change"
    EVIDENCE_UPDATE = "evidence_update"
    TELEMETRY_INGESTION = "telemetry_ingestion"
    EXPORT_PACKAGE = "export_package"
    WAIVER_APPROVAL = "waiver_approval"

    def is_consequential(self) -> bool:
        """Return whether this action category needs tighter governance by default."""

        return self in {
            PolicyActionCategory.AUTONOMY_EXECUTION,
            PolicyActionCategory.MODEL_REGISTRY_CHANGE,
            PolicyActionCategory.WAIVER_APPROVAL,
        }


class PolicySubjectType(RuntimeStrEnum):
    """Subject type a policy rule can apply to."""

    MODEL = "model"
    SYSTEM = "system"
    USE_CASE = "use_case"
    DEPLOYMENT = "deployment"
    SCENARIO = "scenario"
    EVIDENCE_BUNDLE = "evidence_bundle"
    TELEMETRY_SOURCE = "telemetry_source"
    EXPORT_PACKAGE = "export_package"


class PolicyRiskTier(RuntimeStrEnum):
    """Risk tier used by policy packs."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"

    @property
    def rank(self) -> int:
        """Return ordinal risk rank where larger means stronger governance."""

        ranks = {
            PolicyRiskTier.LOW: 1,
            PolicyRiskTier.MODERATE: 2,
            PolicyRiskTier.HIGH: 3,
            PolicyRiskTier.CRITICAL: 4,
        }
        return ranks[self]

    def requires_explicit_authority(self) -> bool:
        """Return whether this risk tier should require explicit authority."""

        return self.rank >= PolicyRiskTier.HIGH.rank


class PolicyAuthorityRequirement(RuntimeStrEnum):
    """Authority required before a policy decision may be satisfied."""

    NONE = "none"
    HUMAN_REVIEWER = "human_reviewer"
    SYSTEM_OWNER = "system_owner"
    GOVERNANCE_BOARD = "governance_board"

    @property
    def rank(self) -> int:
        """Return ordinal authority rank where larger means stronger authority."""

        ranks = {
            PolicyAuthorityRequirement.NONE: 0,
            PolicyAuthorityRequirement.HUMAN_REVIEWER: 1,
            PolicyAuthorityRequirement.SYSTEM_OWNER: 2,
            PolicyAuthorityRequirement.GOVERNANCE_BOARD: 3,
        }
        return ranks[self]

    def satisfies(self, required: PolicyAuthorityRequirement) -> bool:
        """Return whether this authority level satisfies the required level."""

        return self.rank >= required.rank


@dataclass(frozen=True, slots=True)
class PolicyRule:
    """One machine-readable policy rule for bounded action governance."""

    rule_id: str
    name: str
    description: str
    decision: PolicyDecision
    action_categories: tuple[PolicyActionCategory, ...]
    subject_types: tuple[PolicySubjectType, ...]
    minimum_risk_tier: PolicyRiskTier = PolicyRiskTier.LOW
    authority_requirement: PolicyAuthorityRequirement = PolicyAuthorityRequirement.NONE
    required_evidence_kinds: tuple[str, ...] = ()
    blocked_conditions: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        """Validate policy rules before they can enter a policy pack."""

        _require_identifier(self.rule_id, "rule_id")
        _require_text(self.name, "policy rule name")
        _require_text(self.description, "policy rule description")
        if not self.action_categories:
            raise ContractValueError(f"Policy rule {self.rule_id!r} needs action categories.")
        if len(self.action_categories) != len(set(self.action_categories)):
            raise ContractValueError(
                f"Policy rule {self.rule_id!r} has duplicate action categories."
            )
        if not self.subject_types:
            raise ContractValueError(f"Policy rule {self.rule_id!r} needs subject types.")
        if len(self.subject_types) != len(set(self.subject_types)):
            raise ContractValueError(f"Policy rule {self.rule_id!r} has duplicate subject types.")
        _require_optional_nonblank_tuple(
            self.required_evidence_kinds,
            f"policy rule {self.rule_id!r} required_evidence_kinds",
        )
        _require_optional_nonblank_tuple(
            self.blocked_conditions,
            f"policy rule {self.rule_id!r} blocked_conditions",
        )
        if self.rationale and not self.rationale.strip():
            raise ContractValueError(f"Policy rule {self.rule_id!r} rationale is blank.")
        self._validate_authority_boundary()

    def applies_to_action(self, action_category: PolicyActionCategory) -> bool:
        """Return whether the rule applies to an action category."""

        return action_category in self.action_categories

    def applies_to_subject(self, subject_type: PolicySubjectType) -> bool:
        """Return whether the rule applies to a policy subject type."""

        return subject_type in self.subject_types

    def applies_to_risk_tier(self, risk_tier: PolicyRiskTier) -> bool:
        """Return whether the rule applies at the provided risk tier."""

        return risk_tier.rank >= self.minimum_risk_tier.rank

    def _validate_authority_boundary(self) -> None:
        """Validate anti-overclaim authority requirements."""

        if (
            self.decision.needs_authority()
            and self.authority_requirement is PolicyAuthorityRequirement.NONE
        ):
            raise ContractValueError(
                f"Policy rule {self.rule_id!r} decision {self.decision.value!r} requires authority."
            )
        if self.decision is PolicyDecision.REQUIRE_WAIVER and not self.required_evidence_kinds:
            raise ContractValueError(
                f"Policy rule {self.rule_id!r} requires waiver evidence kinds."
            )
        if (
            self.decision is PolicyDecision.ALLOW
            and self.minimum_risk_tier.requires_explicit_authority()
            and self.authority_requirement is PolicyAuthorityRequirement.NONE
        ):
            raise ContractValueError(
                f"Policy rule {self.rule_id!r} cannot allow high-risk action without authority."
            )
        if (
            PolicyActionCategory.WAIVER_APPROVAL in self.action_categories
            and self.authority_requirement is PolicyAuthorityRequirement.NONE
        ):
            raise ContractValueError(
                f"Policy rule {self.rule_id!r} waiver approval requires authority."
            )


@dataclass(frozen=True, slots=True)
class PolicyWaiver:
    """Bounded waiver record for a policy exception."""

    waiver_id: str
    policy_pack_id: str
    covered_rule_ids: tuple[str, ...]
    granted_by: str
    authority_requirement: PolicyAuthorityRequirement
    justification: str
    evidence_bundle_ids: tuple[str, ...]
    scope_limitations: tuple[str, ...]
    expires_at_utc: str

    def __post_init__(self) -> None:
        """Validate waiver records so exceptions remain bounded and reviewable."""

        _require_identifier(self.waiver_id, "waiver_id")
        _require_identifier(self.policy_pack_id, "waiver policy_pack_id")
        _require_nonblank_tuple(self.covered_rule_ids, "waiver covered_rule_ids")
        _require_text(self.granted_by, "waiver granted_by")
        _require_text(self.justification, "waiver justification")
        _require_nonblank_tuple(self.evidence_bundle_ids, "waiver evidence_bundle_ids")
        _require_nonblank_tuple(self.scope_limitations, "waiver scope_limitations")
        _require_text(self.expires_at_utc, "waiver expires_at_utc")
        if self.authority_requirement is PolicyAuthorityRequirement.NONE:
            raise ContractValueError("policy waivers require explicit authority.")

    def covers_rule(self, rule_id: str) -> bool:
        """Return whether this waiver covers a specific policy rule."""

        return rule_id in self.covered_rule_ids


@dataclass(frozen=True, slots=True)
class PolicyPack:
    """Versioned local policy pack used by the policy subsystem."""

    policy_pack_id: str
    name: str
    version: str
    owner: str
    lifecycle_state: PolicyLifecycleState
    rules: tuple[PolicyRule, ...]
    default_decision: PolicyDecision = PolicyDecision.REQUIRE_REVIEW
    notes: str = ""

    def __post_init__(self) -> None:
        """Validate policy packs as stable governance artifacts."""

        _require_identifier(self.policy_pack_id, "policy_pack_id")
        _require_text(self.name, "policy pack name")
        _require_text(self.version, "policy pack version")
        _require_text(self.owner, "policy pack owner")
        if self.notes and not self.notes.strip():
            raise ContractValueError("policy pack notes must not be whitespace only.")
        if self.lifecycle_state.is_evaluable() and not self.rules:
            raise ContractValueError("active policy packs must contain at least one rule.")
        if self.default_decision is PolicyDecision.ALLOW:
            raise ContractValueError("policy pack default decision must not be allow.")
        self._validate_unique_rule_ids()
        self._validate_active_pack_has_restrictive_rule()

    def is_evaluable(self) -> bool:
        """Return whether this policy pack may be evaluated."""

        return self.lifecycle_state.is_evaluable()

    def rule_by_id(self, rule_id: str) -> PolicyRule | None:
        """Return a rule by ID, if present."""

        return {rule.rule_id: rule for rule in self.rules}.get(rule_id)

    def _validate_unique_rule_ids(self) -> None:
        """Reject duplicate rule IDs."""

        rule_ids = tuple(rule.rule_id for rule in self.rules)
        if len(rule_ids) != len(set(rule_ids)):
            raise ContractValueError("policy packs must not contain duplicate rule IDs.")

    def _validate_active_pack_has_restrictive_rule(self) -> None:
        """Ensure active packs contain at least one review, waiver, or block rule."""

        if not self.lifecycle_state.is_evaluable():
            return
        if not any(rule.decision is not PolicyDecision.ALLOW for rule in self.rules):
            raise ContractValueError(
                "active policy packs must contain at least one restrictive rule."
            )
