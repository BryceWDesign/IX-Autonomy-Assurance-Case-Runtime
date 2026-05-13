from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import ContractValueError
from ix_autonomy_assurance_case_runtime.telemetry import (
    TelemetryEnvelope,
    TelemetryFieldType,
    TelemetryFreshnessStatus,
    TelemetryQualityFlag,
    TelemetryReplayRecord,
    TelemetrySchema,
    TelemetrySchemaField,
    TelemetrySource,
    TelemetrySourceKind,
    TelemetryTimestampAuthority,
    TelemetryTrustLevel,
)


def _source(
    *,
    source_id: str = "telemetry-nav-sim",
    kind: TelemetrySourceKind = TelemetrySourceKind.SIMULATOR,
    trust_level: TelemetryTrustLevel = TelemetryTrustLevel.HIGH,
    timestamp_authority: TelemetryTimestampAuthority = TelemetryTimestampAuthority.SOURCE_PROVIDED,
    evidence_bundle_ids: tuple[str, ...] = ("ev-telemetry-source-001",),
) -> TelemetrySource:
    return TelemetrySource(
        source_id=source_id,
        name="Navigation simulator telemetry",
        kind=kind,
        trust_level=trust_level,
        timestamp_authority=timestamp_authority,
        owner="Assurance Lab",
        allowed_schema_ids=("schema-nav-telemetry-v1",),
        evidence_bundle_ids=evidence_bundle_ids,
    )


