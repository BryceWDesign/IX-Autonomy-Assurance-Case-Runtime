from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import (
    EvidenceBundle,
    EvidenceRecord,
    EvidenceRuntimeError,
    canonical_json_bytes,
    sha256_canonical_json,
    sha256_hexdigest,
)


def build_record() -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id="EV-001",
        kind="scenario-run",
        source="run-bundles/scenario-001.json",
        payload={
            "runtime_decision": "safe_hold",
            "telemetry": {
                "boundary_distance_ft": 125.0,
                "navigation_confidence": 0.42,
            },
            "criteria": ["AC-001", "AC-002"],
        },
        status=EvidenceStatus.ACCEPTED,
        tags=("navigation", "safe-hold"),
    )


def build_bundle() -> EvidenceBundle:
    return EvidenceBundle(
        bundle_id="BND-001",
        case_id="CASE-001",
        scenario_id="SCN-001",
        records=(build_record(),),
    )


def test_canonical_json_bytes_are_deterministic_for_key_order() -> None:
    left = {"b": 2, "a": {"d": 4, "c": 3}}
    right = {"a": {"c": 3, "d": 4}, "b": 2}

    assert canonical_json_bytes(left) == canonical_json_bytes(right)
    assert canonical_json_bytes(left) == b'{"a":{"c":3,"d":4},"b":2}'


def test_sha256_helpers_return_prefixed_digest() -> None:
    assert sha256_hexdigest(b"abc") == (
        "sha256:ba7816bf8f01cfea414140de5dae2223"
        "b00361a396177a9cb410ff61f20015ad"
    )
    assert sha256_canonical_json({"message": "abc"}).startswith("sha256:")


def test_evidence_record_calculates_stable_content_hash() -> None:
    record = build_record()
    equivalent_record = EvidenceRecord(
        evidence_id="EV-001",
        kind="scenario-run",
        source="run-bundles/scenario-001.json",
        payload={
            "criteria": ["AC-001", "AC-002"],
            "telemetry": {
                "navigation_confidence": 0.42,
                "boundary_distance_ft": 125.0,
            },
            "runtime_decision": "safe_hold",
        },
        status=EvidenceStatus.ACCEPTED,
        tags=("safe-hold", "navigation"),
    )

    assert record.calculate_content_hash() == equivalent_record.calculate_content_hash()


def test_evidence_record_with_computed_hash_validates() -> None:
    record = build_record().with_computed_hash()

    assert record.content_hash is not None
    assert record.has_valid_content_hash() is True
    assert record.to_dict()["content_hash"] == record.content_hash


def test_evidence_record_detects_hash_mismatch() -> None:
    record = EvidenceRecord(
        evidence_id="EV-001",
        kind="scenario-run",
        source="run-bundles/scenario-001.json",
        payload={"runtime_decision": "safe_hold"},
        content_hash="sha256:not-the-real-hash",
    )

    assert record.has_valid_content_hash() is False


def test_evidence_bundle_computes_record_and_bundle_hashes() -> None:
    bundle = build_bundle().with_computed_hashes()

    assert bundle.bundle_hash is not None
    assert bundle.has_valid_bundle_hash() is True
    assert bundle.records[0].content_hash is not None
    assert bundle.records[0].has_valid_content_hash() is True


def test_evidence_bundle_integrity_validation_passes_for_hashed_bundle() -> None:
    bundle = build_bundle().with_computed_hashes()

    report = bundle.validate_integrity()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()


def test_evidence_bundle_integrity_validation_warns_on_missing_hashes() -> None:
    bundle = build_bundle()

    report = bundle.validate_integrity()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == (
        "Evidence record 'EV-001' has no content hash.",
        "Evidence bundle 'BND-001' has no bundle hash.",
    )


