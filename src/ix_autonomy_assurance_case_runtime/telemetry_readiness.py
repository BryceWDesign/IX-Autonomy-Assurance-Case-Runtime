"""Telemetry adapter readiness decision surface.

Telemetry source, schema, replay, and adapter-normalization records only support
prototype maturity when they prove that bounded telemetry can be normalized into
runtime-usable envelopes. This module turns those checks into the capability
gate for the ``telemetry-adapters`` target.

The checks are local prototype checks only. They do not claim live sensor
integration, classified feed handling, external time authority, deployment
readiness, authority to operate, certification, or agency acceptance.
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
from ix_autonomy_assurance_case_runtime.telemetry_adapter import (
    TelemetryAdapterCatalog,
    TelemetryAdapterDecision,
    TelemetryAdapterFindingSeverity,
    TelemetryAdapterReport,
)

TELEMETRY_CAPABILITY_ID = "telemetry-adapters"


class TelemetryReadinessDecision(RuntimeStrEnum):
    """Decision for whether telemetry adapters can support prototype maturity."""

    COMPLETE = "complete"
    LIMITED = "limited"
    BLOCKED = "blocked"

    def supports_capability_completion(self) -> bool:
        """Return whether this decision completes the telemetry capability."""

        return self is TelemetryReadinessDecision.COMPLETE

    def blocks_claim_progress(self) -> bool:
        """Return whether this decision blocks telemetry-based maturity progress."""

        return self is TelemetryReadinessDecision.BLOCKED


class TelemetryReadinessFindingSeverity(RuntimeStrEnum):
    """Severity for normalized telemetry-readiness findings."""

    INFO = "info"
    WARNING = "warning"
    BLOCKER = "blocker"

    def blocks_completion(self) -> bool:
        """Return whether this finding blocks telemetry capability completion."""

        return self is TelemetryReadinessFindingSeverity.BLOCKER


class TelemetryReadinessFindingSource(RuntimeStrEnum):
    """Source subsystem that produced a telemetry-readiness finding."""

    CATALOG = "catalog"
    ADAPTER_REPORT = "adapter_report"
    ENVELOPE = "envelope"
    REPLAY = "replay"
    READINESS = "readiness"


@dataclass(frozen=True, slots=True)
class TelemetryReadinessFinding:
    """One normalized telemetry-readiness finding."""

    finding_id: str
    severity: TelemetryReadinessFindingSeverity
    source: TelemetryReadinessFindingSource
    message: str
    telemetry_source_id: str | None = None
    schema_id: str | None = None
    input_id: str | None = None
    envelope_id: str | None = None
    replay_record_id: str | None = None
    field_name: str | None = None
    source_finding_id: str | None = None

    def __post_init__(self) -> None:
        """Validate readiness finding fields."""

        _require_identifier(self.finding_id, "telemetry readiness finding_id")
        if not self.message.strip():
            raise ContractValueError(
                f"Telemetry readiness finding {self.finding_id!r} needs a message."
            )
        for field_name, value in (
            ("telemetry_source_id", self.telemetry_source_id),
            ("schema_id", self.schema_id),
            ("input_id", self.input_id),
            ("envelope_id", self.envelope_id),
            ("replay_record_id", self.replay_record_id),
            ("field_name", self.field_name),
            ("source_finding_id", self.source_finding_id),
        ):
            if value is not None:
                _require_identifier(value, field_name)


@dataclass(frozen=True, slots=True)
class TelemetryLayerReadinessReport:
    """Combined readiness report for the telemetry-adapter capability layer."""

    decision: TelemetryReadinessDecision
    source_count: int
    schema_count: int
    replay_record_count: int
    adapter_report_count: int
    findings: tuple[TelemetryReadinessFinding, ...]
    capability_id: str = TELEMETRY_CAPABILITY_ID

    def __post_init__(self) -> None:
        """Validate telemetry readiness report counters and capability ID."""

        _require_identifier(self.capability_id, "capability_id")
        for field_name, value in (
            ("source_count", self.source_count),
            ("schema_count", self.schema_count),
            ("replay_record_count", self.replay_record_count),
            ("adapter_report_count", self.adapter_report_count),
        ):
            if value < 0:
                raise ContractValueError(f"{field_name} must not be negative.")

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
            if finding.severity is TelemetryReadinessFindingSeverity.WARNING
        )

    def is_complete(self) -> bool:
        """Return whether telemetry adapters can count as complete."""

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
        """Evaluate prototype claim readiness with telemetry completion state."""

        completed = tuple(existing_completed_capability_ids) + self.completed_capability_ids()
        return PrototypeReadinessGate().evaluate(
            completed_capability_ids=completed,
            requested_claim_level=requested_claim_level,
        )

    def findings_for_source(
        self,
        telemetry_source_id: str,
    ) -> tuple[TelemetryReadinessFinding, ...]:
        """Return readiness findings for a telemetry source ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.telemetry_source_id == telemetry_source_id
        )

    def findings_for_schema(self, schema_id: str) -> tuple[TelemetryReadinessFinding, ...]:
        """Return readiness findings for a telemetry schema ID."""

        return tuple(finding for finding in self.findings if finding.schema_id == schema_id)

    def findings_for_input(self, input_id: str) -> tuple[TelemetryReadinessFinding, ...]:
        """Return readiness findings for a telemetry normalization input ID."""

        return tuple(finding for finding in self.findings if finding.input_id == input_id)

    def findings_for_envelope(
        self,
        envelope_id: str,
    ) -> tuple[TelemetryReadinessFinding, ...]:
        """Return readiness findings for a telemetry envelope ID."""

        return tuple(finding for finding in self.findings if finding.envelope_id == envelope_id)

    def findings_for_replay_record(
        self,
        replay_record_id: str,
    ) -> tuple[TelemetryReadinessFinding, ...]:
        """Return readiness findings for a telemetry replay record ID."""

        return tuple(
            finding
            for finding in self.findings
            if finding.replay_record_id == replay_record_id
        )

    def summary(self) -> str:
        """Return a deterministic telemetry-readiness summary."""

        return (
            f"telemetry-readiness: {self.decision.value} "
            f"({self.source_count} source(s), {self.schema_count} schema(s), "
            f"{self.replay_record_count} replay record(s), "
            f"{self.adapter_report_count} adapter report(s), "
            f"{self.blocker_count} blocker(s), {self.warning_count} warning(s), "
            f"capability={self.capability_id})"
        )


