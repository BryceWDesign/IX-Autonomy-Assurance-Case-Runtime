"""Policy-pack evaluation engine for bounded runtime governance decisions.

Policy records define the governance boundary; this module evaluates an action
request against an active policy pack, available waivers, evidence-kind posture,
authority level, risk tier, and active conditions. The evaluator is intentionally
local and deterministic. It does not claim connection to an official government
policy engine or authorization system.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.policy import (
    PolicyActionCategory,
    PolicyAuthorityRequirement,
    PolicyDecision,
    PolicyPack,
    PolicyRiskTier,
    PolicyRule,
    PolicySubjectType,
    PolicyWaiver,
)


def _require_identifier(value: str, field_name: str) -> None:
    """Validate an evaluator identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")


def _require_text(value: str, field_name: str) -> None:
    """Validate evaluator text."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")


def _validate_optional_unique_strings(values: tuple[str, ...], field_name: str) -> None:
    """Validate optional string tuples used by policy requests."""

    for value in values:
        if not value.strip():
            raise ContractValueError(f"{field_name} must not contain blank values.")
    if len(values) != len(set(values)):
        raise ContractValueError(f"{field_name} must not contain duplicate values.")


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse a UTC timestamp with strict timezone handling."""

    _require_text(value, field_name)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 UTC timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class PolicyEvaluationFindingSeverity(RuntimeStrEnum):
    """Severity for policy evaluation findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_action(self) -> bool:
        """Return whether this finding blocks the requested action."""

        return self is PolicyEvaluationFindingSeverity.BLOCKER


@dataclass(frozen=True, slots=True)
class PolicyEvaluationRequest:
    """Request evaluated against a policy pack."""

    request_id: str
    action_category: PolicyActionCategory
    subject_type: PolicySubjectType
    subject_id: str
    risk_tier: PolicyRiskTier
    requested_by: str
    authority: PolicyAuthorityRequirement = PolicyAuthorityRequirement.NONE
    evidence_kinds: tuple[str, ...] = ()
    active_conditions: tuple[str, ...] = ()
    waiver_ids: tuple[str, ...] = ()
    evaluated_at_utc: str = "1970-01-01T00:00:00Z"

    def __post_init__(self) -> None:
        """Validate a policy evaluation request."""

        _require_identifier(self.request_id, "policy request_id")
        _require_identifier(self.subject_id, "policy subject_id")
        _require_text(self.requested_by, "policy requested_by")
        _validate_optional_unique_strings(self.evidence_kinds, "policy evidence_kinds")
        _validate_optional_unique_strings(self.active_conditions, "policy active_conditions")
        _validate_optional_unique_strings(self.waiver_ids, "policy waiver_ids")
        _parse_utc_timestamp(self.evaluated_at_utc, "policy evaluated_at_utc")

    @property
    def evaluated_at(self) -> datetime:
        """Return the parsed UTC evaluation timestamp."""

        return _parse_utc_timestamp(self.evaluated_at_utc, "policy evaluated_at_utc")

    def has_evidence_kind(self, evidence_kind: str) -> bool:
        """Return whether the request provides a required evidence kind."""

        return evidence_kind in self.evidence_kinds

    def has_active_condition(self, condition: str) -> bool:
        """Return whether an active condition is present on the request."""

        return condition in self.active_conditions


@dataclass(frozen=True, slots=True)
class PolicyEvaluationFinding:
    """One finding produced while evaluating a policy request."""

    finding_id: str
    severity: PolicyEvaluationFindingSeverity
    message: str
    rule_id: str | None = None
    waiver_id: str | None = None

    def __post_init__(self) -> None:
        """Validate policy evaluation finding fields."""

        if not self.finding_id.strip():
            raise ContractValueError("Policy evaluation finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Policy evaluation finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Policy evaluation finding {self.finding_id!r} needs a message."
            )
        if self.rule_id is not None and not self.rule_id.strip():
            raise ContractValueError(
                f"Policy evaluation finding {self.finding_id!r} has a blank rule ID."
            )
        if self.waiver_id is not None and not self.waiver_id.strip():
            raise ContractValueError(
                f"Policy evaluation finding {self.finding_id!r} has a blank waiver ID."
            )


@dataclass(frozen=True, slots=True)
class PolicyRuleEvaluation:
    """Evaluation result for one matching policy rule."""

    rule_id: str
    decision: PolicyDecision
    required_decision: PolicyDecision
    findings: tuple[PolicyEvaluationFinding, ...]
    satisfied_by_waiver_id: str | None = None

    def __post_init__(self) -> None:
        """Validate rule evaluation records."""

        _require_identifier(self.rule_id, "policy rule evaluation rule_id")
        if self.satisfied_by_waiver_id is not None:
            _require_identifier(
                self.satisfied_by_waiver_id,
                "policy rule evaluation satisfied_by_waiver_id",
            )

    @property
    def blocker_count(self) -> int:
        """Return blocker count for this rule evaluation."""

        return sum(finding.severity.blocks_action() for finding in self.findings)

    def blocks_action(self) -> bool:
        """Return whether this rule evaluation blocks the request."""

        return self.decision is PolicyDecision.BLOCK or self.blocker_count > 0


@dataclass(frozen=True, slots=True)
class PolicyEvaluationReport:
    """Aggregated policy evaluation report for one request."""

    request_id: str
    policy_pack_id: str
    decision: PolicyDecision
    matched_rule_ids: tuple[str, ...]
    rule_evaluations: tuple[PolicyRuleEvaluation, ...]
    findings: tuple[PolicyEvaluationFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return blocker findings across the report."""

        return sum(finding.severity.blocks_action() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return warning findings across the report."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is PolicyEvaluationFindingSeverity.WARNING
        )

    def permits_without_intervention(self) -> bool:
        """Return whether policy permits the request without intervention."""

        return self.decision.permits_without_intervention() and self.blocker_count == 0

    def summary(self) -> str:
        """Return a deterministic policy evaluation summary."""

        return (
            f"policy-evaluation: {self.decision.value} "
            f"({len(self.matched_rule_ids)} matched rule(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s))"
        )


