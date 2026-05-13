from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.telemetry import (
    TelemetryFieldType,
    TelemetryQualityFlag,
    TelemetryReplayRecord,
    TelemetrySchema,
    TelemetrySchemaField,
    TelemetrySource,
    TelemetrySourceKind,
    TelemetryTimestampAuthority,
    TelemetryTrustLevel,
)
from ix_autonomy_assurance_case_runtime.telemetry_adapter import (
    TelemetryAdapter,
    TelemetryAdapterCatalog,
    TelemetryAdapterDecision,
    TelemetryAdapterFinding,
    TelemetryAdapterFindingSeverity,
    TelemetryAdapterPolicy,
    TelemetryNormalizationInput,
)


def _source(
    *,
    source_id: str = "telemetry-nav-sim",
    kind: TelemetrySourceKind = TelemetrySourceKind.SIMULATOR,
    trust_level: TelemetryTrustLevel = TelemetryTrustLevel.HIGH,
    timestamp_authority: TelemetryTimestampAuthority = TelemetryTimestampAuthority.SOURCE_PROVIDED,
    allowed_schema_ids: tuple[str, ...] = ("schema-nav-telemetry-v1",),
    evidence_bundle_ids: tuple[str, ...] = ("ev-telemetry-source-001",),
) -> TelemetrySource:
    return TelemetrySource(
        source_id=source_id,
        name="Navigation simulator telemetry",
        kind=kind,
        trust_level=trust_level,
        timestamp_authority=timestamp_authority,
        owner="Assurance Lab",
        allowed_schema_ids=allowed_schema_ids,
        evidence_bundle_ids=evidence_bundle_ids,
    )


def _schema(schema_id: str = "schema-nav-telemetry-v1") -> TelemetrySchema:
    return TelemetrySchema(
        schema_id=schema_id,
        name="Navigation telemetry schema",
        version="2026.05",
        fields=(
            TelemetrySchemaField(
                field_name="position_error_ft",
                field_type=TelemetryFieldType.FLOAT,
                unit="ft",
                minimum_value=0.0,
                maximum_value=1000.0,
            ),
            TelemetrySchemaField(
                field_name="authority_state",
                field_type=TelemetryFieldType.ENUM,
                allowed_values=("manual_control", "supervised_autonomy"),
            ),
            TelemetrySchemaField(
                field_name="sensor_valid",
                field_type=TelemetryFieldType.BOOLEAN,
            ),
        ),
    )


def _replay_record() -> TelemetryReplayRecord:
    return TelemetryReplayRecord(
        replay_record_id="replay-nav-001",
        source_id="telemetry-nav-replay",
        schema_id="schema-nav-telemetry-v1",
        replay_file_uri="local://telemetry/replay-nav-001.jsonl",
        recorded_at_utc="2026-05-12T12:05:00Z",
        scenario_ids=("scenario-degraded-nav",),
        envelope_ids=("envelope-telemetry-input-001",),
        evidence_bundle_ids=("ev-telemetry-replay-001",),
    )


def _input(
    *,
    input_id: str = "telemetry-input-001",
    source_id: str = "telemetry-nav-sim",
    schema_id: str = "schema-nav-telemetry-v1",
    captured_at_utc: str = "2026-05-12T12:00:00Z",
    received_at_utc: str = "2026-05-12T12:00:05Z",
    payload: dict[str, object] | None = None,
    replay_record_id: str | None = None,
) -> TelemetryNormalizationInput:
    return TelemetryNormalizationInput(
        input_id=input_id,
        source_id=source_id,
        schema_id=schema_id,
        captured_at_utc=captured_at_utc,
        received_at_utc=received_at_utc,
        payload=payload
        or {
            "position_error_ft": 12.5,
            "authority_state": "supervised_autonomy",
            "sensor_valid": True,
        },
        replay_record_id=replay_record_id,
    )


def _adapter(
    *,
    sources: tuple[TelemetrySource, ...] | None = None,
    schemas: tuple[TelemetrySchema, ...] | None = None,
    replay_records: tuple[TelemetryReplayRecord, ...] = (),
    policy: TelemetryAdapterPolicy | None = None,
) -> TelemetryAdapter:
    return TelemetryAdapter(
        TelemetryAdapterCatalog(
            sources=sources if sources is not None else (_source(),),
            schemas=schemas if schemas is not None else (_schema(),),
            replay_records=replay_records,
        ),
        policy=policy,
    )


