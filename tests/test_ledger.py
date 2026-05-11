from __future__ import annotations

import pytest

from ix_autonomy_assurance_case_runtime.contracts import EvidenceStatus
from ix_autonomy_assurance_case_runtime.evidence import EvidenceBundle, EvidenceRecord
from ix_autonomy_assurance_case_runtime.ledger import (
    LedgerEntry,
    LedgerRecordType,
    LedgerRuntimeError,
    RunLedger,
)


def build_evidence_bundle(
    *,
    bundle_id: str = "BND-RUN-001",
    evidence_id: str = "EV-RUN-001",
    case_id: str = "CASE-001",
    scenario_id: str = "SCN-001",
) -> EvidenceBundle:
    record = EvidenceRecord(
        evidence_id=evidence_id,
        kind="scenario-run",
        source=f"scenario:{scenario_id}",
        payload={
            "case_id": case_id,
            "final_decision": "safe_hold",
            "scenario_id": scenario_id,
            "verification_result": "pass",
        },
        status=EvidenceStatus.ACCEPTED,
        created_by="ix-scenario-runner",
        tags=("scenario-run", scenario_id),
    ).with_computed_hash()

    return EvidenceBundle(
        bundle_id=bundle_id,
        case_id=case_id,
        scenario_id=scenario_id,
        records=(record,),
        created_by="ix-scenario-runner",
    ).with_computed_hashes()


def test_empty_ledger_is_valid_with_warning() -> None:
    ledger = RunLedger(ledger_id="LEDGER-001")

    report = ledger.validate_chain()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ("Run ledger 'LEDGER-001' has no entries.",)


def test_append_evidence_bundle_creates_valid_first_entry() -> None:
    bundle = build_evidence_bundle()
    ledger = RunLedger(ledger_id="LEDGER-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=bundle,
        run_id="RUN-001",
    )

    report = ledger.validate_chain()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()

    entry = ledger.entries[0]
    assert entry.sequence_number == 1
    assert entry.previous_entry_hash is None
    assert entry.entry_hash is not None
    assert entry.has_valid_entry_hash() is True
    assert entry.record_type is LedgerRecordType.EVIDENCE_BUNDLE
    assert entry.artifact_id == "BND-RUN-001"
    assert entry.run_id == "RUN-001"
    assert entry.scenario_id == "SCN-001"


def test_append_multiple_bundles_creates_valid_hash_chain() -> None:
    first_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-001",
        evidence_id="EV-RUN-001",
    )
    second_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-002",
        evidence_id="EV-RUN-002",
    )

    ledger = (
        RunLedger(ledger_id="LEDGER-001")
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-001",
            bundle=first_bundle,
            run_id="RUN-001",
        )
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-002",
            bundle=second_bundle,
            run_id="RUN-002",
        )
    )

    report = ledger.validate_chain()

    assert report.is_valid is True
    assert report.errors == ()
    assert report.warnings == ()
    assert ledger.entries[1].sequence_number == 2
    assert ledger.entries[1].previous_entry_hash == ledger.entries[0].entry_hash
    assert ledger.latest_entry_hash() == ledger.entries[1].entry_hash


def test_ledger_detects_tampered_entry_payload() -> None:
    bundle = build_evidence_bundle()
    ledger = RunLedger(ledger_id="LEDGER-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=bundle,
        run_id="RUN-001",
    )
    original_entry = ledger.entries[0]
    tampered_entry = LedgerEntry(
        entry_id=original_entry.entry_id,
        sequence_number=original_entry.sequence_number,
        record_type=original_entry.record_type,
        case_id=original_entry.case_id,
        artifact_id=original_entry.artifact_id,
        artifact_hash=original_entry.artifact_hash,
        payload={
            "bundle_id": "BND-RUN-001",
            "case_id": "CASE-001",
            "record_count": 999,
            "record_ids": ["EV-RUN-001"],
            "scenario_id": "SCN-001",
        },
        run_id=original_entry.run_id,
        scenario_id=original_entry.scenario_id,
        previous_entry_hash=original_entry.previous_entry_hash,
        created_by=original_entry.created_by,
        tags=original_entry.tags,
        entry_hash=original_entry.entry_hash,
    )
    tampered_ledger = RunLedger(
        ledger_id=ledger.ledger_id,
        entries=(tampered_entry,),
        created_by=ledger.created_by,
    )

    report = tampered_ledger.validate_chain()

    assert report.is_valid is False
    assert report.errors == ("Ledger entry 'LEDGER-ENTRY-001' hash does not match entry content.",)


