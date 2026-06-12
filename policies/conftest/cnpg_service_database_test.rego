package rendered

import rego.v1

valid_rendered_input := [{"path": "rendered-cnpg.yaml", "contents": doc} | doc := valid_rendered_docs[_]]

valid_rendered_docs := [
	valid_database("lorem"),
	valid_sql_config_map("lorem"),
	valid_alias("lorem"),
	valid_job("lorem"),
	valid_external_secret("lorem", "ro-a", service_role("lorem", "ro_a")),
	valid_external_secret("lorem", "ro-b", service_role("lorem", "ro_b")),
	valid_external_secret("lorem", "rw-a", service_role("lorem", "rw_a")),
	valid_external_secret("lorem", "rw-b", service_role("lorem", "rw_b")),
	valid_external_secret("lorem", "mig-a", service_role("lorem", "mig_a")),
	valid_cluster("lorem"),
]

test_valid_rendered_cnpg_bundle_passes if {
	count(deny) == 0 with input as valid_rendered_input
}

test_wrong_database_contract_fails if {
	bad_db := json.patch(valid_database("lorem"), [{"op": "replace", "path": "/spec/databaseReclaimPolicy", "value": "retain"}])
	bad := replace_doc(valid_rendered_input, "Database", "cnpg-eso-lorem", bad_db)
	count(deny) > 0 with input as bad
}

test_missing_matching_external_secret_fails if {
	bad := [entry |
		entry := valid_rendered_input[_]
		not object.get(entry.contents, "kind", "") == "ExternalSecret"
	]
	count(deny) > 0 with input as bad
}

