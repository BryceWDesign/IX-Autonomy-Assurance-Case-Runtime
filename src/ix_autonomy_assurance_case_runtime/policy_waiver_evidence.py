"""Evidence coverage validation for policy waivers.

The policy evaluator can determine whether a waiver satisfies a policy rule, but
serious governance also needs proof that waiver evidence exists, validates, and
matches the active policy pack. This module adds that validation layer without
claiming external approval, certification, or agency authorization.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle
from ix_autonomy_assurance_case_runtime.policy import PolicyPack, PolicyWaiver


def _parse_utc_timestamp(value: str, field_name: str) -> datetime:
    """Parse an ISO-8601 timestamp and normalize it to UTC."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractValueError(f"{field_name} must be an ISO-8601 UTC timestamp.") from exc
    if parsed.tzinfo is None:
        raise ContractValueError(f"{field_name} must include a timezone.")
    return parsed.astimezone(UTC)


class PolicyWaiverEvidenceFindingSeverity(RuntimeStrEnum):
    """Severity for waiver evidence coverage findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_acceptance(self) -> bool:
        """Return whether this finding blocks waiver evidence acceptance."""

        return self is PolicyWaiverEvidenceFindingSeverity.BLOCKER


class PolicyWaiverReferenceType(RuntimeStrEnum):
    """Reference types used in waiver evidence findings."""

    POLICY_PACK = "policy_pack"
    POLICY_RULE = "policy_rule"
    WAIVER = "waiver"
    EVIDENCE_BUNDLE = "evidence_bundle"


@dataclass(frozen=True, slots=True)
class PolicyWaiverEvidenceFinding:
    """One policy waiver evidence coverage finding."""

    finding_id: str
    severity: PolicyWaiverEvidenceFindingSeverity
    message: str
    waiver_id: str
    reference_id: str | None = None
    reference_type: PolicyWaiverReferenceType | None = None

    def __post_init__(self) -> None:
        """Validate waiver evidence finding fields."""

        if not self.finding_id.strip():
            raise ContractValueError("Policy waiver evidence finding ID must not be blank.")
        if self.finding_id != self.finding_id.strip():
            raise ContractValueError(
                "Policy waiver evidence finding ID must not contain edge whitespace."
            )
        if not self.message.strip():
            raise ContractValueError(
                f"Policy waiver evidence finding {self.finding_id!r} needs a message."
            )
        if not self.waiver_id.strip():
            raise ContractValueError(
                f"Policy waiver evidence finding {self.finding_id!r} needs a waiver ID."
            )
        if self.reference_id is not None and not self.reference_id.strip():
            raise ContractValueError(
                f"Policy waiver evidence finding {self.finding_id!r} has a blank reference ID."
            )
        if (self.reference_id is None) != (self.reference_type is None):
            raise ContractValueError(
                f"Policy waiver evidence finding {self.finding_id!r} must pair reference ID "
                "and reference type."
            )


@dataclass(frozen=True, slots=True)
class PolicyWaiverEvidenceCoverageReport:
    """Coverage report for waiver evidence and policy-pack references."""

    policy_pack_id: str
    waiver_count: int
    referenced_bundle_count: int
    provided_bundle_count: int
    findings: tuple[PolicyWaiverEvidenceFinding, ...]

    @property
    def blocker_count(self) -> int:
        """Return blocker count for waiver evidence coverage."""

        return sum(1 for finding in self.findings if finding.severity.blocks_acceptance())

    @property
    def warning_count(self) -> int:
        """Return warning count for waiver evidence coverage."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is PolicyWaiverEvidenceFindingSeverity.WARNING
        )

    def is_coverage_ready(self) -> bool:
        """Return whether waiver evidence coverage has no blockers."""

        return self.blocker_count == 0

    def findings_for_waiver(self, waiver_id: str) -> tuple[PolicyWaiverEvidenceFinding, ...]:
        """Return findings attached to a specific waiver."""

        return tuple(finding for finding in self.findings if finding.waiver_id == waiver_id)

    def summary(self) -> str:
        """Return a deterministic waiver evidence coverage summary."""

        return (
            "policy-waiver-evidence: "
            f"{self.waiver_count} waiver(s), "
            f"{self.referenced_bundle_count} referenced bundle(s), "
            f"{self.provided_bundle_count} provided bundle(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s)"
        )