class TelemetryLayerReadinessEvaluator:
    """Evaluate whether telemetry adapters can count toward prototype maturity."""

    def __init__(self, catalog: TelemetryAdapterCatalog) -> None:
        """Create a telemetry readiness evaluator from an adapter catalog."""

        self._catalog = catalog

    def evaluate(
        self,
        adapter_reports: Iterable[TelemetryAdapterReport],
    ) -> TelemetryLayerReadinessReport:
        """Evaluate telemetry catalog and adapter reports as one completion surface."""

        report_tuple = tuple(adapter_reports)
        findings = (
            self._build_catalog_findings()
            + self._build_report_readiness_findings(report_tuple)
            + self._normalize_adapter_findings(report_tuple)
        )
        return TelemetryLayerReadinessReport(
            decision=self._decide(findings),
            source_count=len(self._catalog.sources),
            schema_count=len(self._catalog.schemas),
            replay_record_count=len(self._catalog.replay_records),
            adapter_report_count=len(report_tuple),
            findings=findings,
        )

    def _build_catalog_findings(self) -> tuple[TelemetryReadinessFinding, ...]:
        """Build readiness findings from catalog structure and replay coverage."""

        findings: list[TelemetryReadinessFinding] = []
        if not self._catalog.sources:
            findings.append(
                TelemetryReadinessFinding(
                    finding_id="telemetry-readiness-no-sources",
                    severity=TelemetryReadinessFindingSeverity.BLOCKER,
                    source=TelemetryReadinessFindingSource.CATALOG,
                    message="Telemetry readiness requires at least one registered source.",
                )
            )
        if not self._catalog.schemas:
            findings.append(
                TelemetryReadinessFinding(
                    finding_id="telemetry-readiness-no-schemas",
                    severity=TelemetryReadinessFindingSeverity.BLOCKER,
                    source=TelemetryReadinessFindingSource.CATALOG,
                    message="Telemetry readiness requires at least one registered schema.",
                )
            )
        if not self._catalog.replay_records:
            findings.append(
                TelemetryReadinessFinding(
                    finding_id="telemetry-readiness-no-replay-records",
                    severity=TelemetryReadinessFindingSeverity.WARNING,
                    source=TelemetryReadinessFindingSource.REPLAY,
                    message=(
                        "Telemetry readiness is stronger when replay records are present for "
                        "deterministic re-evaluation."
                    ),
                )
            )
        return tuple(findings)

    @staticmethod
    def _build_report_readiness_findings(
        adapter_reports: tuple[TelemetryAdapterReport, ...],
    ) -> tuple[TelemetryReadinessFinding, ...]:
        """Build readiness findings from adapter report outcomes."""

        findings: list[TelemetryReadinessFinding] = []
        if not adapter_reports:
            findings.append(
                TelemetryReadinessFinding(
                    finding_id="telemetry-readiness-no-adapter-reports",
                    severity=TelemetryReadinessFindingSeverity.BLOCKER,
                    source=TelemetryReadinessFindingSource.READINESS,
                    message=(
                        "Telemetry readiness requires at least one adapter report proving "
                        "normalization behavior."
                    ),
                )
            )
            return tuple(findings)

        if not any(report.can_support_runtime_evaluation() for report in adapter_reports):
            findings.append(
                TelemetryReadinessFinding(
                    finding_id="telemetry-readiness-no-runtime-usable-envelope",
                    severity=TelemetryReadinessFindingSeverity.BLOCKER,
                    source=TelemetryReadinessFindingSource.ENVELOPE,
                    message=(
                        "Telemetry readiness requires at least one accepted, runtime-usable "
                        "normalized envelope."
                    ),
                )
            )

        for report in adapter_reports:
            if report.decision is TelemetryAdapterDecision.REJECTED:
                findings.append(
                    TelemetryReadinessFinding(
                        finding_id=f"adapter-report-{report.input_id}-rejected",
                        severity=TelemetryReadinessFindingSeverity.BLOCKER,
                        source=TelemetryReadinessFindingSource.ADAPTER_REPORT,
                        message=(
                            "Rejected telemetry adapter reports block telemetry capability "
                            "completion."
                        ),
                        input_id=report.input_id,
                    )
                )
            elif report.decision is TelemetryAdapterDecision.DEGRADED:
                findings.append(
                    TelemetryReadinessFinding(
                        finding_id=f"adapter-report-{report.input_id}-degraded",
                        severity=TelemetryReadinessFindingSeverity.WARNING,
                        source=TelemetryReadinessFindingSource.ADAPTER_REPORT,
                        message=(
                            "Degraded telemetry adapter reports limit telemetry capability "
                            "confidence."
                        ),
                        input_id=report.input_id,
                        envelope_id=(
                            report.envelope.envelope_id
                            if report.envelope is not None
                            else None
                        ),
                    )
                )
            elif report.envelope is None:
                findings.append(
                    TelemetryReadinessFinding(
                        finding_id=f"adapter-report-{report.input_id}-missing-envelope",
                        severity=TelemetryReadinessFindingSeverity.BLOCKER,
                        source=TelemetryReadinessFindingSource.ENVELOPE,
                        message="Accepted telemetry adapter reports must include an envelope.",
                        input_id=report.input_id,
                    )
                )
        return tuple(findings)

    @staticmethod
    def _normalize_adapter_findings(
        adapter_reports: tuple[TelemetryAdapterReport, ...],
    ) -> tuple[TelemetryReadinessFinding, ...]:
        """Normalize adapter findings into telemetry-readiness findings."""

        normalized: list[TelemetryReadinessFinding] = []
        for report in adapter_reports:
            for finding in report.findings:
                normalized.append(
                    TelemetryReadinessFinding(
                        finding_id=f"adapter-{finding.finding_id}",
                        severity=_map_adapter_severity(finding.severity),
                        source=TelemetryReadinessFindingSource.ADAPTER_REPORT,
                        message=finding.message,
                        telemetry_source_id=finding.source_id,
                        schema_id=finding.schema_id,
                        input_id=report.input_id,
                        envelope_id=(
                            report.envelope.envelope_id
                            if report.envelope is not None
                            else None
                        ),
                        replay_record_id=finding.replay_record_id,
                        field_name=finding.field_name,
                        source_finding_id=finding.finding_id,
                    )
                )
        return tuple(normalized)

    @staticmethod
    def _decide(
        findings: tuple[TelemetryReadinessFinding, ...],
    ) -> TelemetryReadinessDecision:
        """Return the combined telemetry readiness decision."""

        if any(finding.severity.blocks_completion() for finding in findings):
            return TelemetryReadinessDecision.BLOCKED
        if any(
            finding.severity is TelemetryReadinessFindingSeverity.WARNING
            for finding in findings
        ):
            return TelemetryReadinessDecision.LIMITED
        return TelemetryReadinessDecision.COMPLETE


def _map_adapter_severity(
    severity: TelemetryAdapterFindingSeverity,
) -> TelemetryReadinessFindingSeverity:
    """Map adapter finding severity to readiness finding severity."""

    if severity is TelemetryAdapterFindingSeverity.BLOCKER:
        return TelemetryReadinessFindingSeverity.BLOCKER
    if severity is TelemetryAdapterFindingSeverity.WARNING:
        return TelemetryReadinessFindingSeverity.WARNING
    return TelemetryReadinessFindingSeverity.INFO


def _require_identifier(value: str, field_name: str) -> None:
    """Validate a stable telemetry-readiness identifier."""

    if not value.strip():
        raise ContractValueError(f"{field_name} must not be blank.")
    if value != value.strip():
        raise ContractValueError(f"{field_name} must not contain edge whitespace.")
    if " " in value:
        raise ContractValueError(f"{field_name} must not contain spaces.")