def test_ledger_detects_broken_previous_hash_link() -> None:
    first_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-001",
        evidence_id="EV-RUN-001",
    )
    second_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-002",
        evidence_id="EV-RUN-002",
    )
    ledger = (
        RunLedger(ledger_id="LEDGER-001")
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-001",
            bundle=first_bundle,
            run_id="RUN-001",
        )
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-002",
            bundle=second_bundle,
            run_id="RUN-002",
        )
    )
    second_entry = ledger.entries[1]
    broken_second_entry = LedgerEntry(
        entry_id=second_entry.entry_id,
        sequence_number=second_entry.sequence_number,
        record_type=second_entry.record_type,
        case_id=second_entry.case_id,
        artifact_id=second_entry.artifact_id,
        artifact_hash=second_entry.artifact_hash,
        payload=second_entry.payload,
        run_id=second_entry.run_id,
        scenario_id=second_entry.scenario_id,
        previous_entry_hash="sha256:0000000000000000000000000000000000000000000000000000000000000000",
        created_by=second_entry.created_by,
        tags=second_entry.tags,
    ).with_computed_hash()
    broken_ledger = RunLedger(
        ledger_id=ledger.ledger_id,
        entries=(ledger.entries[0], broken_second_entry),
        created_by=ledger.created_by,
    )

    report = broken_ledger.validate_chain()

    assert report.is_valid is False
    assert (
        "Ledger entry 'LEDGER-ENTRY-002' previous hash does not match entry 'LEDGER-ENTRY-001'."
    ) in report.errors


def test_ledger_detects_sequence_number_gap() -> None:
    bundle = build_evidence_bundle()
    artifact_hash = bundle.bundle_hash or bundle.calculate_bundle_hash()
    entry = LedgerEntry(
        entry_id="LEDGER-ENTRY-003",
        sequence_number=3,
        record_type=LedgerRecordType.EVIDENCE_BUNDLE,
        case_id="CASE-001",
        artifact_id="BND-RUN-001",
        artifact_hash=artifact_hash,
    ).with_computed_hash()
    ledger = RunLedger(
        ledger_id="LEDGER-001",
        entries=(entry,),
    )

    report = ledger.validate_chain()

    assert report.is_valid is False
    assert "Ledger entry 'LEDGER-ENTRY-003' has sequence_number 3, expected 1." in report.errors


def test_ledger_detects_duplicate_entry_ids() -> None:
    bundle = build_evidence_bundle()
    ledger = RunLedger(ledger_id="LEDGER-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=bundle,
        run_id="RUN-001",
    )
    duplicate_ledger = RunLedger(
        ledger_id=ledger.ledger_id,
        entries=(ledger.entries[0], ledger.entries[0]),
        created_by=ledger.created_by,
    )

    report = duplicate_ledger.validate_chain()

    assert report.is_valid is False
    assert "Ledger entry identifier 'LEDGER-ENTRY-001' is duplicated." in report.errors


def test_ledger_detects_duplicate_run_ids_when_required() -> None:
    first_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-001",
        evidence_id="EV-RUN-001",
    )
    second_bundle = build_evidence_bundle(
        bundle_id="BND-RUN-002",
        evidence_id="EV-RUN-002",
    )
    ledger = (
        RunLedger(ledger_id="LEDGER-001")
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-001",
            bundle=first_bundle,
            run_id="RUN-DUP",
        )
        .append_evidence_bundle(
            entry_id="LEDGER-ENTRY-002",
            bundle=second_bundle,
            run_id="RUN-DUP",
        )
    )

    normal_report = ledger.validate_chain()
    strict_report = ledger.validate_chain(require_unique_run_ids=True)

    assert normal_report.is_valid is True
    assert strict_report.is_valid is False
    assert "Ledger run identifier 'RUN-DUP' is duplicated." in strict_report.errors