def test_telemetry_adapter_accepts_clean_source_schema_payload_and_timestamps() -> None:
    report = _adapter().normalize(_input())

    assert report.decision is TelemetryAdapterDecision.ACCEPTED
    assert report.has_envelope()
    assert report.can_support_runtime_evaluation()
    assert report.blocker_count == 0
    assert report.warning_count == 0
    assert report.envelope is not None
    assert report.envelope.envelope_id == "envelope-telemetry-input-001"
    assert report.envelope.quality_flags == ()
    assert report.summary() == (
        "telemetry-adapter: accepted (envelope, 0 blocker(s), 0 warning(s))"
    )


def test_telemetry_adapter_rejects_missing_source_or_schema() -> None:
    missing_source_report = _adapter(sources=()).normalize(_input())
    missing_schema_report = _adapter(schemas=()).normalize(_input())

    assert missing_source_report.decision is TelemetryAdapterDecision.REJECTED
    assert missing_source_report.blocker_count == 1
    assert not missing_source_report.has_envelope()
    assert missing_source_report.findings[0].finding_id == (
        "input-telemetry-input-001-missing-source"
    )

    assert missing_schema_report.decision is TelemetryAdapterDecision.REJECTED
    assert missing_schema_report.blocker_count == 1
    assert missing_schema_report.findings[0].finding_id == (
        "input-telemetry-input-001-missing-schema"
    )


def test_telemetry_adapter_rejects_source_schema_mismatch() -> None:
    source = _source(allowed_schema_ids=("schema-other-v1",))
    report = _adapter(sources=(source,)).normalize(_input())

    assert report.decision is TelemetryAdapterDecision.REJECTED
    assert report.blocker_count == 1
    assert report.findings[0].quality_flag is TelemetryQualityFlag.SCHEMA_MISMATCH


def test_telemetry_adapter_rejects_missing_required_field() -> None:
    report = _adapter().normalize(
        _input(
            payload={
                "position_error_ft": 12.5,
                "authority_state": "supervised_autonomy",
            }
        )
    )

    assert report.decision is TelemetryAdapterDecision.REJECTED
    assert report.blocker_count == 1
    assert report.findings_for_field("sensor_valid")[0].quality_flag is (
        TelemetryQualityFlag.MISSING_FIELD
    )


def test_telemetry_adapter_rejects_schema_type_enum_and_range_errors() -> None:
    report = _adapter().normalize(
        _input(
            payload={
                "position_error_ft": 5000.0,
                "authority_state": "unknown_authority",
                "sensor_valid": "yes",
            }
        )
    )

    assert report.decision is TelemetryAdapterDecision.REJECTED
    assert report.blocker_count == 3
    assert {
        finding.quality_flag
        for finding in report.findings
    } == {
        TelemetryQualityFlag.OUT_OF_RANGE,
        TelemetryQualityFlag.SCHEMA_MISMATCH,
    }


def test_telemetry_adapter_degrades_stale_but_schema_valid_telemetry() -> None:
    report = _adapter(policy=TelemetryAdapterPolicy(max_latency_seconds=10)).normalize(
        _input(
            captured_at_utc="2026-05-12T12:00:00Z",
            received_at_utc="2026-05-12T12:01:00Z",
        )
    )

    assert report.decision is TelemetryAdapterDecision.DEGRADED
    assert report.has_envelope()
    assert not report.can_support_runtime_evaluation()
    assert report.warning_count == 1
    assert report.envelope is not None
    assert report.envelope.quality_flags == (TelemetryQualityFlag.STALE_TIMESTAMP,)


def test_telemetry_adapter_rejects_future_captured_timestamp() -> None:
    report = _adapter().normalize(
        _input(
            captured_at_utc="2026-05-12T12:00:10Z",
            received_at_utc="2026-05-12T12:00:05Z",
        )
    )

    assert report.decision is TelemetryAdapterDecision.REJECTED
    assert report.blocker_count == 1
    assert report.findings[0].quality_flag is TelemetryQualityFlag.FUTURE_TIMESTAMP


