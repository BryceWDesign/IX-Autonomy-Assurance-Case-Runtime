"""Prototype capability rollup evaluator.

Individual capability readiness reports prove local slices of the assurance
runtime. This module rolls those reports into one serious-prototype maturity
view while preserving blockers, warnings, duplicate capability claims, missing
target capability IDs, and unexpected completion claims.

This module does not replace the lower-level readiness gates and does not claim
certification, authority to operate, deployment readiness, agency endorsement, or
operational acceptance.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError, RuntimeStrEnum
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessGate,
    PrototypeReadinessReport,
)
from ix_autonomy_assurance_case_runtime.prototype_target import (
    SERIOUS_PROTOTYPE_TARGET_PERCENT,
    build_serious_prototype_targets,
)


class CapabilityLayerReport(Protocol):
    """Protocol implemented by capability-layer readiness reports."""

    @property
    def capability_id(self) -> str:
        """Return the canonical capability ID for this layer."""

    def is_complete(self) -> bool:
        """Return whether the capability layer is complete."""

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return capability IDs this layer honestly completes."""

    def summary(self) -> str:
        """Return a deterministic summary for the layer."""


class PrototypeRollupFindingSeverity(RuntimeStrEnum):
    """Severity for prototype rollup findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_rollup(self) -> bool:
        """Return whether this finding blocks rollup acceptance."""

        return self is PrototypeRollupFindingSeverity.BLOCKER


class PrototypeRollupFindingSource(RuntimeStrEnum):
    """Source that produced a prototype rollup finding."""

    LAYER = "layer"
    CAPABILITY = "capability"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class CapabilityLayerRollupEntry:
    """Normalized layer report entry used by the prototype rollup."""

    layer_id: str
    capability_id: str
    is_complete: bool
    completed_capability_ids: tuple[str, ...]
    layer_summary: str
    blocker_count: int = 0
    warning_count: int = 0

    def __post_init__(self) -> None:
        """Validate normalized layer rollup entry fields."""

        _require_identifier(self.layer_id, "layer_id")
        _require_identifier(self.capability_id, "capability_id")
        _require_text(self.layer_summary, "layer_summary")
        object.__setattr__(
            self,
            "completed_capability_ids",
            _normalize_identifier_tuple(
                self.completed_capability_ids,
                "completed_capability_ids",
            ),
        )
        if self.blocker_count < 0:
            raise ContractValueError("blocker_count must not be negative.")
        if self.warning_count < 0:
            raise ContractValueError("warning_count must not be negative.")


@dataclass(frozen=True, slots=True)
class PrototypeRollupFinding:
    """One normalized prototype rollup finding."""

    finding_id: str
    severity: PrototypeRollupFindingSeverity
    source: PrototypeRollupFindingSource
    message: str
    capability_id: str | None = None
    layer_id: str | None = None

    def __post_init__(self) -> None:
        """Validate prototype rollup finding fields."""

        _require_identifier(self.finding_id, "prototype rollup finding_id")
        _require_text(self.message, "message")
        if self.capability_id is not None:
            _require_identifier(self.capability_id, "capability_id")
        if self.layer_id is not None:
            _require_identifier(self.layer_id, "layer_id")


@dataclass(frozen=True, slots=True)
class PrototypeCapabilityRollupReport:
    """Integrated rollup report for capability-layer readiness results."""

    requested_claim_level: PrototypeClaimLevel
    readiness_report: PrototypeReadinessReport
    layer_entries: tuple[CapabilityLayerRollupEntry, ...]
    findings: tuple[PrototypeRollupFinding, ...]
    duplicate_capability_ids: tuple[str, ...]
    missing_expected_capability_ids: tuple[str, ...]
    unexpected_completed_capability_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate prototype rollup report fields."""

        object.__setattr__(
            self,
            "duplicate_capability_ids",
            _normalize_identifier_tuple(
                self.duplicate_capability_ids,
                "duplicate_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "missing_expected_capability_ids",
            _normalize_identifier_tuple(
                self.missing_expected_capability_ids,
                "missing_expected_capability_ids",
            ),
        )
        object.__setattr__(
            self,
            "unexpected_completed_capability_ids",
            _normalize_identifier_tuple(
                self.unexpected_completed_capability_ids,
                "unexpected_completed_capability_ids",
            ),
        )

    @property
    def achieved_percent(self) -> int:
        """Return the maturity percent reported by the prototype readiness gate."""

        return self.readiness_report.achieved_percent

    @property
    def blocker_count(self) -> int:
        """Return rollup blocker count."""

        return sum(finding.severity.blocks_rollup() for finding in self.findings)

    @property
    def warning_count(self) -> int:
        """Return rollup warning count."""

        return sum(
            1
            for finding in self.findings
            if finding.severity is PrototypeRollupFindingSeverity.WARNING
        )

    def target_percent_met(self) -> bool:
        """Return whether the serious prototype percent target is met."""

        return self.achieved_percent >= SERIOUS_PROTOTYPE_TARGET_PERCENT

    def completed_capability_ids(self) -> tuple[str, ...]:
        """Return unique completed capability IDs from the readiness report."""

        return self.readiness_report.completed_capability_ids

    def findings_for_capability(
        self,
        capability_id: str,
    ) -> tuple[PrototypeRollupFinding, ...]:
        """Return findings for a capability ID."""

        return tuple(
            finding for finding in self.findings if finding.capability_id == capability_id
        )

    def findings_for_layer(self, layer_id: str) -> tuple[PrototypeRollupFinding, ...]:
        """Return findings for a layer ID."""

        return tuple(finding for finding in self.findings if finding.layer_id == layer_id)

    def is_rollup_clean(self) -> bool:
        """Return whether the rollup has no blockers and meets the target percent."""

        return self.blocker_count == 0 and self.target_percent_met()

    def summary(self) -> str:
        """Return a deterministic prototype rollup summary."""

        return (
            f"prototype-rollup: {self.achieved_percent}% "
            f"({len(self.completed_capability_ids())} completed capability(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"target={SERIOUS_PROTOTYPE_TARGET_PERCENT}%)"
        )