class PolicyEvaluator:
    """Evaluate local policy packs against bounded action requests."""

    def __init__(self, policy_pack: PolicyPack, waivers: tuple[PolicyWaiver, ...] = ()) -> None:
        """Create an evaluator for one policy pack and optional waivers."""

        self._policy_pack = policy_pack
        self._waiver_by_id = self._index_waivers(waivers)

    def evaluate(self, request: PolicyEvaluationRequest) -> PolicyEvaluationReport:
        """Evaluate a request and return a deterministic policy report."""

        if not self._policy_pack.is_evaluable():
            finding = PolicyEvaluationFinding(
                finding_id="policy-pack-not-active",
                severity=PolicyEvaluationFindingSeverity.BLOCKER,
                message="Policy pack is not active and cannot support runtime policy claims.",
            )
            return PolicyEvaluationReport(
                request_id=request.request_id,
                policy_pack_id=self._policy_pack.policy_pack_id,
                decision=PolicyDecision.BLOCK,
                matched_rule_ids=(),
                rule_evaluations=(),
                findings=(finding,),
            )

        matching_rules = tuple(
            rule for rule in self._policy_pack.rules if rule_matches(rule, request)
        )
        if not matching_rules:
            finding = PolicyEvaluationFinding(
                finding_id="policy-default-decision-applied",
                severity=PolicyEvaluationFindingSeverity.WARNING,
                message="No policy rule matched; policy pack default decision was applied.",
            )
            return PolicyEvaluationReport(
                request_id=request.request_id,
                policy_pack_id=self._policy_pack.policy_pack_id,
                decision=self._policy_pack.default_decision,
                matched_rule_ids=(),
                rule_evaluations=(),
                findings=(finding,),
            )

        rule_evaluations = tuple(self._evaluate_rule(rule, request) for rule in matching_rules)
        findings = tuple(
            finding
            for rule_evaluation in rule_evaluations
            for finding in rule_evaluation.findings
        )
        decision = _aggregate_decision(rule_evaluations)
        return PolicyEvaluationReport(
            request_id=request.request_id,
            policy_pack_id=self._policy_pack.policy_pack_id,
            decision=decision,
            matched_rule_ids=tuple(rule.rule_id for rule in matching_rules),
            rule_evaluations=rule_evaluations,
            findings=findings,
        )

    @staticmethod
    def _index_waivers(waivers: tuple[PolicyWaiver, ...]) -> dict[str, PolicyWaiver]:
        """Index waivers by ID and reject duplicates."""

        indexed: dict[str, PolicyWaiver] = {}
        for waiver in waivers:
            if waiver.waiver_id in indexed:
                raise ContractValueError(f"Duplicate policy waiver ID {waiver.waiver_id!r}.")
            indexed[waiver.waiver_id] = waiver
        return indexed

    def _evaluate_rule(
        self,
        rule: PolicyRule,
        request: PolicyEvaluationRequest,
    ) -> PolicyRuleEvaluation:
        """Evaluate one matching rule."""

        findings: list[PolicyEvaluationFinding] = []
        triggered_blocked_conditions = tuple(
            condition
            for condition in rule.blocked_conditions
            if request.has_active_condition(condition)
        )
        if triggered_blocked_conditions:
            for condition in triggered_blocked_conditions:
                findings.append(
                    PolicyEvaluationFinding(
                        finding_id=f"rule-{rule.rule_id}-blocked-condition-{condition}",
                        severity=PolicyEvaluationFindingSeverity.BLOCKER,
                        message=f"Blocked condition {condition!r} is active for the request.",
                        rule_id=rule.rule_id,
                    )
                )
            return PolicyRuleEvaluation(
                rule_id=rule.rule_id,
                decision=PolicyDecision.BLOCK,
                required_decision=rule.decision,
                findings=tuple(findings),
            )

        missing_evidence = tuple(
            evidence_kind
            for evidence_kind in rule.required_evidence_kinds
            if not request.has_evidence_kind(evidence_kind)
        )
        for evidence_kind in missing_evidence:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-missing-evidence-{evidence_kind}",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message=f"Required evidence kind {evidence_kind!r} is missing.",
                    rule_id=rule.rule_id,
                )
            )

        if rule.decision is PolicyDecision.BLOCK:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-blocks-action",
                    severity=PolicyEvaluationFindingSeverity.BLOCKER,
                    message="Policy rule explicitly blocks the requested action.",
                    rule_id=rule.rule_id,
                )
            )
            return PolicyRuleEvaluation(
                rule_id=rule.rule_id,
                decision=PolicyDecision.BLOCK,
                required_decision=rule.decision,
                findings=tuple(findings),
            )

        if rule.decision is PolicyDecision.REQUIRE_WAIVER:
            waiver = self._find_valid_waiver(rule, request, findings)
            if waiver is None:
                return PolicyRuleEvaluation(
                    rule_id=rule.rule_id,
                    decision=PolicyDecision.REQUIRE_WAIVER,
                    required_decision=rule.decision,
                    findings=tuple(findings),
                )
            return PolicyRuleEvaluation(
                rule_id=rule.rule_id,
                decision=(
                    PolicyDecision.ALLOW
                    if not missing_evidence
                    else PolicyDecision.REQUIRE_REVIEW
                ),
                required_decision=rule.decision,
                findings=tuple(findings),
                satisfied_by_waiver_id=waiver.waiver_id,
            )

        if rule.decision is PolicyDecision.REQUIRE_REVIEW:
            if not request.authority.satisfies(rule.authority_requirement):
                findings.append(
                    PolicyEvaluationFinding(
                        finding_id=f"rule-{rule.rule_id}-authority-insufficient",
                        severity=PolicyEvaluationFindingSeverity.WARNING,
                        message=(
                            f"Authority {request.authority.value!r} does not satisfy "
                            f"required authority {rule.authority_requirement.value!r}."
                        ),
                        rule_id=rule.rule_id,
                    )
                )
                return PolicyRuleEvaluation(
                    rule_id=rule.rule_id,
                    decision=PolicyDecision.REQUIRE_REVIEW,
                    required_decision=rule.decision,
                    findings=tuple(findings),
                )
            return PolicyRuleEvaluation(
                rule_id=rule.rule_id,
                decision=(
                    PolicyDecision.ALLOW
                    if not missing_evidence
                    else PolicyDecision.REQUIRE_REVIEW
                ),
                required_decision=rule.decision,
                findings=tuple(findings),
            )

        if missing_evidence:
            return PolicyRuleEvaluation(
                rule_id=rule.rule_id,
                decision=PolicyDecision.REQUIRE_REVIEW,
                required_decision=rule.decision,
                findings=tuple(findings),
            )
        return PolicyRuleEvaluation(
            rule_id=rule.rule_id,
            decision=PolicyDecision.ALLOW,
            required_decision=rule.decision,
            findings=tuple(findings),
        )

    def _find_valid_waiver(
        self,
        rule: PolicyRule,
        request: PolicyEvaluationRequest,
        findings: list[PolicyEvaluationFinding],
    ) -> PolicyWaiver | None:
        """Find a valid waiver satisfying a waiver-required rule."""

        if not request.waiver_ids:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-required",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Policy rule requires a bounded waiver before this action can proceed.",
                    rule_id=rule.rule_id,
                )
            )
            return None

        for waiver_id in request.waiver_ids:
            waiver = self._waiver_by_id.get(waiver_id)
            if waiver is None:
                findings.append(
                    PolicyEvaluationFinding(
                        finding_id=f"rule-{rule.rule_id}-waiver-{waiver_id}-missing",
                        severity=PolicyEvaluationFindingSeverity.WARNING,
                        message="Requested waiver ID was not provided to the evaluator.",
                        rule_id=rule.rule_id,
                        waiver_id=waiver_id,
                    )
                )
                continue
            if self._waiver_satisfies_rule(waiver, rule, request, findings):
                findings.append(
                    PolicyEvaluationFinding(
                        finding_id=f"rule-{rule.rule_id}-waiver-{waiver_id}-accepted",
                        severity=PolicyEvaluationFindingSeverity.INFO,
                        message="Bounded waiver satisfies the policy rule for this request.",
                        rule_id=rule.rule_id,
                        waiver_id=waiver_id,
                    )
                )
                return waiver
        findings.append(
            PolicyEvaluationFinding(
                finding_id=f"rule-{rule.rule_id}-no-valid-waiver",
                severity=PolicyEvaluationFindingSeverity.WARNING,
                message="No requested waiver satisfied the policy rule.",
                rule_id=rule.rule_id,
            )
        )
        return None

    def _waiver_satisfies_rule(
        self,
        waiver: PolicyWaiver,
        rule: PolicyRule,
        request: PolicyEvaluationRequest,
        findings: list[PolicyEvaluationFinding],
    ) -> bool:
        """Return whether a waiver satisfies a policy rule and request context."""

        if waiver.policy_pack_id != self._policy_pack.policy_pack_id:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-{waiver.waiver_id}-wrong-pack",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Waiver belongs to a different policy pack.",
                    rule_id=rule.rule_id,
                    waiver_id=waiver.waiver_id,
                )
            )
            return False
        if not waiver.covers_rule(rule.rule_id):
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-{waiver.waiver_id}-not-covered",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Waiver does not cover this policy rule.",
                    rule_id=rule.rule_id,
                    waiver_id=waiver.waiver_id,
                )
            )
            return False
        if not waiver.authority_requirement.satisfies(rule.authority_requirement):
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-{waiver.waiver_id}-authority-low",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Waiver authority does not satisfy the rule authority requirement.",
                    rule_id=rule.rule_id,
                    waiver_id=waiver.waiver_id,
                )
            )
            return False
        try:
            expires_at = _parse_utc_timestamp(waiver.expires_at_utc, "waiver expires_at_utc")
        except ContractValueError:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-{waiver.waiver_id}-bad-expiration",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Waiver expiration timestamp is invalid.",
                    rule_id=rule.rule_id,
                    waiver_id=waiver.waiver_id,
                )
            )
            return False
        if expires_at <= request.evaluated_at:
            findings.append(
                PolicyEvaluationFinding(
                    finding_id=f"rule-{rule.rule_id}-waiver-{waiver.waiver_id}-expired",
                    severity=PolicyEvaluationFindingSeverity.WARNING,
                    message="Waiver is expired at the request evaluation time.",
                    rule_id=rule.rule_id,
                    waiver_id=waiver.waiver_id,
                )
            )
            return False
        return True


def rule_matches(rule: PolicyRule, request: PolicyEvaluationRequest) -> bool:
    """Return whether a policy rule applies to a request."""

    return (
        rule.applies_to_action(request.action_category)
        and rule.applies_to_subject(request.subject_type)
        and rule.applies_to_risk_tier(request.risk_tier)
    )


def _aggregate_decision(rule_evaluations: tuple[PolicyRuleEvaluation, ...]) -> PolicyDecision:
    """Aggregate rule decisions using fail-closed precedence."""

    decisions = tuple(evaluation.decision for evaluation in rule_evaluations)
    if any(decision is PolicyDecision.BLOCK for decision in decisions):
        return PolicyDecision.BLOCK
    if any(decision is PolicyDecision.REQUIRE_WAIVER for decision in decisions):
        return PolicyDecision.REQUIRE_WAIVER
    if any(decision is PolicyDecision.REQUIRE_REVIEW for decision in decisions):
        return PolicyDecision.REQUIRE_REVIEW
    return PolicyDecision.ALLOW
