from __future__ import annotations

from ix_autonomy_assurance_case_runtime.assurance_dossier_readiness import (
    AssuranceDossierLayerReadinessReport,
    AssuranceDossierReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.assurance_dossier_validation import (
    AssuranceDossierValidationReport,
)
from ix_autonomy_assurance_case_runtime.claim_guardrails_readiness import (
    ClaimGuardrailLayerReadinessReport,
    ClaimGuardrailReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.claim_guardrails_validation import (
    ClaimGuardrailValidationReport,
)
from ix_autonomy_assurance_case_runtime.export_package_readiness import (
    ExportPackageLayerReadinessReport,
    ExportPackageReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.export_package_validation import (
    ExportPackageValidationReport,
)
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile_readiness import (
    FederalEvaluationLayerReadinessReport,
    FederalEvaluationReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.federal_evaluation_profile_validation import (
    FederalEvaluationValidationReport,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk import FrameworkCoverageReport
from ix_autonomy_assurance_case_runtime.framework_crosswalk_evidence import (
    FrameworkEvidenceCoverageReport,
)
from ix_autonomy_assurance_case_runtime.framework_crosswalk_readiness import (
    FrameworkCrosswalkLayerReadinessReport,
    FrameworkCrosswalkReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.monitoring_readiness import (
    MonitoringLayerReadinessReport,
    MonitoringReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.monitoring_validation import MonitoringValidationReport
from ix_autonomy_assurance_case_runtime.policy_readiness import (
    PolicyLayerReadinessDecision,
    PolicyLayerReadinessReport,
)
from ix_autonomy_assurance_case_runtime.policy_waiver_evidence import (
    PolicyWaiverEvidenceCoverageReport,
)
from ix_autonomy_assurance_case_runtime.prototype_readiness import (
    PrototypeClaimLevel,
    PrototypeReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.prototype_rollup import (
    CapabilityLayerReport,
    PrototypeCapabilityRollupEvaluator,
)
from ix_autonomy_assurance_case_runtime.prototype_target import (
    required_serious_prototype_capability_ids,
    serious_prototype_capability_ids,
)
from ix_autonomy_assurance_case_runtime.provenance_readiness import (
    ProvenanceLayerReadinessReport,
    ProvenanceReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.provenance_verifier import (
    ProvenanceManifestDecision,
    ProvenanceManifestVerificationReport,
)
from ix_autonomy_assurance_case_runtime.registry_catalog import RegistryValidationReport
from ix_autonomy_assurance_case_runtime.registry_evidence import RegistryEvidenceCoverageReport
from ix_autonomy_assurance_case_runtime.registry_readiness import (
    RegistryLayerReadinessReport,
    RegistryReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.review_workflow_readiness import (
    ReviewWorkflowLayerReadinessReport,
    ReviewWorkflowReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.review_workflow_validation import (
    ReviewWorkflowValidationReport,
)
from ix_autonomy_assurance_case_runtime.scenario_campaign_readiness import (
    ScenarioCampaignLayerReadinessReport,
    ScenarioCampaignReadinessDecision,
)
from ix_autonomy_assurance_case_runtime.telemetry_readiness import (
    TelemetryLayerReadinessReport,
    TelemetryReadinessDecision,
)


def _complete_layer_reports() -> tuple[CapabilityLayerReport, ...]:
    return (
        RegistryLayerReadinessReport(
            decision=RegistryReadinessDecision.COMPLETE,
            catalog_report=RegistryValidationReport(
                model_count=1,
                system_count=1,
                use_case_count=1,
                deployment_count=1,
                findings=(),
            ),
            evidence_report=RegistryEvidenceCoverageReport(
                referenced_bundle_count=3,
                provided_bundle_count=3,
                findings=(),
            ),
            findings=(),
        ),
        PolicyLayerReadinessReport(
            decision=PolicyLayerReadinessDecision.COMPLETE,
            evaluation_reports=(),
            waiver_evidence_report=PolicyWaiverEvidenceCoverageReport(
                policy_pack_id="pack-fed-001",
                waiver_count=1,
                referenced_bundle_count=1,
                provided_bundle_count=1,
                findings=(),
            ),
            findings=(),
        ),
        FrameworkCrosswalkLayerReadinessReport(
            decision=FrameworkCrosswalkReadinessDecision.COMPLETE,
            coverage_report=FrameworkCoverageReport(coverage=(), findings=()),
            evidence_report=FrameworkEvidenceCoverageReport(
                referenced_bundle_count=1,
                provided_bundle_count=1,
                findings=(),
            ),
            findings=(),
        ),
        ProvenanceLayerReadinessReport(
            decision=ProvenanceReadinessDecision.COMPLETE,
            verification_report=ProvenanceManifestVerificationReport(
                manifest_id="manifest-provenance-001",
                decision=ProvenanceManifestDecision.VERIFIED,
                artifact_count=1,
                signed_artifact_count=1,
                attestation_count=1,
                findings=(),
            ),
            findings=(),
        ),
        TelemetryLayerReadinessReport(
            decision=TelemetryReadinessDecision.COMPLETE,
            source_count=1,
            schema_count=1,
            replay_record_count=1,
            adapter_report_count=1,
            findings=(),
        ),
        ScenarioCampaignLayerReadinessReport(
            decision=ScenarioCampaignReadinessDecision.COMPLETE,
            campaign_count=1,
            run_report_count=1,
            findings=(),
        ),
        MonitoringLayerReadinessReport(
            decision=MonitoringReadinessDecision.COMPLETE,
            validation_report=MonitoringValidationReport(
                snapshot_count=1,
                drift_count=1,
                incident_count=1,
                trigger_count=1,
                findings=(),
            ),
            findings=(),
        ),
        ReviewWorkflowLayerReadinessReport(
            decision=ReviewWorkflowReadinessDecision.COMPLETE,
            validation_report=ReviewWorkflowValidationReport(
                workflow_id="workflow-review-001",
                finding_count=1,
                signoff_count=1,
                dissent_count=0,
                evidence_bundle_count=1,
                findings=(),
            ),
            findings=(),
        ),
        ExportPackageLayerReadinessReport(
            decision=ExportPackageReadinessDecision.COMPLETE,
            validation_report=ExportPackageValidationReport(
                package_id="export-package-001",
                artifact_count=5,
                redaction_rule_count=1,
                evidence_bundle_count=3,
                provenance_manifest_count=1,
                findings=(),
            ),
            findings=(),
        ),
        AssuranceDossierLayerReadinessReport(
            decision=AssuranceDossierReadinessDecision.COMPLETE,
            validation_report=AssuranceDossierValidationReport(
                dossier_id="dossier-runtime-001",
                trace_thread_count=1,
                artifact_count=5,
                evidence_reference_count=4,
                evidence_bundle_count=4,
                provenance_manifest_count=1,
                export_package_count=1,
                findings=(),
            ),
            findings=(),
        ),
        ClaimGuardrailLayerReadinessReport(
            decision=ClaimGuardrailReadinessDecision.COMPLETE,
            validation_report=ClaimGuardrailValidationReport(
                package_id="claim-package-runtime-001",
                claim_count=2,
                evidence_reference_count=1,
                prohibited_rule_count=1,
                evidence_bundle_count=1,
                findings=(),
            ),
            findings=(),
        ),
        FederalEvaluationLayerReadinessReport(
            decision=FederalEvaluationReadinessDecision.COMPLETE,
            validation_report=FederalEvaluationValidationReport(
                profile_id="fed-profile-runtime-001",
                mapping_count=12,
                concern_count=8,
                core_concern_count=8,
                completed_capability_count=12,
                artifact_count=8,
                evidence_bundle_count=8,
                findings=(),
            ),
            findings=(),
        ),
    )


def test_all_twelve_capability_readiness_surfaces_roll_up_to_full_local_maturity() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(
        _complete_layer_reports(),
        requested_claim_level=PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
    )

    assert report.is_rollup_clean()
    assert report.readiness_report.decision is PrototypeReadinessDecision.ALLOW
    assert report.achieved_percent == 100
    assert report.completed_capability_ids() == serious_prototype_capability_ids()
    assert report.missing_expected_capability_ids == ()
    assert report.unexpected_completed_capability_ids == ()
    assert report.duplicate_capability_ids == ()
    assert report.findings == ()
    assert report.summary() == (
        "prototype-rollup: 100% (12 completed capability(s), 0 blocker(s), "
        "0 warning(s), target=80%)"
    )


def test_original_nine_required_readiness_surfaces_still_reach_eighty_percent() -> None:
    report = PrototypeCapabilityRollupEvaluator().evaluate(
        _complete_layer_reports()[:9],
        requested_claim_level=PrototypeClaimLevel.SERIOUS_OPEN_SOURCE_PROTOTYPE,
        expected_capability_ids=required_serious_prototype_capability_ids(),
    )

    assert report.is_rollup_clean()
    assert report.readiness_report.decision is PrototypeReadinessDecision.ALLOW
    assert report.achieved_percent == 80
    assert report.completed_capability_ids() == required_serious_prototype_capability_ids()
    assert report.missing_expected_capability_ids == ()
    assert report.unexpected_completed_capability_ids == ()
    assert report.duplicate_capability_ids == ()
    assert report.findings == ()