class PrototypeCapabilityRollupEvaluator:
    """Evaluate capability-layer reports as one maturity rollup."""

    def evaluate(
        self,
        layer_reports: Iterable[CapabilityLayerReport],
        *,
        requested_claim_level: PrototypeClaimLevel = (
            PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE
        ),
        expected_capability_ids: Iterable[str] | None = None,
    ) -> PrototypeCapabilityRollupReport:
        """Evaluate capability-layer reports as one prototype maturity rollup."""

        layer_entries = tuple(
            _entry_from_report(index, report)
            for index, report in enumerate(layer_reports, start=1)
        )
        expected_ids = (
            tuple(_default_expected_capability_ids())
            if expected_capability_ids is None
            else _normalize_identifier_tuple(
                tuple(expected_capability_ids),
                "expected_capability_ids",
            )
        )
        completed_ids = _unique_completed_capability_ids(layer_entries)
        duplicate_ids = _duplicate_completed_capability_ids(layer_entries)
        missing_expected_ids = tuple(
            capability_id for capability_id in expected_ids if capability_id not in completed_ids
        )
        unexpected_ids = tuple(
            capability_id for capability_id in completed_ids if capability_id not in expected_ids
        )
        readiness_report = PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed_ids,
            requested_claim_level=requested_claim_level,
        )
        findings = (
            _layer_findings(layer_entries)
            + _capability_findings(
                layer_entries=layer_entries,
                duplicate_capability_ids=duplicate_ids,
                missing_expected_capability_ids=missing_expected_ids,
                unexpected_completed_capability_ids=unexpected_ids,
            )
            + _readiness_findings(readiness_report)
        )
        return PrototypeCapabilityRollupReport(
            requested_claim_level=requested_claim_level,
            readiness_report=readiness_report,
            layer_entries=layer_entries,
            findings=findings,
            duplicate_capability_ids=duplicate_ids,
            missing_expected_capability_ids=missing_expected_ids,
            unexpected_completed_capability_ids=unexpected_ids,
        )