def test_evidence_bundle_integrity_validation_fails_on_record_hash_mismatch() -> None:
    bad_record = EvidenceRecord(
        evidence_id="EV-BAD",
        kind="scenario-run",
        source="run-bundles/scenario-bad.json",
        payload={"runtime_decision": "allow"},
        content_hash="sha256:not-the-real-hash",
    )
    bundle = EvidenceBundle(
        bundle_id="BND-BAD",
        case_id="CASE-001",
        records=(bad_record,),
    ).with_computed_hashes()
    tampered_record = EvidenceRecord(
        evidence_id="EV-BAD",
        kind="scenario-run",
        source="run-bundles/scenario-bad.json",
        payload={"runtime_decision": "safe_hold"},
        content_hash=bundle.records[0].content_hash,
    )
    tampered_bundle = EvidenceBundle(
        bundle_id="BND-BAD",
        case_id="CASE-001",
        records=(tampered_record,),
        bundle_hash=bundle.bundle_hash,
    )

    report = tampered_bundle.validate_integrity()

    assert report.is_valid is False
    assert (
        "Evidence record 'EV-BAD' content hash does not match record content."
        in report.errors
    )
    assert "Evidence bundle 'BND-BAD' hash does not match bundle content." in report.errors


def test_evidence_bundle_integrity_validation_fails_on_invalid_status() -> None:
    record = EvidenceRecord(
        evidence_id="EV-INVALID",
        kind="operator-note",
        source="operator-review.json",
        payload={"note": "invalidated during review"},
        status=EvidenceStatus.INVALID,
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-INVALID",
        case_id="CASE-001",
        records=(record,),
    ).with_computed_hashes()

    report = bundle.validate_integrity()

    assert report.is_valid is False
    assert report.errors == ("Evidence record 'EV-INVALID' is marked invalid.",)


def test_evidence_bundle_integrity_validation_warns_on_stale_status() -> None:
    record = EvidenceRecord(
        evidence_id="EV-STALE",
        kind="old-scenario-run",
        source="run-bundles/old.json",
        payload={"runtime_decision": "defer"},
        status=EvidenceStatus.STALE,
    ).with_computed_hash()
    bundle = EvidenceBundle(
        bundle_id="BND-STALE",
        case_id="CASE-001",
        records=(record,),
    ).with_computed_hashes()

    report = bundle.validate_integrity()

    assert report.is_valid is True
    assert report.warnings == (
        "Evidence record 'EV-STALE' has non-usable status 'stale'.",
    )


def test_evidence_bundle_record_index_uses_evidence_id() -> None:
    bundle = build_bundle()

    assert set(bundle.record_index()) == {"EV-001"}


def test_evidence_bundle_to_dict_contains_computed_hash_when_requested() -> None:
    bundle = build_bundle()

    payload = bundle.to_dict(include_computed_hash=True)

    assert payload["bundle_hash"] == bundle.calculate_bundle_hash()
    records = payload["records"]
    assert isinstance(records, list)
    assert records[0]["content_hash"] == build_record().calculate_content_hash()


def test_evidence_bundle_rejects_duplicate_record_identifiers() -> None:
    record = build_record()

    with pytest.raises(EvidenceRuntimeError, match="duplicate evidence_id"):
        EvidenceBundle(
            bundle_id="BND-DUP",
            case_id="CASE-001",
            records=(record, record),
        )


def test_evidence_record_rejects_blank_fields() -> None:
    with pytest.raises(EvidenceRuntimeError, match="evidence_id must not be blank"):
        EvidenceRecord(
            evidence_id=" ",
            kind="scenario-run",
            source="run-bundles/scenario-001.json",
        )


def test_evidence_record_rejects_duplicate_tags() -> None:
    with pytest.raises(EvidenceRuntimeError, match="tags must not contain duplicate"):
        EvidenceRecord(
            evidence_id="EV-001",
            kind="scenario-run",
            source="run-bundles/scenario-001.json",
            tags=("navigation", "navigation"),
        )


def test_evidence_record_rejects_non_finite_float_payload_values() -> None:
    with pytest.raises(EvidenceRuntimeError, match="JSON float values must be finite"):
        EvidenceRecord(
            evidence_id="EV-001",
            kind="scenario-run",
            source="run-bundles/scenario-001.json",
            payload={"value": float("nan")},
        )
