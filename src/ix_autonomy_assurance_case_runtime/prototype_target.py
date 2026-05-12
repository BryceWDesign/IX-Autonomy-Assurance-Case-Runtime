"""Target capability model for the serious federal/IC/DoD prototype evolution.

This module defines the stable 80-percent prototype target used to govern the
next expansion of the runtime. It is intentionally modest: it does not claim
certification, classified deployment readiness, or operational acceptance.
Instead, it makes the missing capability families explicit so future commits can
add them without drifting into vague roadmap language.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum

BASELINE_MATURITY_PERCENT = 40
SERIOUS_PROTOTYPE_TARGET_PERCENT = 80


class PrototypeCapabilityArea(RuntimeStrEnum):
    """Capability families required for the serious prototype target."""

    REGISTRY = "registry"
    POLICY = "policy"
    FRAMEWORK_CROSSWALK = "framework_crosswalk"
    PROVENANCE = "provenance"
    TELEMETRY = "telemetry"
    SCENARIO_CAMPAIGNS = "scenario_campaigns"
    MONITORING = "monitoring"
    REVIEW_WORKFLOW = "review_workflow"
    EXPORT_PACKAGES = "export_packages"
    SECURITY_HARDENING = "security_hardening"


@dataclass(frozen=True, slots=True)
class PrototypeCapabilityTarget:
    """One measurable capability needed to reach the 80-percent prototype target."""

    capability_id: str
    area: PrototypeCapabilityArea
    name: str
    purpose: str
    acceptance_signals: tuple[str, ...]
    blocked_claims_until_met: tuple[str, ...]
    maturity_lift_points: int

    def __post_init__(self) -> None:
        """Validate that target capability records are strict and reviewable."""

        if not self.capability_id.strip():
            raise ContractValueError("Prototype capability ID must not be blank.")
        if self.capability_id != self.capability_id.strip():
            raise ContractValueError("Prototype capability ID must not contain edge whitespace.")
        if not self.name.strip():
            raise ContractValueError(f"Prototype capability {self.capability_id!r} needs a name.")
        if not self.purpose.strip():
            message = f"Prototype capability {self.capability_id!r} needs a purpose."
            raise ContractValueError(message)
        if not self.acceptance_signals:
            message = f"Prototype capability {self.capability_id!r} needs acceptance signals."
            raise ContractValueError(message)
        if not self.blocked_claims_until_met:
            message = f"Prototype capability {self.capability_id!r} needs blocked-claim limits."
            raise ContractValueError(message)
        if self.maturity_lift_points <= 0:
            message = f"Prototype capability {self.capability_id!r} must lift maturity."
            raise ContractValueError(message)
        for signal in self.acceptance_signals:
            if not signal.strip():
                message = f"Prototype capability {self.capability_id!r} has a blank signal."
                raise ContractValueError(message)
        for blocked_claim in self.blocked_claims_until_met:
            if not blocked_claim.strip():
                message = f"Prototype capability {self.capability_id!r} has a blank claim limit."
                raise ContractValueError(message)

    def requires_audit_artifact(self) -> bool:
        """Return whether this target requires explicit reviewable evidence."""

        audit_terms = (
            "audit",
            "attestation",
            "evidence",
            "ledger",
            "metadata",
            "record",
            "report",
            "review",
            "signature",
            "trace",
        )
        searchable_text = " ".join((self.purpose, *self.acceptance_signals)).lower()
        return any(term in searchable_text for term in audit_terms)


@dataclass(frozen=True, slots=True)
class PrototypeMaturityAssessment:
    """Calculated maturity posture against the 80-percent serious prototype target."""

    baseline_percent: int
    target_percent: int
    achieved_percent: int
    completed_capability_ids: tuple[str, ...]
    remaining_capability_ids: tuple[str, ...]

    @property
    def remaining_percent(self) -> int:
        """Return the remaining percentage points needed to reach the target."""

        return max(self.target_percent - self.achieved_percent, 0)

    def meets_serious_prototype_target(self) -> bool:
        """Return whether the target maturity has been reached."""

        return self.achieved_percent >= self.target_percent


def build_serious_prototype_targets() -> tuple[PrototypeCapabilityTarget, ...]:
    """Return the canonical capability targets for the 80-percent evolution."""

    return (
        PrototypeCapabilityTarget(
            capability_id="registry-layer",
            area=PrototypeCapabilityArea.REGISTRY,
            name="Model, system, and use-case registry",
            purpose=(
                "Record AI/autonomy systems, model versions, ownership, approved uses, "
                "deployment context, lifecycle state, and risk tier."
            ),
            acceptance_signals=(
                "Typed records exist for systems, models, use cases, deployments, and risk tiers.",
                "Registry entries link to assurance cases, scenario evidence, and approval state.",
                "Tests reject blank ownership, unsupported lifecycle state, "
                "and missing intended use.",
            ),
            blocked_claims_until_met=(
                "Cannot claim enterprise AI inventory support.",
                "Cannot claim model registry readiness.",
            ),
            maturity_lift_points=5,
        ),
        PrototypeCapabilityTarget(
            capability_id="policy-pack-engine",
            area=PrototypeCapabilityArea.POLICY,
            name="Policy-pack engine and waiver lifecycle",
            purpose=(
                "Evaluate machine-readable policy packs for allowed actions, blocked actions, "
                "authority requirements, review triggers, and bounded waiver decisions."
            ),
            acceptance_signals=(
                "Policy packs produce allow, review, block, or waiver-required decisions.",
                "Waivers require explicit authority, expiration, scope, and evidence references.",
                "Tests prove unsafe actions fail closed when policy or waiver data is missing.",
            ),
            blocked_claims_until_met=(
                "Cannot claim policy-as-code governance.",
                "Cannot claim delegated-risk acceptance tracking.",
            ),
            maturity_lift_points=5,
        ),
        PrototypeCapabilityTarget(
            capability_id="framework-crosswalks",
            area=PrototypeCapabilityArea.FRAMEWORK_CROSSWALK,
            name="Federal assurance framework crosswalks",
            purpose=(
                "Map runtime assurance artifacts to recognized governance, risk, acquisition, "
                "and testing control objectives without claiming official certification."
            ),
            acceptance_signals=(
                "Control objectives can be mapped to evidence, claims, scenarios, and reports.",
                "Coverage reports identify satisfied, partial, missing, and out-of-scope controls.",
                "Tests prove unknown frameworks and duplicate control IDs are rejected.",
            ),
            blocked_claims_until_met=(
                "Cannot claim federal-control alignment evidence.",
                "Cannot claim reviewer-ready coverage reporting.",
            ),
            maturity_lift_points=4,
        ),
        PrototypeCapabilityTarget(
            capability_id="signed-provenance",
            area=PrototypeCapabilityArea.PROVENANCE,
            name="Signed provenance and evidence attestation",
            purpose=(
                "Attach artifact digests, signer identity metadata, signature records, and "
                "verification status to evidence bundles and run-ledger entries."
            ),
            acceptance_signals=(
                "Evidence manifests include deterministic artifact digests and signer metadata.",
                "Signature verification distinguishes verified, unsigned, mismatched, "
                "and expired states.",
                "Tamper tests prove changed evidence cannot silently retain a valid attestation.",
            ),
            blocked_claims_until_met=(
                "Cannot claim signed evidence package support.",
                "Cannot claim provenance-backed artifact integrity.",
            ),
            maturity_lift_points=5,
        ),
        PrototypeCapabilityTarget(
            capability_id="telemetry-adapters",
            area=PrototypeCapabilityArea.TELEMETRY,
            name="Telemetry adapter and source-trust boundary",
            purpose=(
                "Normalize runtime telemetry from typed adapters while preserving source identity, "
                "timestamp posture, schema validation, replay metadata, and trust limits."
            ),
            acceptance_signals=(
                "Adapters produce canonical telemetry envelopes with source "
                "and timestamp metadata.",
                "Stale, malformed, spoofed, and unsupported telemetry is rejected or degraded.",
                "Replay fixtures can reproduce accepted and rejected telemetry decisions.",
            ),
            blocked_claims_until_met=(
                "Cannot claim real telemetry ingestion posture.",
                "Cannot claim source-trust-aware runtime evaluation.",
            ),
            maturity_lift_points=4,
        ),
        PrototypeCapabilityTarget(
            capability_id="scenario-campaign-runner",
            area=PrototypeCapabilityArea.SCENARIO_CAMPAIGNS,
            name="Scenario campaign runner and adversarial lab",
            purpose=(
                "Run multi-scenario evaluation campaigns with acceptance thresholds, adversarial "
                "probes, regression posture, failure clustering, and campaign evidence reports."
            ),
            acceptance_signals=(
                "Campaigns aggregate multiple scenario runs into deterministic "
                "pass/fail summaries.",
                "Adversarial, degraded-mode, regression, and stress campaign tags are supported.",
                "Tests prove threshold failures cannot be reported as accepted campaigns.",
            ),
            blocked_claims_until_met=(
                "Cannot claim campaign-level T&E support.",
                "Cannot claim adversarial evaluation coverage.",
            ),
            maturity_lift_points=5,
        ),
        PrototypeCapabilityTarget(
            capability_id="monitoring-incidents",
            area=PrototypeCapabilityArea.MONITORING,
            name="Monitoring, drift, and incident trail",
            purpose=(
                "Track lifecycle monitoring snapshots, drift posture, incident records, "
                "revalidation triggers, and degraded confidence over time."
            ),
            acceptance_signals=(
                "Monitoring snapshots preserve system, model, scenario, and evidence references.",
                "Drift and incident records can force revalidation or authority review.",
                "Tests prove stale monitoring data cannot support current acceptance claims.",
            ),
            blocked_claims_until_met=(
                "Cannot claim lifecycle monitoring support.",
                "Cannot claim performance-shift response tracking.",
            ),
            maturity_lift_points=4,
        ),
        PrototypeCapabilityTarget(
            capability_id="review-workflow",
            area=PrototypeCapabilityArea.REVIEW_WORKFLOW,
            name="Reviewer workflow, signoff, and dissent trail",
            purpose=(
                "Represent reviewer roles, approvals, conditional approvals, dissent, unresolved "
                "findings, and disposition history as audit-ready workflow records."
            ),
            acceptance_signals=(
                "Review records preserve actor role, authority scope, disposition, and rationale.",
                "Unresolved findings block acceptance unless a bounded waiver "
                "explicitly covers them.",
                "Tests prove dissent and missing rationale survive export and "
                "cannot be erased silently.",
            ),
            blocked_claims_until_met=(
                "Cannot claim structured human governance workflow.",
                "Cannot claim audit-ready signoff support.",
            ),
            maturity_lift_points=3,
        ),
        PrototypeCapabilityTarget(
            capability_id="audit-export-packages",
            area=PrototypeCapabilityArea.EXPORT_PACKAGES,
            name="Audit, T&E, acquisition, and governance package exports",
            purpose=(
                "Produce deterministic export packages that collect claims, evidence, policy, "
                "traceability, review state, provenance, and unresolved gaps for external review."
            ),
            acceptance_signals=(
                "Export packages include manifest, evidence index, policy posture, "
                "and open findings.",
                "Different package profiles can emphasize audit, T&E, acquisition, "
                "or governance review.",
                "Tests prove missing required sections fail package validation.",
            ),
            blocked_claims_until_met=(
                "Cannot claim oversight-ready package generation.",
                "Cannot claim acquisition-review package support.",
            ),
            maturity_lift_points=3,
        ),
        PrototypeCapabilityTarget(
            capability_id="security-hardening",
            area=PrototypeCapabilityArea.SECURITY_HARDENING,
            name="Security hardening and adversarial evidence defenses",
            purpose=(
                "Expand threat tests for tampered evidence, replay abuse, unsafe waiver scope, "
                "unsupported policy bypass, and misleading provenance claims."
            ),
            acceptance_signals=(
                "Adversarial tests cover tamper, replay, stale input, and policy-bypass attempts.",
                "Security documentation distinguishes local prototype limits from "
                "deployment controls.",
                "Tests prove the runtime fails closed on unsupported trust or authority claims.",
            ),
            blocked_claims_until_met=(
                "Cannot claim hardened evidence workflow posture.",
                "Cannot claim adversarial misuse resistance beyond the current local prototype.",
            ),
            maturity_lift_points=2,
        ),
    )


def assess_serious_prototype_maturity(
    completed_capability_ids: Iterable[str],
) -> PrototypeMaturityAssessment:
    """Assess maturity progress against the serious prototype target capabilities."""

    targets = build_serious_prototype_targets()
    target_by_id = {target.capability_id: target for target in targets}
    completed_unique = tuple(dict.fromkeys(completed_capability_ids))
    unknown_ids = tuple(
        capability_id for capability_id in completed_unique if capability_id not in target_by_id
    )
    if unknown_ids:
        formatted = ", ".join(repr(capability_id) for capability_id in unknown_ids)
        raise ContractValueError(f"Unknown prototype capability ID(s): {formatted}")

    achieved_lift = sum(
        target_by_id[capability_id].maturity_lift_points for capability_id in completed_unique
    )
    achieved_percent = min(
        BASELINE_MATURITY_PERCENT + achieved_lift,
        SERIOUS_PROTOTYPE_TARGET_PERCENT,
    )
    remaining_ids = tuple(
        target.capability_id for target in targets if target.capability_id not in completed_unique
    )

    return PrototypeMaturityAssessment(
        baseline_percent=BASELINE_MATURITY_PERCENT,
        target_percent=SERIOUS_PROTOTYPE_TARGET_PERCENT,
        achieved_percent=achieved_percent,
        completed_capability_ids=completed_unique,
        remaining_capability_ids=remaining_ids,
    )
