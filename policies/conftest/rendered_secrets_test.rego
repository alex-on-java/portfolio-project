package rendered_sources

import rego.v1

valid_discovery := {
	"discovered_overlays": [
		{"path": "gitops/apps/workloads/fixture-alpha/overlays/any/dev"},
		{"path": "gitops/apps/workloads/fixture-alpha/overlays/any/stg"},
		{"path": "gitops/apps/workloads/fixture-alpha/overlays/ephemeral/prd"},
		{"path": "gitops/apps/workloads/fixture-alpha/overlays/main/prd"},
	],
}

fixture_workload_gsm_contracts := {
	"fixture-alpha-gsm": {
		"workload": "fixture-alpha",
		"name": "fixture-alpha-gsm",
		"store_kind": "ClusterSecretStore",
		"store_name": "gcp-secret-manager",
		"required": {
			"any/dev": {"namespace": "dev", "key": "fixture-alpha-gsm-dev"},
			"any/stg": {"namespace": "stg", "key": "fixture-alpha-gsm-stg"},
			"ephemeral/prd": {"namespace": "prd", "key": "fixture-alpha-gsm-stg"},
			"main/prd": {"namespace": "prd", "key": "fixture-alpha-gsm-prd"},
		},
	},
}

valid_rendered_secrets_input := [
	gsm_entry("fixture-alpha", "any", "dev", "dev", "fixture-alpha-gsm-dev"),
	gsm_entry("fixture-alpha", "any", "stg", "stg", "fixture-alpha-gsm-stg"),
	gsm_entry("fixture-alpha", "ephemeral", "prd", "prd", "fixture-alpha-gsm-stg"),
	gsm_entry("fixture-alpha", "main", "prd", "prd", "fixture-alpha-gsm-prd"),
]

test_valid_declared_workload_gsm_renders_pass if {
	count(deny) == 0 with input as valid_rendered_secrets_input with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_sentinel_remote_ref_key_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), fixture_gsm("dev", sentinel_remote_ref_key))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm spec.data[].remoteRef.key must not be REPLACE_IN_OVERLAY"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_production_key_in_ephemeral_reachable_render_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("ephemeral", "prd"), fixture_gsm("prd", "fixture-alpha-gsm-prd"))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-ephemeral-prd.yaml: ExternalSecret/fixture-alpha-gsm ephemeral-reachable overlay must not reference production GSM key fixture-alpha-gsm-prd"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_data_from_find_in_workload_gsm_subject_fails if {
	bad_doc := object.union(fixture_gsm("prd", "fixture-alpha-gsm-stg"), {"spec": object.union(fixture_gsm("prd", "fixture-alpha-gsm-stg").spec, {"data": [], "dataFrom": [{"find": {"name": {"regexp": "fixture-alpha-gsm-.*"}}}]})})
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("ephemeral", "prd"), bad_doc)
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-ephemeral-prd.yaml: ExternalSecret/fixture-alpha-gsm spec.dataFrom[].find is unsupported for workload GSM contracts"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_wrong_expected_key_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), fixture_gsm("dev", "fixture-alpha-gsm-stg"))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm must use GSM key fixture-alpha-gsm-dev for overlay any/dev"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_missing_namespace_fails if {
	bad_doc := json.patch(fixture_gsm("dev", "fixture-alpha-gsm-dev"), [{"op": "remove", "path": "/metadata/namespace"}])
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), bad_doc)
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm must render metadata.namespace"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_unsupported_namespace_env_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), fixture_gsm("qa", "fixture-alpha-gsm-dev"))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm namespace qa is not a supported workload environment"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_namespace_path_env_mismatch_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), fixture_gsm("stg", "fixture-alpha-gsm-dev"))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm namespace stg must match rendered path environment dev"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_copied_staging_content_under_dev_path_fails if {
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), fixture_gsm("stg", "fixture-alpha-gsm-stg"))
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm namespace stg must match rendered path environment dev"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_wrong_target_name_fails if {
	bad_doc := json.patch(fixture_gsm("dev", "fixture-alpha-gsm-dev"), [{"op": "replace", "path": "/spec/target/name", "value": "wrong-secret"}])
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), bad_doc)
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm target.name must be fixture-alpha-gsm"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_missing_required_discovered_overlay_fails if {
	missing_main_discovery := {
		"discovered_overlays": [
			{"path": "gitops/apps/workloads/fixture-alpha/overlays/any/dev"},
			{"path": "gitops/apps/workloads/fixture-alpha/overlays/any/stg"},
			{"path": "gitops/apps/workloads/fixture-alpha/overlays/ephemeral/prd"},
		],
	}
	msg := "overlays/main/prd: workload fixture-alpha required GSM contract fixture-alpha-gsm was not discovered"
	msg in deny with input as valid_rendered_secrets_input with data.render_contract as missing_main_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_missing_required_rendered_external_secret_fails if {
	bad := [entry |
		entry := valid_rendered_secrets_input[_]
		entry.path != fixture_path("main", "prd")
	]
	msg := "overlays/main/prd: workload fixture-alpha required rendered ExternalSecret/fixture-alpha-gsm was not found"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_extract_key_is_explicit_unsupported_shape if {
	base := fixture_gsm("dev", "fixture-alpha-gsm-dev")
	bad_doc := object.union(base, {"spec": object.union(base.spec, {"data": [], "dataFrom": [{"extract": {"key": "fixture-alpha-gsm-dev"}}]})})
	bad := replace_secret_entry(valid_rendered_secrets_input, fixture_path("any", "dev"), bad_doc)
	msg := "kustomize--gitops-apps-workloads-fixture-alpha-overlays-any-dev.yaml: ExternalSecret/fixture-alpha-gsm spec.dataFrom[].extract.key=fixture-alpha-gsm-dev is unsupported; use spec.data[].remoteRef.key for workload GSM contracts"
	msg in deny with input as bad with data.render_contract as valid_discovery with data.rendered_sources.workload_gsm_contracts as fixture_workload_gsm_contracts
}

test_generator_backed_external_secret_passes_untouched if {
	count(deny) == 0 with input as [generator_entry]
}

test_non_overlay_render_passes_untouched if {
	input_doc := {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "ordinary", "namespace": "default"}}
	count(deny) == 0 with input as [{"path": "plain.yaml", "contents": input_doc}]
}