class PolicyWaiverEvidenceValidator:
    """Validate policy waiver references and evidence coverage."""

    def __init__(self, policy_pack: PolicyPack, bundles: Iterable[EvidenceBundle]) -> None:
        """Create a validator for one policy pack and available evidence bundles."""

        self._policy_pack = policy_pack
        self._bundle_by_id = self._index_bundles(bundles)

    def validate(
        self,
        waivers: Iterable[PolicyWaiver],
        *,
        as_of_utc: str | None = None,
    ) -> PolicyWaiverEvidenceCoverageReport:
        """Validate waiver evidence, rule coverage, policy-pack linkage, and expiration."""

        waiver_tuple = tuple(waivers)
        self._validate_unique_waivers(waiver_tuple)
        findings: list[PolicyWaiverEvidenceFinding] = []
        findings.extend(self._validate_waiver_policy_references(waiver_tuple))
        findings.extend(self._validate_waiver_evidence_references(waiver_tuple))
        if as_of_utc is not None:
            findings.extend(self._validate_expiration(waiver_tuple, as_of_utc))

        referenced_bundle_ids = {
            bundle_id for waiver in waiver_tuple for bundle_id in waiver.evidence_bundle_ids
        }
        return PolicyWaiverEvidenceCoverageReport(
            policy_pack_id=self._policy_pack.policy_pack_id,
            waiver_count=len(waiver_tuple),
            referenced_bundle_count=len(referenced_bundle_ids),
            provided_bundle_count=len(self._bundle_by_id),
            findings=tuple(findings),
        )

    @staticmethod
    def _index_bundles(bundles: Iterable[EvidenceBundle]) -> dict[str, EvidenceBundle]:
        """Index evidence bundles and reject duplicate bundle IDs."""

        indexed: dict[str, EvidenceBundle] = {}
        for bundle in bundles:
            if bundle.bundle_id in indexed:
                raise ContractValueError(f"Duplicate evidence bundle ID {bundle.bundle_id!r}.")
            indexed[bundle.bundle_id] = bundle
        return indexed

    @staticmethod
    def _validate_unique_waivers(waivers: tuple[PolicyWaiver, ...]) -> None:
        """Reject duplicate waiver IDs in the validation input."""

        waiver_ids = tuple(waiver.waiver_id for waiver in waivers)
        if len(waiver_ids) != len(set(waiver_ids)):
            raise ContractValueError("policy waiver evidence input has duplicate waiver IDs.")

    def _validate_waiver_policy_references(
        self,
        waivers: tuple[PolicyWaiver, ...],
    ) -> tuple[PolicyWaiverEvidenceFinding, ...]:
        """Validate waiver-to-policy-pack and waiver-to-rule references."""

        findings: list[PolicyWaiverEvidenceFinding] = []
        for waiver in waivers:
            if waiver.policy_pack_id != self._policy_pack.policy_pack_id:
                findings.append(
                    PolicyWaiverEvidenceFinding(
                        finding_id=f"waiver-{waiver.waiver_id}-wrong-policy-pack",
                        severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
                        message="Waiver references a different policy pack.",
                        waiver_id=waiver.waiver_id,
                        reference_id=waiver.policy_pack_id,
                        reference_type=PolicyWaiverReferenceType.POLICY_PACK,
                    )
                )
            for rule_id in waiver.covered_rule_ids:
                if self._policy_pack.rule_by_id(rule_id) is None:
                    findings.append(
                        PolicyWaiverEvidenceFinding(
                            finding_id=f"waiver-{waiver.waiver_id}-missing-rule-{rule_id}",
                            severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
                            message="Waiver covers a policy rule that is not present in the pack.",
                            waiver_id=waiver.waiver_id,
                            reference_id=rule_id,
                            reference_type=PolicyWaiverReferenceType.POLICY_RULE,
                        )
                    )
        return tuple(findings)

    def _validate_waiver_evidence_references(
        self,
        waivers: tuple[PolicyWaiver, ...],
    ) -> tuple[PolicyWaiverEvidenceFinding, ...]:
        """Validate waiver evidence bundle references and bundle integrity."""

        findings: list[PolicyWaiverEvidenceFinding] = []
        for waiver in waivers:
            for bundle_id in waiver.evidence_bundle_ids:
                bundle = self._bundle_by_id.get(bundle_id)
                if bundle is None:
                    findings.append(
                        PolicyWaiverEvidenceFinding(
                            finding_id=f"waiver-{waiver.waiver_id}-missing-evidence-{bundle_id}",
                            severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
                            message="Waiver references a missing evidence bundle.",
                            waiver_id=waiver.waiver_id,
                            reference_id=bundle_id,
                            reference_type=PolicyWaiverReferenceType.EVIDENCE_BUNDLE,
                        )
                    )
                    continue

                validation = bundle.validate_integrity()
                for error in validation.errors:
                    findings.append(
                        PolicyWaiverEvidenceFinding(
                            finding_id=f"waiver-{waiver.waiver_id}-evidence-{bundle_id}-error",
                            severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
                            message=error,
                            waiver_id=waiver.waiver_id,
                            reference_id=bundle_id,
                            reference_type=PolicyWaiverReferenceType.EVIDENCE_BUNDLE,
                        )
                    )
                for warning in validation.warnings:
                    findings.append(
                        PolicyWaiverEvidenceFinding(
                            finding_id=f"waiver-{waiver.waiver_id}-evidence-{bundle_id}-warning",
                            severity=PolicyWaiverEvidenceFindingSeverity.WARNING,
                            message=warning,
                            waiver_id=waiver.waiver_id,
                            reference_id=bundle_id,
                            reference_type=PolicyWaiverReferenceType.EVIDENCE_BUNDLE,
                        )
                    )
        return tuple(findings)

    @staticmethod
    def _validate_expiration(
        waivers: tuple[PolicyWaiver, ...],
        as_of_utc: str,
    ) -> tuple[PolicyWaiverEvidenceFinding, ...]:
        """Validate waiver expiration against a provided UTC timestamp."""

        as_of = _parse_utc_timestamp(as_of_utc, "policy waiver evidence as_of_utc")
        findings: list[PolicyWaiverEvidenceFinding] = []
        for waiver in waivers:
            expires_at = _parse_utc_timestamp(
                waiver.expires_at_utc,
                f"waiver {waiver.waiver_id!r} expires_at_utc",
            )
            if expires_at <= as_of:
                findings.append(
                    PolicyWaiverEvidenceFinding(
                        finding_id=f"waiver-{waiver.waiver_id}-expired",
                        severity=PolicyWaiverEvidenceFindingSeverity.BLOCKER,
                        message="Waiver is expired at the coverage evaluation time.",
                        waiver_id=waiver.waiver_id,
                        reference_id=waiver.expires_at_utc,
                        reference_type=PolicyWaiverReferenceType.WAIVER,
                    )
                )
        return tuple(findings)