def test_telemetry_adapter_degrades_low_trust_source_without_rejecting_by_default() -> None:
    source = _source(
        trust_level=TelemetryTrustLevel.LOW,
        evidence_bundle_ids=(),
    )

    report = _adapter(sources=(source,)).normalize(_input())

    assert report.decision is TelemetryAdapterDecision.DEGRADED
    assert report.warning_count == 1
    assert report.envelope is not None
    assert report.envelope.quality_flags == (TelemetryQualityFlag.SOURCE_UNTRUSTED,)

    rejected_report = _adapter(
        sources=(source,),
        policy=TelemetryAdapterPolicy(reject_untrusted_sources=True),
    ).normalize(_input())

    assert rejected_report.decision is TelemetryAdapterDecision.REJECTED
    assert rejected_report.blocker_count == 1


def test_telemetry_adapter_accepts_known_replay_record_with_replay_only_flag() -> None:
    replay_source = _source(
        source_id="telemetry-nav-replay",
        kind=TelemetrySourceKind.LOG_REPLAY,
        trust_level=TelemetryTrustLevel.MODERATE,
        timestamp_authority=TelemetryTimestampAuthority.REPLAY_FILE,
        evidence_bundle_ids=(),
    )
    report = _adapter(
        sources=(replay_source,),
        replay_records=(_replay_record(),),
    ).normalize(
        _input(
            source_id="telemetry-nav-replay",
            replay_record_id="replay-nav-001",
        )
    )

    assert report.decision is TelemetryAdapterDecision.ACCEPTED
    assert report.has_envelope()
    assert report.envelope is not None
    assert report.envelope.quality_flags == (TelemetryQualityFlag.REPLAY_ONLY,)
    assert report.envelope.replay_record_id == "replay-nav-001"


def test_telemetry_adapter_rejects_replay_source_without_known_replay_record() -> None:
    replay_source = _source(
        source_id="telemetry-nav-replay",
        kind=TelemetrySourceKind.LOG_REPLAY,
        trust_level=TelemetryTrustLevel.MODERATE,
        timestamp_authority=TelemetryTimestampAuthority.REPLAY_FILE,
        evidence_bundle_ids=(),
    )

    missing_id_report = _adapter(sources=(replay_source,)).normalize(
        _input(source_id="telemetry-nav-replay")
    )
    missing_record_report = _adapter(sources=(replay_source,)).normalize(
        _input(
            source_id="telemetry-nav-replay",
            replay_record_id="replay-nav-001",
        )
    )

    assert missing_id_report.decision is TelemetryAdapterDecision.REJECTED
    assert missing_id_report.blocker_count == 1
    assert missing_record_report.decision is TelemetryAdapterDecision.REJECTED
    assert missing_record_report.blocker_count == 1


def test_telemetry_adapter_catalog_rejects_duplicate_records() -> None:
    source = _source()
    schema = _schema()
    replay_record = _replay_record()

    with pytest.raises(ContractValueError, match="Duplicate telemetry source ID"):
        TelemetryAdapterCatalog(
            sources=(source, source),
            schemas=(schema,),
        )

    with pytest.raises(ContractValueError, match="Duplicate telemetry schema ID"):
        TelemetryAdapterCatalog(
            sources=(source,),
            schemas=(schema, schema),
        )

    with pytest.raises(ContractValueError, match="Duplicate telemetry replay record ID"):
        TelemetryAdapterCatalog(
            sources=(source,),
            schemas=(schema,),
            replay_records=(replay_record, replay_record),
        )


def test_telemetry_adapter_finding_and_policy_validate_inputs() -> None:
    with pytest.raises(ContractValueError, match="max_latency_seconds must be positive"):
        TelemetryAdapterPolicy(max_latency_seconds=0)

    with pytest.raises(ContractValueError, match="needs a message"):
        TelemetryAdapterFinding(
            finding_id="bad-finding",
            severity=TelemetryAdapterFindingSeverity.BLOCKER,
            message="",
        )

    with pytest.raises(ContractValueError, match="blank field name"):
        TelemetryAdapterFinding(
            finding_id="bad-finding",
            severity=TelemetryAdapterFindingSeverity.BLOCKER,
            message="Bad finding.",
            field_name="",
        )