def test_ledger_warns_when_entry_hash_is_missing() -> None:
    bundle = build_evidence_bundle()
    entry = LedgerEntry(
        entry_id="LEDGER-ENTRY-001",
        sequence_number=1,
        record_type=LedgerRecordType.EVIDENCE_BUNDLE,
        case_id="CASE-001",
        artifact_id="BND-RUN-001",
        artifact_hash=bundle.bundle_hash or bundle.calculate_bundle_hash(),
    )
    ledger = RunLedger(
        ledger_id="LEDGER-001",
        entries=(entry,),
    )

    report = ledger.validate_chain()

    assert report.is_valid is True
    assert report.warnings == ("Ledger entry 'LEDGER-ENTRY-001' has no entry hash.",)


def test_first_ledger_entry_must_not_have_previous_hash() -> None:
    bundle = build_evidence_bundle()
    entry = LedgerEntry(
        entry_id="LEDGER-ENTRY-001",
        sequence_number=1,
        record_type=LedgerRecordType.EVIDENCE_BUNDLE,
        case_id="CASE-001",
        artifact_id="BND-RUN-001",
        artifact_hash=bundle.bundle_hash or bundle.calculate_bundle_hash(),
        previous_entry_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
    ).with_computed_hash()
    ledger = RunLedger(
        ledger_id="LEDGER-001",
        entries=(entry,),
    )

    report = ledger.validate_chain()

    assert report.is_valid is False
    assert "First ledger entry 'LEDGER-ENTRY-001' must not have a previous hash." in report.errors


def test_ledger_to_dict_is_machine_readable() -> None:
    bundle = build_evidence_bundle()
    ledger = RunLedger(ledger_id="LEDGER-001").append_evidence_bundle(
        entry_id="LEDGER-ENTRY-001",
        bundle=bundle,
        run_id="RUN-001",
    )

    payload = ledger.to_dict()

    assert payload["ledger_id"] == "LEDGER-001"
    assert payload["created_by"] == "ix-run-ledger"

    entries = payload["entries"]
    assert isinstance(entries, list)
    entry_payload = entries[0]
    assert isinstance(entry_payload, dict)
    artifact_hash = entry_payload["artifact_hash"]
    assert isinstance(artifact_hash, str)
    assert entry_payload["entry_id"] == "LEDGER-ENTRY-001"
    assert entry_payload["entry_hash"] == ledger.entries[0].entry_hash
    assert artifact_hash.startswith("sha256:")


def test_ledger_entry_rejects_unprefixed_hashes() -> None:
    with pytest.raises(LedgerRuntimeError, match="artifact_hash must use the 'sha256:' prefix"):
        LedgerEntry(
            entry_id="LEDGER-ENTRY-BAD",
            sequence_number=1,
            record_type=LedgerRecordType.EVIDENCE_BUNDLE,
            case_id="CASE-001",
            artifact_id="BND-BAD",
            artifact_hash="not-a-prefixed-hash",
        )


def test_ledger_entry_rejects_invalid_sequence_number() -> None:
    with pytest.raises(LedgerRuntimeError, match="sequence_number must be greater"):
        LedgerEntry(
            entry_id="LEDGER-ENTRY-BAD",
            sequence_number=0,
            record_type=LedgerRecordType.EVIDENCE_BUNDLE,
            case_id="CASE-001",
            artifact_id="BND-BAD",
            artifact_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        )


def test_ledger_entry_rejects_duplicate_tags() -> None:
    with pytest.raises(LedgerRuntimeError, match="tags must not contain duplicate"):
        LedgerEntry(
            entry_id="LEDGER-ENTRY-BAD",
            sequence_number=1,
            record_type=LedgerRecordType.MANUAL_NOTE,
            case_id="CASE-001",
            artifact_id="NOTE-001",
            artifact_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
            tags=("review", "review"),
        )


def test_ledger_rejects_blank_identity_fields() -> None:
    with pytest.raises(LedgerRuntimeError, match="ledger_id must not be blank"):
        RunLedger(ledger_id=" ")

    with pytest.raises(LedgerRuntimeError, match="entry_id must not be blank"):
        LedgerEntry(
            entry_id=" ",
            sequence_number=1,
            record_type=LedgerRecordType.MANUAL_NOTE,
            case_id="CASE-001",
            artifact_id="NOTE-001",
            artifact_hash="sha256:1111111111111111111111111111111111111111111111111111111111111111",
        )
