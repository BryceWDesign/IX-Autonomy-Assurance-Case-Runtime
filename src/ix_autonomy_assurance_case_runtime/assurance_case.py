"""Assurance-case domain model.

This module defines the core evidence-backed structure used by the runtime:

mission context -> claims -> hazards -> controls -> mitigations -> verification
criteria -> evidence.

The model is intentionally deterministic and validation-heavy. It does not treat
a claim as trustworthy merely because it exists; references must resolve, severe
hazards must have controls or mitigations, and review-ready cases must pass
reference validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ix_autonomy_assurance_case_runtime.contracts import (
    AssuranceCaseStatus,
    EvidenceStatus,
    HazardSeverity,
    VerificationResult,
)


class AssuranceModelError(ValueError):
    """Raised when an assurance-case artifact is malformed."""


def _require_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AssuranceModelError(f"{field_name} must not be blank.")
    return normalized


def _normalize_ids(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    normalized = tuple(_require_text(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise AssuranceModelError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    """Evidence reference attached to claims, hazards, controls, or criteria."""

    evidence_id: str
    description: str
    source: str
    status: EvidenceStatus = EvidenceStatus.PROVIDED
    supports: tuple[str, ...] = field(default_factory=tuple)
    content_hash: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_id", _require_text(self.evidence_id, "evidence_id"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(self, "source", _require_text(self.source, "source"))
        object.__setattr__(self, "supports", _normalize_ids(self.supports, "supports"))

        if self.content_hash is not None:
            object.__setattr__(
                self,
                "content_hash",
                _require_text(self.content_hash, "content_hash"),
            )

    def is_usable(self) -> bool:
        """Return whether this evidence can currently support assurance claims."""

        return self.status.is_usable()


@dataclass(frozen=True, slots=True)
class Assumption:
    """Assumption that must remain true for an assurance argument to hold."""

    assumption_id: str
    statement: str
    rationale: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "assumption_id",
            _require_text(self.assumption_id, "assumption_id"),
        )
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(self, "rationale", _require_text(self.rationale, "rationale"))
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )


@dataclass(frozen=True, slots=True)
class VerificationCriterion:
    """Checkable acceptance criterion for a claim, hazard control, or scenario."""

    criterion_id: str
    statement: str
    verification_method: str
    expected_result: str
    result: VerificationResult = VerificationResult.NOT_RUN
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "criterion_id",
            _require_text(self.criterion_id, "criterion_id"),
        )
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(
            self,
            "verification_method",
            _require_text(self.verification_method, "verification_method"),
        )
        object.__setattr__(
            self,
            "expected_result",
            _require_text(self.expected_result, "expected_result"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )

    def supports_acceptance(self) -> bool:
        """Return whether this criterion has passed verification."""

        return self.result.is_success()


@dataclass(frozen=True, slots=True)
class Control:
    """Control intended to constrain or reduce autonomy hazard risk."""

    control_id: str
    name: str
    description: str
    mitigates_hazard_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_id", _require_text(self.control_id, "control_id"))
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "mitigates_hazard_ids",
            _normalize_ids(self.mitigates_hazard_ids, "mitigates_hazard_ids"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )

        if not self.mitigates_hazard_ids:
            raise AssuranceModelError("mitigates_hazard_ids must not be empty.")


@dataclass(frozen=True, slots=True)
class Mitigation:
    """Specific mitigation linking one hazard to one control."""

    mitigation_id: str
    hazard_id: str
    control_id: str
    description: str
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mitigation_id",
            _require_text(self.mitigation_id, "mitigation_id"),
        )
        object.__setattr__(self, "hazard_id", _require_text(self.hazard_id, "hazard_id"))
        object.__setattr__(self, "control_id", _require_text(self.control_id, "control_id"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )


@dataclass(frozen=True, slots=True)
class Hazard:
    """Autonomy hazard tracked by severity, controls, mitigations, and evidence."""

    hazard_id: str
    title: str
    description: str
    severity: HazardSeverity
    control_ids: tuple[str, ...] = field(default_factory=tuple)
    mitigation_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "hazard_id", _require_text(self.hazard_id, "hazard_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "description", _require_text(self.description, "description"))
        object.__setattr__(self, "control_ids", _normalize_ids(self.control_ids, "control_ids"))
        object.__setattr__(
            self,
            "mitigation_ids",
            _normalize_ids(self.mitigation_ids, "mitigation_ids"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )

    def requires_control(self) -> bool:
        """Return whether the hazard severity requires a control or mitigation."""

        return self.severity.requires_mitigation()

    def has_control_path(self) -> bool:
        """Return whether the hazard references at least one control or mitigation."""

        return bool(self.control_ids or self.mitigation_ids)


@dataclass(frozen=True, slots=True)
class AssuranceClaim:
    """Evidence-backed claim in an assurance case."""

    claim_id: str
    statement: str
    argument: str
    subclaim_ids: tuple[str, ...] = field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = field(default_factory=tuple)
    assumption_ids: tuple[str, ...] = field(default_factory=tuple)
    verification_criterion_ids: tuple[str, ...] = field(default_factory=tuple)
    verification_result: VerificationResult = VerificationResult.NOT_RUN

    def __post_init__(self) -> None:
        object.__setattr__(self, "claim_id", _require_text(self.claim_id, "claim_id"))
        object.__setattr__(self, "statement", _require_text(self.statement, "statement"))
        object.__setattr__(self, "argument", _require_text(self.argument, "argument"))
        object.__setattr__(
            self,
            "subclaim_ids",
            _normalize_ids(self.subclaim_ids, "subclaim_ids"),
        )
        object.__setattr__(
            self,
            "evidence_ids",
            _normalize_ids(self.evidence_ids, "evidence_ids"),
        )
        object.__setattr__(
            self,
            "assumption_ids",
            _normalize_ids(self.assumption_ids, "assumption_ids"),
        )
        object.__setattr__(
            self,
            "verification_criterion_ids",
            _normalize_ids(
                self.verification_criterion_ids,
                "verification_criterion_ids",
            ),
        )

    def has_support_path(self) -> bool:
        """Return whether the claim has evidence, subclaims, or verification criteria."""

        return bool(
            self.evidence_ids
            or self.subclaim_ids
            or self.verification_criterion_ids
        )


@dataclass(frozen=True, slots=True)
class AssuranceCaseValidationReport:
    """Validation result for an assurance case."""

    errors: tuple[str, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return whether the assurance case has no validation errors."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class AssuranceCase:
    """Top-level assurance case for an AI/autonomous system evaluation."""

    case_id: str
    title: str
    system_name: str
    mission_context: str
    status: AssuranceCaseStatus = AssuranceCaseStatus.DRAFT
    claims: tuple[AssuranceClaim, ...] = field(default_factory=tuple)
    hazards: tuple[Hazard, ...] = field(default_factory=tuple)
    controls: tuple[Control, ...] = field(default_factory=tuple)
    mitigations: tuple[Mitigation, ...] = field(default_factory=tuple)
    assumptions: tuple[Assumption, ...] = field(default_factory=tuple)
    evidence: tuple[EvidenceLink, ...] = field(default_factory=tuple)
    verification_criteria: tuple[VerificationCriterion, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "case_id", _require_text(self.case_id, "case_id"))
        object.__setattr__(self, "title", _require_text(self.title, "title"))
        object.__setattr__(self, "system_name", _require_text(self.system_name, "system_name"))
        object.__setattr__(
            self,
            "mission_context",
            _require_text(self.mission_context, "mission_context"),
        )

    def evidence_index(self) -> dict[str, EvidenceLink]:
        """Return evidence records keyed by evidence identifier."""

        return {item.evidence_id: item for item in self.evidence}

    def claim_index(self) -> dict[str, AssuranceClaim]:
        """Return claims keyed by claim identifier."""

        return {item.claim_id: item for item in self.claims}

    def hazard_index(self) -> dict[str, Hazard]:
        """Return hazards keyed by hazard identifier."""

        return {item.hazard_id: item for item in self.hazards}

    def control_index(self) -> dict[str, Control]:
        """Return controls keyed by control identifier."""

        return {item.control_id: item for item in self.controls}

    def mitigation_index(self) -> dict[str, Mitigation]:
        """Return mitigations keyed by mitigation identifier."""

        return {item.mitigation_id: item for item in self.mitigations}

    def assumption_index(self) -> dict[str, Assumption]:
        """Return assumptions keyed by assumption identifier."""

        return {item.assumption_id: item for item in self.assumptions}

    def verification_criterion_index(self) -> dict[str, VerificationCriterion]:
        """Return verification criteria keyed by criterion identifier."""

        return {item.criterion_id: item for item in self.verification_criteria}

    def validate_references(self) -> AssuranceCaseValidationReport:
        """Validate internal references and return errors/warnings."""

        errors: list[str] = []
        warnings: list[str] = []

        self._validate_unique_identifiers(errors)
        evidence = self.evidence_index()
        claims = self.claim_index()
        hazards = self.hazard_index()
        controls = self.control_index()
        mitigations = self.mitigation_index()
        assumptions = self.assumption_index()
        criteria = self.verification_criterion_index()

        if not self.claims:
            errors.append("Assurance case must contain at least one claim.")

        for claim in self.claims:
            self._require_existing(claim.evidence_ids, evidence, claim.claim_id, "evidence", errors)
            self._require_existing(claim.subclaim_ids, claims, claim.claim_id, "subclaim", errors)
            self._require_existing(
                claim.assumption_ids,
                assumptions,
                claim.claim_id,
                "assumption",
                errors,
            )
            self._require_existing(
                claim.verification_criterion_ids,
                criteria,
                claim.claim_id,
                "verification criterion",
                errors,
            )

            if not claim.has_support_path():
                warnings.append(f"Claim {claim.claim_id!r} has no support path.")

        for hazard in self.hazards:
            self._require_existing(hazard.control_ids, controls, hazard.hazard_id, "control", errors)
            self._require_existing(
                hazard.mitigation_ids,
                mitigations,
                hazard.hazard_id,
                "mitigation",
                errors,
            )
            self._require_existing(hazard.evidence_ids, evidence, hazard.hazard_id, "evidence", errors)

            if hazard.requires_control() and not hazard.has_control_path():
                errors.append(
                    f"Hazard {hazard.hazard_id!r} is {hazard.severity.value} "
                    "and requires at least one control or mitigation."
                )

        for control in self.controls:
            self._require_existing(
                control.mitigates_hazard_ids,
                hazards,
                control.control_id,
                "hazard",
                errors,
            )
            self._require_existing(control.evidence_ids, evidence, control.control_id, "evidence", errors)

        for mitigation in self.mitigations:
            self._require_existing((mitigation.hazard_id,), hazards, mitigation.mitigation_id, "hazard", errors)
            self._require_existing(
                (mitigation.control_id,),
                controls,
                mitigation.mitigation_id,
                "control",
                errors,
            )
            self._require_existing(
                mitigation.evidence_ids,
                evidence,
                mitigation.mitigation_id,
                "evidence",
                errors,
            )

        for assumption in self.assumptions:
            self._require_existing(
                assumption.evidence_ids,
                evidence,
                assumption.assumption_id,
                "evidence",
                errors,
            )

        for criterion in self.verification_criteria:
            self._require_existing(
                criterion.evidence_ids,
                evidence,
                criterion.criterion_id,
                "evidence",
                errors,
            )

        for item in self.evidence:
            if not item.is_usable():
                warnings.append(
                    f"Evidence {item.evidence_id!r} is referenced with status "
                    f"{item.status.value!r}."
                )

        if self.status.requires_review() and errors:
            errors.append("Case cannot be ready for review while validation errors exist.")

        if self.status is AssuranceCaseStatus.ACCEPTED and errors:
            errors.append("Case cannot be accepted while validation errors exist.")

        return AssuranceCaseValidationReport(
            errors=tuple(errors),
            warnings=tuple(warnings),
        )

    def unresolved_hazard_ids(self) -> tuple[str, ...]:
        """Return severe hazard identifiers without a control or mitigation path."""

        return tuple(
            hazard.hazard_id
            for hazard in self.hazards
            if hazard.requires_control() and not hazard.has_control_path()
        )

    def unsupported_claim_ids(self) -> tuple[str, ...]:
        """Return claim identifiers that have no evidence, subclaims, or criteria."""

        return tuple(claim.claim_id for claim in self.claims if not claim.has_support_path())

    def ready_for_human_review(self) -> bool:
        """Return whether the case passes validation and is marked for review."""

        return self.status.requires_review() and self.validate_references().is_valid

    def _validate_unique_identifiers(self, errors: list[str]) -> None:
        artifact_ids = (
            tuple(claim.claim_id for claim in self.claims)
            + tuple(hazard.hazard_id for hazard in self.hazards)
            + tuple(control.control_id for control in self.controls)
            + tuple(mitigation.mitigation_id for mitigation in self.mitigations)
            + tuple(assumption.assumption_id for assumption in self.assumptions)
            + tuple(item.evidence_id for item in self.evidence)
            + tuple(criterion.criterion_id for criterion in self.verification_criteria)
        )
        duplicates = sorted({artifact_id for artifact_id in artifact_ids if artifact_ids.count(artifact_id) > 1})

        for duplicate in duplicates:
            errors.append(f"Artifact identifier {duplicate!r} is duplicated.")

    @staticmethod
    def _require_existing(
        ids: tuple[str, ...],
        index: dict[str, object],
        owner_id: str,
        reference_name: str,
        errors: list[str],
    ) -> None:
        for reference_id in ids:
            if reference_id not in index:
                errors.append(
                    f"Artifact {owner_id!r} references missing {reference_name} "
                    f"{reference_id!r}."
                )
