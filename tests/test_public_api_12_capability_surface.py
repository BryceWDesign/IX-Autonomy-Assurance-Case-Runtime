from __future__ import annotations

import ix_autonomy_assurance_case_runtime as ix

CAPABILITY_EXPORT_GROUPS = {
    "registry-layer": (
        "REGISTRY_CAPABILITY_ID",
        "RegistryLayerReadinessEvaluator",
        "RegistryLayerReadinessReport",
        "RegistryReadinessDecision",
    ),
    "policy-pack-engine": (
        "POLICY_CAPABILITY_ID",
        "PolicyLayerReadinessEvaluator",
        "PolicyLayerReadinessReport",
        "PolicyLayerReadinessDecision",
    ),
    "framework-crosswalks": (
        "FRAMEWORK_CROSSWALK_CAPABILITY_ID",
        "FrameworkCrosswalkLayerReadinessEvaluator",
        "FrameworkCrosswalkLayerReadinessReport",
        "FrameworkCrosswalkReadinessDecision",
    ),
    "signed-provenance": (
        "PROVENANCE_CAPABILITY_ID",
        "ProvenanceLayerReadinessEvaluator",
        "ProvenanceLayerReadinessReport",
        "ProvenanceReadinessDecision",
    ),
    "telemetry-adapters": (
        "TELEMETRY_CAPABILITY_ID",
        "TelemetryLayerReadinessEvaluator",
        "TelemetryLayerReadinessReport",
        "TelemetryReadinessDecision",
    ),
    "scenario-campaign-runner": (
        "SCENARIO_CAMPAIGN_CAPABILITY_ID",
        "ScenarioCampaignLayerReadinessEvaluator",
        "ScenarioCampaignLayerReadinessReport",
        "ScenarioCampaignReadinessDecision",
    ),
    "monitoring-incidents": (
        "MONITORING_CAPABILITY_ID",
        "MonitoringLayerReadinessEvaluator",
        "MonitoringLayerReadinessReport",
        "MonitoringReadinessDecision",
    ),
    "review-workflow": (
        "REVIEW_WORKFLOW_CAPABILITY_ID",
        "ReviewWorkflowLayerReadinessEvaluator",
        "ReviewWorkflowLayerReadinessReport",
        "ReviewWorkflowReadinessDecision",
    ),
    "audit-report-export": (
        "EXPORT_PACKAGE_CAPABILITY_ID",
        "ExportPackageLayerReadinessEvaluator",
        "ExportPackageLayerReadinessReport",
        "ExportPackageReadinessDecision",
    ),
    "assurance-dossier": (
        "ASSURANCE_DOSSIER_CAPABILITY_ID",
        "AssuranceDossierLayerReadinessEvaluator",
        "AssuranceDossierLayerReadinessReport",
        "AssuranceDossierReadinessDecision",
    ),
    "claim-guardrails": (
        "CLAIM_GUARDRAIL_CAPABILITY_ID",
        "ClaimGuardrailLayerReadinessEvaluator",
        "ClaimGuardrailLayerReadinessReport",
        "ClaimGuardrailReadinessDecision",
    ),
    "federal-evaluation-profile": (
        "FEDERAL_EVALUATION_PROFILE_CAPABILITY_ID",
        "FederalEvaluationLayerReadinessEvaluator",
        "FederalEvaluationLayerReadinessReport",
        "FederalEvaluationReadinessDecision",
    ),
}


def test_public_api_exports_all_twelve_capability_readiness_surfaces() -> None:
    for capability_id, export_names in CAPABILITY_EXPORT_GROUPS.items():
        constant_name = export_names[0]

        assert getattr(ix, constant_name) == capability_id
        for export_name in export_names:
            assert export_name in ix.__all__
            assert hasattr(ix, export_name)


def test_public_api_exports_maturity_and_rollup_entry_points() -> None:
    expected_exports = (
        "BASELINE_MATURITY_PERCENT",
        "SERIOUS_PROTOTYPE_TARGET_PERCENT",
        "PrototypeCapabilityArea",
        "PrototypeCapabilityTarget",
        "PrototypeMaturityAssessment",
        "PrototypeClaimLevel",
        "PrototypeReadinessGate",
        "PrototypeReadinessReport",
        "CapabilityLayerReport",
        "CapabilityLayerRollupEntry",
        "PrototypeCapabilityRollupEvaluator",
        "PrototypeCapabilityRollupReport",
        "build_serious_prototype_targets",
        "assess_serious_prototype_maturity",
    )

    for export_name in expected_exports:
        assert export_name in ix.__all__
        assert hasattr(ix, export_name)


def test_public_api_all_tuple_has_no_duplicates() -> None:
    assert len(ix.__all__) == len(set(ix.__all__))
