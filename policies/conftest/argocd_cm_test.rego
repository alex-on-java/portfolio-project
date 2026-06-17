package rendered

import rego.v1

argocd_test_main_path := "kustomize--gitops-platform-argocd-bootstrap-overlays-main.yaml"

argocd_test_ephemeral_path := "kustomize--gitops-platform-argocd-bootstrap-overlays-ephemeral.yaml"

argocd_test_discovery := {"discovered_overlays": [
	{"path": "gitops/platform/argocd/bootstrap/overlays/main"},
	{"path": "gitops/platform/argocd/bootstrap/overlays/ephemeral"},
]}

argocd_test_valid_input := [
	{"path": argocd_test_main_path, "contents": argocd_test_valid_cm},
	{"path": argocd_test_ephemeral_path, "contents": argocd_test_valid_cm},
	{"path": argocd_test_ephemeral_path, "contents": {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "fixture-observability"}}},
]

argocd_test_valid_cm := {
	"apiVersion": "v1",
	"kind": "ConfigMap",
	"metadata": {
		"name": "argocd-cm",
		"namespace": "argocd",
		"labels": {"app.kubernetes.io/part-of": "argocd"},
		"annotations": {"argocd.argoproj.io/sync-wave": "-90"},
	},
	"data": {
		"application.instanceLabelKey": "argocd.argoproj.io/instance",
		"resource.exclusions": "- apiGroups: ['fixture.example.invalid']\n",
		"resource.customizations.ignoreResourceUpdates.all": "jsonPointers:\n  - /status\n",
		"resource.customizations.health.postgresql.cnpg.io_Database": "hs = {}\n",
	},
}

test_valid_argocd_cm_bootstrap_outputs_pass if {
	count(argocd_test_deny(argocd_test_valid_input)) == 0
}

test_missing_main_argocd_cm_fails if {
	bad := [entry |
		entry := argocd_test_valid_input[_]
		entry.path != argocd_test_main_path
	]
	"main: bootstrap overlay must render exactly one ConfigMap/argocd-cm" in argocd_test_deny(bad)
}

test_duplicate_ephemeral_argocd_cm_fails if {
	bad := array.concat(argocd_test_valid_input, [{"path": argocd_test_ephemeral_path, "contents": argocd_test_valid_cm}])
	"ephemeral: bootstrap overlay must render exactly one ConfigMap/argocd-cm" in argocd_test_deny(bad)
}

test_main_overlay_extra_object_fails if {
	bad := array.concat(argocd_test_valid_input, [{"path": argocd_test_main_path, "contents": {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "fixture-dev"}}}])
	sprintf("%s: main bootstrap overlay must render only ConfigMap/argocd-cm; found Namespace/fixture-dev", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_required_namespace_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "remove", "path": "/metadata/namespace"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm metadata.namespace must be argocd", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_required_part_of_label_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "replace", "path": "/metadata/labels", "value": {}}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm label app.kubernetes.io/part-of must be argocd", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_required_sync_wave_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "replace", "path": "/metadata/annotations", "value": {}}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm annotation argocd.argoproj.io/sync-wave must be -90", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_required_instance_label_key_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "remove", "path": "/data/application.instanceLabelKey"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm data.application.instanceLabelKey must be argocd.argoproj.io/instance", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_resource_exclusions_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "remove", "path": "/data/resource.exclusions"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm must include data.resource.exclusions", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_ignore_resource_updates_all_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "remove", "path": "/data/resource.customizations.ignoreResourceUpdates.all"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm must include data.resource.customizations.ignoreResourceUpdates.all", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_missing_cnpg_database_health_customization_fails if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "remove", "path": "/data/resource.customizations.health.postgresql.cnpg.io_Database"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm must include data.resource.customizations.health.postgresql.cnpg.io_Database", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_timeout_reconciliation_is_forbidden if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "add", "path": "/data/timeout.reconciliation", "value": "180s"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm must not include data.timeout.reconciliation", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_cnpg_cluster_health_customization_is_forbidden if {
	bad_cm := json.patch(argocd_test_valid_cm, [{"op": "add", "path": "/data/resource.customizations.health.postgresql.cnpg.io_Cluster", "value": "hs = {}\n"}])
	bad := argocd_test_replace_entry(argocd_test_valid_input, argocd_test_main_path, bad_cm)
	sprintf("%s: ConfigMap/argocd-cm must not include data.resource.customizations.health.postgresql.cnpg.io_Cluster", [argocd_test_main_path]) in argocd_test_deny(bad)
}

test_unrelated_rendered_input_is_ignored if {
	unrelated := [{"path": "kustomize--fixture-unrelated.yaml", "contents": {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "fixture", "namespace": "fixture"}, "data": {"key": "value"}}}]
	count(deny) == 0 with input as unrelated
}

argocd_test_deny(test_input) := result if {
	result := deny with input as test_input with data.render_contract as argocd_test_discovery with data.rendered.workload_gsm_contracts as {}
}

argocd_test_replace_entry(entries, path, replacement) := updated if {
	updated := [entry |
		original := entries[_]
		entry := argocd_test_replacement_entry(original, path, replacement)
	]
}

argocd_test_replacement_entry(entry, path, replacement) := {"path": entry.path, "contents": replacement} if {
	entry.path == path
	argocd_is_cm(entry.contents)
}

argocd_test_replacement_entry(entry, path, replacement) := entry if {
	not entry.path == path
}

argocd_test_replacement_entry(entry, path, replacement) := entry if {
	entry.path == path
	not argocd_is_cm(entry.contents)
}