def _entry_from_report(
    index: int,
    report: CapabilityLayerReport,
) -> CapabilityLayerRollupEntry:
    """Build a normalized rollup entry from a capability-layer report."""

    capability_id = _require_identifier(report.capability_id, "capability_id")
    completed_capability_ids = report.completed_capability_ids()
    return CapabilityLayerRollupEntry(
        layer_id=f"layer-{index}-{capability_id}",
        capability_id=capability_id,
        is_complete=report.is_complete(),
        completed_capability_ids=completed_capability_ids,
        layer_summary=report.summary(),
        blocker_count=_optional_int(report, "blocker_count"),
        warning_count=_optional_int(report, "warning_count"),
    )


def _optional_int(report: object, attribute_name: str) -> int:
    """Return an optional integer report attribute with strict validation."""

    value = getattr(report, attribute_name, 0)
    if not isinstance(value, int):
        raise ContractValueError(f"{attribute_name} must be an integer when present.")
    if value < 0:
        raise ContractValueError(f"{attribute_name} must not be negative.")
    return value


def _default_expected_capability_ids() -> tuple[str, ...]:
    """Return target capability IDs from the serious prototype target model."""

    return tuple(target.capability_id for target in build_serious_prototype_targets())


def _unique_completed_capability_ids(
    layer_entries: tuple[CapabilityLayerRollupEntry, ...],
) -> tuple[str, ...]:
    """Return unique completed capability IDs in first-seen order."""

    completed: list[str] = []
    for entry in layer_entries:
        completed.extend(entry.completed_capability_ids)
    return tuple(dict.fromkeys(completed))


def _duplicate_completed_capability_ids(
    layer_entries: tuple[CapabilityLayerRollupEntry, ...],
) -> tuple[str, ...]:
    """Return duplicate completed capability IDs."""

    completed: list[str] = []
    for entry in layer_entries:
        completed.extend(entry.completed_capability_ids)
    counts = Counter(completed)
    return tuple(capability_id for capability_id, count in counts.items() if count > 1)


def _layer_findings(
    layer_entries: tuple[CapabilityLayerRollupEntry, ...],
) -> tuple[PrototypeRollupFinding, ...]:
    """Build findings for incomplete or internally warning-heavy layers."""

    findings: list[PrototypeRollupFinding] = []
    if not layer_entries:
        findings.append(
            PrototypeRollupFinding(
                finding_id="prototype-rollup-no-layer-reports",
                severity=PrototypeRollupFindingSeverity.BLOCKER,
                source=PrototypeRollupFindingSource.LAYER,
                message="Prototype rollup requires at least one capability-layer report.",
            )
        )

    for entry in layer_entries:
        if not entry.is_complete:
            findings.append(
                PrototypeRollupFinding(
                    finding_id=f"{entry.layer_id}-not-complete",
                    severity=PrototypeRollupFindingSeverity.BLOCKER,
                    source=PrototypeRollupFindingSource.LAYER,
                    message="Capability-layer report is not complete.",
                    capability_id=entry.capability_id,
                    layer_id=entry.layer_id,
                )
            )
        if entry.is_complete and entry.capability_id not in entry.completed_capability_ids:
            findings.append(
                PrototypeRollupFinding(
                    finding_id=f"{entry.layer_id}-missing-own-capability-id",
                    severity=PrototypeRollupFindingSeverity.BLOCKER,
                    source=PrototypeRollupFindingSource.CAPABILITY,
                    message=(
                        "Completed capability-layer report did not emit its own capability ID."
                    ),
                    capability_id=entry.capability_id,
                    layer_id=entry.layer_id,
                )
            )
        if entry.warning_count:
            findings.append(
                PrototypeRollupFinding(
                    finding_id=f"{entry.layer_id}-layer-warnings",
                    severity=PrototypeRollupFindingSeverity.WARNING,
                    source=PrototypeRollupFindingSource.LAYER,
                    message="Capability-layer report contains warnings.",
                    capability_id=entry.capability_id,
                    layer_id=entry.layer_id,
                )
            )
    return tuple(findings)