test_external_secret_password_template_mismatch_fails if {
	bad_secret := json.patch(valid_external_secret("lorem", "ro-a", service_role("lorem", "ro_a")), [{"op": "remove", "path": "/spec/target/template/data/password"}])
	bad := replace_doc(valid_rendered_input, "ExternalSecret", "cnpg-verification-lorem-app-ro-a", bad_secret)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_psql_container_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/name", "value": "not-psql"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_database_env_fails if {
	bad_job := job_without_env("lorem", "PGDATABASE")
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_provisioning_job_database_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/env/0/value", "value": "ipsum"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_user_env_fails if {
	bad_job := job_without_env("lorem", "PGUSER")
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_provisioning_job_user_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/env/1/value", "value": "ipsum_app_mig_a"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_password_env_fails if {
	bad_job := job_without_env("lorem", "PGPASSWORD")
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_provisioning_job_secret_name_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/name", "value": "cnpg-verification-ipsum-app-mig-a"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_provisioning_job_secret_key_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/env/2/valueFrom/secretKeyRef/key", "value": "username"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_options_env_fails if {
	bad_job := job_without_env("lorem", "PGOPTIONS")
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_provisioning_job_host_env_fails if {
	bad_job := job_without_env("lorem", "PGHOST")
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_provisioning_job_sql_key_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/command/2", "value": "psql --no-psqlrc --set=ON_ERROR_STOP=1 --file=/sql/provision-ipsum.sql"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_missing_sql_config_map_fails if {
	bad := [entry |
		entry := valid_rendered_input[_]
		metadata_name(entry.contents) != "cnpg-verification-provisioning-sql"
	]
	count(deny) > 0 with input as bad
}

test_sql_config_map_key_body_mismatch_fails if {
	bad_config_map := json.patch(valid_sql_config_map("lorem"), [{"op": "replace", "path": "/data/provision-lorem.sql", "value": "SELECT 1;\n"}])
	bad := replace_doc(valid_rendered_input, "ConfigMap", "cnpg-verification-provisioning-sql", bad_config_map)
	count(deny) > 0 with input as bad
}

test_managed_role_graph_mismatch_fails if {
	bad_cluster := json.patch(valid_cluster("lorem"), [{"op": "replace", "path": "/spec/managed/roles/4/inRoles/0", "value": "lorem_app_rw"}])
	bad := replace_doc(valid_rendered_input, "Cluster", "cnpg-eso-lorem", bad_cluster)
	count(deny) > 0 with input as bad
}

test_unresolved_placeholder_fragment_fails if {
	bad_job := json.patch(valid_job("lorem"), [{"op": "replace", "path": "/spec/template/spec/containers/0/env/3/value", "value": "cnpg-verification-service-placeholder"}])
	bad := replace_doc(valid_rendered_input, "Job", "cnpg-verification-provision-lorem", bad_job)
	count(deny) > 0 with input as bad
}

test_wrong_alias_target_fails if {
	bad_alias := json.patch(valid_alias("lorem"), [{"op": "replace", "path": "/spec/externalName", "value": "wrong-rw.datastores-dev.svc.cluster.local"}])
	bad := replace_doc(valid_rendered_input, "Service", "lorem-db-rw", bad_alias)
	count(deny) > 0 with input as bad
}

test_missing_alias_service_fails if {
	bad := [entry |
		entry := valid_rendered_input[_]
		metadata_name(entry.contents) != "lorem-db-rw"
	]
	count(deny) > 0 with input as bad
}

test_unrelated_rendered_manifest_bundle_is_ignored if {
	unrelated := [{"path": "unrelated.yaml", "contents": {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "ordinary", "namespace": "default"}, "data": {"key": "value"}}}]
	count(deny) == 0 with input as unrelated
}

replace_doc(entries, kind, name, replacement) := updated if {
	updated := [entry |
		original := entries[_]
		entry := replace_entry(original, kind, name, replacement)
	]
}

replace_entry(entry, kind, name, replacement) := {"path": entry.path, "contents": replacement} if {
	object.get(entry.contents, "kind", "") == kind
	metadata_name(entry.contents) == name
}

replace_entry(entry, kind, name, replacement) := entry if {
	not object.get(entry.contents, "kind", "") == kind
}

replace_entry(entry, kind, name, replacement) := entry if {
	object.get(entry.contents, "kind", "") == kind
	metadata_name(entry.contents) != name
}

job_without_env(svc, env_name) := job if {
	base := valid_job(svc)
	env := [entry |
		entry := base.spec.template.spec.containers[0].env[_]
		object.get(entry, "name", "") != env_name
	]
	container := object.union(base.spec.template.spec.containers[0], {"env": env})
	spec := object.union(base.spec.template.spec, {"containers": [container]})
	template := object.union(base.spec.template, {"spec": spec})
	job_spec := object.union(base.spec, {"template": template})
	job := object.union(base, {"spec": job_spec})
}

valid_database(svc) := {
	"apiVersion": "postgresql.cnpg.io/v1",
	"kind": "Database",
	"metadata": {"name": sprintf("cnpg-eso-%s", [svc]), "namespace": "datastores-dev"},
	"spec": {
		"cluster": {"name": sprintf("cnpg-eso-%s", [svc])},
		"name": svc,
		"owner": service_owner(svc),
		"ensure": "present",
		"databaseReclaimPolicy": "delete",
		"schemas": [{"name": svc, "owner": service_owner(svc), "ensure": "present"}],
	},
}

valid_sql_config_map(svc) := {
	"apiVersion": "v1",
	"kind": "ConfigMap",
	"metadata": {"name": "cnpg-verification-provisioning-sql", "namespace": "datastores-dev"},
	"data": {provision_sql_key(svc): expected_sql(svc)},
}

valid_alias(svc) := {
	"apiVersion": "v1",
	"kind": "Service",
	"metadata": {"name": service_alias_name(svc), "namespace": "datastores-dev"},
	"spec": {
		"type": "ExternalName",
		"externalName": sprintf("cnpg-eso-%s-rw.datastores-dev.svc.cluster.local", [svc]),
	},
}

valid_job(svc) := {
	"apiVersion": "batch/v1",
	"kind": "Job",
	"metadata": {"name": provisioning_job_name(svc), "namespace": "datastores-dev"},
	"spec": {
		"template": {
			"spec": {
				"containers": [{
					"name": "psql",
					"env": [
						{"name": "PGDATABASE", "value": svc},
						{"name": "PGUSER", "value": service_role(svc, "mig_a")},
						{"name": "PGPASSWORD", "valueFrom": {"secretKeyRef": {"name": service_secret(svc, "mig-a"), "key": "password"}}},
						{"name": "PGOPTIONS", "value": sprintf("-c role=%s", [service_owner(svc)])},
						{"name": "PGHOST", "value": service_alias_name(svc)},
					],
					"command": ["/bin/sh", "-ceu", sprintf("psql --no-psqlrc --set=ON_ERROR_STOP=1 --file=/sql/%s", [provision_sql_key(svc)])],
				}],
			},
		},
	},
}

valid_external_secret(svc, suffix, username) := {
	"apiVersion": "external-secrets.io/v1",
	"kind": "ExternalSecret",
	"metadata": {"name": service_secret(svc, suffix), "namespace": "datastores-dev"},
	"spec": {
		"refreshInterval": "0s",
		"refreshPolicy": "CreatedOnce",
		"target": {
			"name": service_secret(svc, suffix),
			"creationPolicy": "Owner",
			"template": {
				"type": "kubernetes.io/basic-auth",
				"metadata": {"labels": {"cnpg.io/reload": "true"}},
				"data": {"username": username, "password": "{{ .password }}"},
			},
		},
	},
}

valid_cluster(svc) := {
	"apiVersion": "postgresql.cnpg.io/v1",
	"kind": "Cluster",
	"metadata": {"name": sprintf("cnpg-eso-%s", [svc]), "namespace": "datastores-dev"},
	"spec": {
		"managed": {
			"roles": [
				{"name": service_owner(svc), "ensure": "present", "login": false, "inherit": false},
				{"name": service_role(svc, "ro"), "ensure": "present", "login": false, "inherit": false},
				{"name": service_role(svc, "rw"), "ensure": "present", "login": false, "inherit": false},
				{"name": service_role(svc, "mig"), "ensure": "present", "login": false, "inherit": false, "inRoles": [service_owner(svc)]},
				{"name": service_role(svc, "ro_a"), "ensure": "present", "login": true, "inherit": true, "connectionLimit": -1, "inRoles": [service_role(svc, "ro")], "passwordSecret": {"name": service_secret(svc, "ro-a")}},
				{"name": service_role(svc, "ro_b"), "ensure": "present", "login": true, "inherit": true, "connectionLimit": -1, "inRoles": [service_role(svc, "ro")], "passwordSecret": {"name": service_secret(svc, "ro-b")}},
				{"name": service_role(svc, "rw_a"), "ensure": "present", "login": true, "inherit": true, "connectionLimit": -1, "inRoles": [service_role(svc, "rw")], "passwordSecret": {"name": service_secret(svc, "rw-a")}},
				{"name": service_role(svc, "rw_b"), "ensure": "present", "login": true, "inherit": true, "connectionLimit": -1, "inRoles": [service_role(svc, "rw")], "passwordSecret": {"name": service_secret(svc, "rw-b")}},
				{"name": service_role(svc, "mig_a"), "ensure": "present", "login": true, "inherit": true, "connectionLimit": -1, "inRoles": [service_role(svc, "mig")], "passwordSecret": {"name": service_secret(svc, "mig-a")}},
			],
		},
	},
}