def _schema() -> TelemetrySchema:
    return TelemetrySchema(
        schema_id="schema-nav-telemetry-v1",
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


def _envelope(
    *,
    freshness_status: TelemetryFreshnessStatus = TelemetryFreshnessStatus.CURRENT,
    quality_flags: tuple[TelemetryQualityFlag, ...] = (),
    replay_record_id: str | None = None,
) -> TelemetryEnvelope:
    return TelemetryEnvelope(
        envelope_id="telemetry-envelope-001",
        source_id="telemetry-nav-sim",
        schema_id="schema-nav-telemetry-v1",
        captured_at_utc="2026-05-12T12:00:00Z",
        received_at_utc="2026-05-12T12:00:05Z",
        payload={
            "position_error_ft": 12.5,
            "authority_state": "supervised_autonomy",
            "sensor_valid": True,
        },
        freshness_status=freshness_status,
        quality_flags=quality_flags,
        replay_record_id=replay_record_id,
    )


def test_telemetry_source_tracks_trust_schema_and_timestamp_authority() -> None:
    source = _source()

    assert source.supports_schema("schema-nav-telemetry-v1")
    assert source.can_support_acceptance()
    assert source.kind.is_machine_generated()
    assert source.timestamp_authority.supports_strong_ordering()

    with pytest.raises(ContractValueError, match="trust level requires evidence bundles"):
        _source(evidence_bundle_ids=())


def test_replay_telemetry_source_requires_replay_file_timestamp_authority() -> None:
    with pytest.raises(ContractValueError, match="must use replay-file timestamp authority"):
        _source(
            kind=TelemetrySourceKind.LOG_REPLAY,
            timestamp_authority=TelemetryTimestampAuthority.LOCAL_CLOCK,
            trust_level=TelemetryTrustLevel.MODERATE,
            evidence_bundle_ids=(),
        )

    replay_source = _source(
        kind=TelemetrySourceKind.LOG_REPLAY,
        timestamp_authority=TelemetryTimestampAuthority.REPLAY_FILE,
        trust_level=TelemetryTrustLevel.MODERATE,
        evidence_bundle_ids=(),
    )

    assert replay_source.kind.is_replay_source()


def test_telemetry_schema_preserves_required_fields_and_lookup() -> None:
    schema = _schema()

    assert schema.required_field_names() == (
        "position_error_ft",
        "authority_state",
        "sensor_valid",
    )
    assert schema.field_by_name("authority_state") == TelemetrySchemaField(
        field_name="authority_state",
        field_type=TelemetryFieldType.ENUM,
        allowed_values=("manual_control", "supervised_autonomy"),
    )
    assert schema.field_by_name("missing") is None


def test_telemetry_schema_field_rejects_invalid_enum_and_numeric_boundaries() -> None:
    with pytest.raises(ContractValueError, match="requires allowed values"):
        TelemetrySchemaField(
            field_name="authority_state",
            field_type=TelemetryFieldType.ENUM,
        )

    with pytest.raises(ContractValueError, match="must not define allowed values"):
        TelemetrySchemaField(
            field_name="sensor_valid",
            field_type=TelemetryFieldType.BOOLEAN,
            allowed_values=("true", "false"),
        )

    with pytest.raises(ContractValueError, match="maximum_value must be >= minimum_value"):
        TelemetrySchemaField(
            field_name="position_error_ft",
            field_type=TelemetryFieldType.FLOAT,
            minimum_value=10.0,
            maximum_value=1.0,
        )


def test_telemetry_schema_rejects_duplicate_fields() -> None:
    field = TelemetrySchemaField(
        field_name="sensor_valid",
        field_type=TelemetryFieldType.BOOLEAN,
    )

    with pytest.raises(ContractValueError, match="duplicate fields"):
        TelemetrySchema(
            schema_id="schema-nav-telemetry-v1",
            name="Navigation telemetry schema",
            version="2026.05",
            fields=(field, field),
        )


def test_telemetry_envelope_supports_runtime_evaluation_when_current_and_clean() -> None:
    envelope = _envelope()

    assert envelope.captured_at.year == 2026
    assert envelope.received_at.year == 2026
    assert not envelope.has_blocking_quality_flags()
    assert envelope.can_support_runtime_evaluation()


def test_telemetry_envelope_blocks_stale_future_or_out_of_order_posture() -> None:
    with pytest.raises(ContractValueError, match="must not be after received_at_utc"):
        TelemetryEnvelope(
            envelope_id="telemetry-envelope-001",
            source_id="telemetry-nav-sim",
            schema_id="schema-nav-telemetry-v1",
            captured_at_utc="2026-05-12T12:00:10Z",
            received_at_utc="2026-05-12T12:00:05Z",
            payload={"sensor_valid": True},
            freshness_status=TelemetryFreshnessStatus.CURRENT,
        )

    with pytest.raises(ContractValueError, match="cannot be current and stale"):
        _envelope(quality_flags=(TelemetryQualityFlag.STALE_TIMESTAMP,))

    with pytest.raises(ContractValueError, match="stale status requires stale flag"):
        _envelope(freshness_status=TelemetryFreshnessStatus.STALE)


def test_telemetry_envelope_identifies_blocking_quality_flags() -> None:
    stale_envelope = _envelope(
        freshness_status=TelemetryFreshnessStatus.STALE,
        quality_flags=(TelemetryQualityFlag.STALE_TIMESTAMP,),
    )

    assert stale_envelope.has_blocking_quality_flags()
    assert not stale_envelope.can_support_runtime_evaluation()

    replay_envelope = _envelope(
        quality_flags=(TelemetryQualityFlag.REPLAY_ONLY,),
        replay_record_id="replay-nav-001",
    )

    assert not replay_envelope.has_blocking_quality_flags()
    assert replay_envelope.can_support_runtime_evaluation()


def test_telemetry_replay_record_preserves_scenarios_envelopes_and_evidence() -> None:
    replay = TelemetryReplayRecord(
        replay_record_id="replay-nav-001",
        source_id="telemetry-nav-sim",
        schema_id="schema-nav-telemetry-v1",
        replay_file_uri="local://telemetry/replay-nav-001.jsonl",
        recorded_at_utc="2026-05-12T12:05:00Z",
        scenario_ids=("scenario-degraded-nav",),
        envelope_ids=("telemetry-envelope-001",),
        evidence_bundle_ids=("ev-telemetry-replay-001",),
    )

    assert replay.recorded_at.year == 2026
    assert replay.scenario_ids == ("scenario-degraded-nav",)

    with pytest.raises(ContractValueError, match="scenario_ids must not contain duplicate values"):
        TelemetryReplayRecord(
            replay_record_id="replay-nav-001",
            source_id="telemetry-nav-sim",
            schema_id="schema-nav-telemetry-v1",
            replay_file_uri="local://telemetry/replay-nav-001.jsonl",
            recorded_at_utc="2026-05-12T12:05:00Z",
            scenario_ids=("scenario-degraded-nav", "scenario-degraded-nav"),
        )