def _capability_findings(
    *,
    layer_entries: tuple[CapabilityLayerRollupEntry, ...],
    duplicate_capability_ids: tuple[str, ...],
    missing_expected_capability_ids: tuple[str, ...],
    unexpected_completed_capability_ids: tuple[str, ...],
) -> tuple[PrototypeRollupFinding, ...]:
    """Build capability coverage findings."""

    findings: list[PrototypeRollupFinding] = []
    layer_capability_ids = tuple(entry.capability_id for entry in layer_entries)
    if len(layer_capability_ids) != len(set(layer_capability_ids)):
        findings.append(
            PrototypeRollupFinding(
                finding_id="prototype-rollup-duplicate-layer-capability-ids",
                severity=PrototypeRollupFindingSeverity.BLOCKER,
                source=PrototypeRollupFindingSource.CAPABILITY,
                message="Prototype rollup received duplicate layer capability IDs.",
            )
        )

    for capability_id in duplicate_capability_ids:
        findings.append(
            PrototypeRollupFinding(
                finding_id=f"prototype-rollup-duplicate-completed-{capability_id}",
                severity=PrototypeRollupFindingSeverity.BLOCKER,
                source=PrototypeRollupFindingSource.CAPABILITY,
                message="Capability ID was completed by more than one layer report.",
                capability_id=capability_id,
            )
        )

    for capability_id in unexpected_completed_capability_ids:
        findings.append(
            PrototypeRollupFinding(
                finding_id=f"prototype-rollup-unexpected-completed-{capability_id}",
                severity=PrototypeRollupFindingSeverity.WARNING,
                source=PrototypeRollupFindingSource.CAPABILITY,
                message="Capability ID is not part of the current serious prototype target model.",
                capability_id=capability_id,
            )
        )

    for capability_id in missing_expected_capability_ids:
        findings.append(
            PrototypeRollupFinding(
                finding_id=f"prototype-rollup-missing-expected-{capability_id}",
                severity=PrototypeRollupFindingSeverity.INFO,
                source=PrototypeRollupFindingSource.CAPABILITY,
                message="Capability ID remains incomplete in the serious prototype target model.",
                capability_id=capability_id,
            )
        )

    return tuple(findings)


def _readiness_findings(
    readiness_report: PrototypeReadinessReport,
) -> tuple[PrototypeRollupFinding, ...]:
    """Build findings from the aggregate prototype readiness report."""

    if readiness_report.achieved_percent >= SERIOUS_PROTOTYPE_TARGET_PERCENT:
        return ()
    return (
        PrototypeRollupFinding(
            finding_id="prototype-rollup-target-percent-not-met",
            severity=PrototypeRollupFindingSeverity.BLOCKER,
            source=PrototypeRollupFindingSource.READINESS,
            message=(
                "Completed capability IDs do not yet meet the serious prototype "
                f"target of {SERIOUS_PROTOTYPE_TARGET_PERCENT}%."
            ),
        ),
    )


def _normalize_identifier_tuple(values: tuple[str, ...], field_name: str) -> tuple[str, ...]:
    """Validate identifier tuples and reject duplicates."""

    normalized = tuple(_require_identifier(value, field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ContractValueError(f"{field_name} must not contain duplicate identifiers.")
    return normalized


def _require_identifier(value: str, field_name: str) -> str:
    """Validate and return a stable prototype rollup identifier."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    if normalized != value:
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in normalized:
        raise ContractValueError(f"{field_name} must not contain spaces.")
    return normalized


def _require_text(value: str, field_name: str) -> str:
    """Validate and return nonblank prototype rollup text."""

    normalized = value.strip()
    if not normalized:
        raise ContractValueError(f"{field_name} must not be blank.")
    return normalized