test_uncontracted_workload_gsm_subject_fails if {
	bad := [gsm_entry("fixture-uncontracted", "any", "dev", "dev", "fixture-uncontracted-gsm-dev")]
	msg := "kustomize--gitops-apps-workloads-fixture-uncontracted-overlays-any-dev.yaml: ExternalSecret/fixture-uncontracted-gsm is a workload GSM subject but has no rendered secret contract for workload fixture-uncontracted"
	msg in deny with input as bad
}

test_second_declared_workload_contract_passes if {
	multi_contracts := object.union(fixture_workload_gsm_contracts, {
		"fixture-bravo-gsm": {
			"workload": "fixture-bravo",
			"name": "fixture-bravo-gsm",
			"store_kind": "ClusterSecretStore",
			"store_name": "gcp-secret-manager",
			"required": {"any/dev": {"namespace": "dev", "key": "fixture-bravo-gsm-dev"}},
		},
	})
	multi_discovery := {"discovered_overlays": array.concat(valid_discovery.discovered_overlays, [{"path": "gitops/apps/workloads/fixture-bravo/overlays/any/dev"}])}
	multi_input := array.concat(valid_rendered_secrets_input, [gsm_entry("fixture-bravo", "any", "dev", "dev", "fixture-bravo-gsm-dev")])
	count(deny) == 0 with input as multi_input with data.render_contract as multi_discovery with data.rendered_sources.workload_gsm_contracts as multi_contracts
}

replace_secret_entry(entries, path, replacement) := updated if {
	updated := [entry |
		original := entries[_]
		entry := replace_secret_one(original, path, replacement)
	]
}

replace_secret_one(entry, path, replacement) := {"path": path, "contents": replacement} if {
	entry.path == path
}

replace_secret_one(entry, path, replacement) := entry if {
	entry.path != path
}

gsm_entry(workload, lifecycle, env, namespace, key) := {
	"path": workload_path(workload, lifecycle, env),
	"contents": workload_gsm(workload, namespace, key),
}

fixture_path(lifecycle, env) := workload_path("fixture-alpha", lifecycle, env)

workload_path(workload, lifecycle, env) := sprintf("kustomize--gitops-apps-workloads-%s-overlays-%s-%s.yaml", [workload, lifecycle, env])

fixture_gsm(namespace, key) := workload_gsm("fixture-alpha", namespace, key)

workload_gsm(workload, namespace, key) := {
	"apiVersion": "external-secrets.io/v1",
	"kind": "ExternalSecret",
	"metadata": {"name": sprintf("%s-gsm", [workload]), "namespace": namespace},
	"spec": {
		"secretStoreRef": {"kind": "ClusterSecretStore", "name": "gcp-secret-manager"},
		"target": {"name": sprintf("%s-gsm", [workload]), "creationPolicy": "Owner"},
		"data": [{"secretKey": "demo-gsm", "remoteRef": {"key": key}}],
	},
}

generator_entry := {
	"path": fixture_path("any", "dev"),
	"contents": {
		"apiVersion": "external-secrets.io/v1",
		"kind": "ExternalSecret",
		"metadata": {"name": "fixture-alpha-generated", "namespace": "dev"},
		"spec": {
			"refreshPolicy": "CreatedOnce",
			"target": {"name": "fixture-alpha-generated", "creationPolicy": "Owner"},
			"dataFrom": [{"sourceRef": {"generatorRef": {"kind": "Password", "name": "fixture-alpha-generated"}}}],
		},
	},
}
