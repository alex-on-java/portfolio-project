package main

import rego.v1

valid_values(svc) := {
	"apiVersion": "v1",
	"kind": "ConfigMap",
	"metadata": {
		"name": sprintf("cnpg-service-values-%s", [svc]),
		"annotations": {"config.kubernetes.io/local-config": "true"},
	},
	"data": object.union(
		{"serviceName": svc, "provisionSql": expected_sql(svc)},
		expected_values(svc),
	),
}

valid_component(svc) := component if {
	replacements := array.concat([
		{"source": {"kind": "ConfigMap", "name": sprintf("cnpg-service-values-%s", [svc]), "fieldPath": field}, "targets": [{"select": {"kind": "ConfigMap", "name": "placeholder"}, "fieldPaths": ["data.placeholder"]}]}
		| field := expected_component_source_fields[_]
	], [
		{
			"source": {"kind": "ConfigMap", "name": sprintf("cnpg-service-values-%s", [svc]), "fieldPath": "data.provisionSql"},
			"targets": [{
				"select": {"kind": "ConfigMap", "name": "cnpg-verification-provisioning-sql"},
				"fieldPaths": [sprintf("data.[provision-%s.sql]", [svc])],
				"options": {"create": true},
			}],
		},
		{
			"source": {"kind": "ConfigMap", "name": sprintf("cnpg-service-values-%s", [svc]), "fieldPath": "data.provisionSqlKey"},
			"targets": [{
				"select": {"kind": "Job", "name": "cnpg-verification-provision-service"},
				"fieldPaths": ["spec.template.spec.containers.[name=psql].command.2"],
				"options": {"delimiter": "/sql/", "index": 1},
			}],
		},
	])
	component := {
		"apiVersion": "kustomize.config.k8s.io/v1alpha1",
		"kind": "Component",
		"resources": ["values.yaml"],
		"components": ["../_shared"],
		"replacements": replacements,
	}
}

base_file(services) := {
	"path": "gitops/datastores/cnpg-eso-verification/base/kustomization.yaml",
	"contents": {
		"apiVersion": "kustomize.config.k8s.io/v1beta1",
		"kind": "Kustomization",
		"resources": ["password-generator.yaml", "postinit-sql.yaml", "provisioning-sql.yaml", "cluster.yaml", "verification.yaml"],
		"components": [sprintf("../components/service-database/%s", [svc]) | svc := services[_]],
	},
}

values_file(svc) := {
	"path": sprintf("gitops/datastores/cnpg-eso-verification/components/service-database/%s/values.yaml", [svc]),
	"contents": valid_values(svc),
}

component_file(svc) := {
	"path": sprintf("gitops/datastores/cnpg-eso-verification/components/service-database/%s/kustomization.yaml", [svc]),
	"contents": valid_component(svc),
}

valid_inventory := [
	base_file(["lorem", "ipsum"]),
	values_file("lorem"),
	values_file("ipsum"),
	component_file("lorem"),
	component_file("ipsum"),
]

test_valid_service_values_pass if {
	count(deny) == 0 with input as valid_values("lorem")
}

test_missing_required_value_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "remove", "path": "/data/roleAppRwB"}])
	count(deny) > 0 with input as bad
}

test_wrong_role_prefix_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/roleAppRoA", "value": "ipsum_app_ro_a"}])
	count(deny) > 0 with input as bad
}

test_wrong_secret_prefix_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/secretRwA", "value": "cnpg-verification-ipsum-app-rw-a"}])
	count(deny) > 0 with input as bad
}

test_duplicate_role_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/roleAppRoB", "value": "lorem_app_ro_a"}])
	count(deny) > 0 with input as bad
}

test_duplicate_secret_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/secretRwB", "value": "cnpg-verification-lorem-app-rw-a"}])
	count(deny) > 0 with input as bad
}

test_wrong_sql_key_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/provisionSqlKey", "value": "provision-ipsum.sql\n"}])
	count(deny) > 0 with input as bad
}

test_wrong_sql_body_rejected if {
	bad := json.patch(valid_values("lorem"), [{"op": "replace", "path": "/data/provisionSql", "value": "SELECT 1;\n"}])
	count(deny) > 0 with input as bad
}

test_valid_service_component_pass if {
	count(deny) == 0 with input as valid_component("lorem")
}

test_component_wrong_sql_key_field_rejected if {
	base := valid_component("lorem")
	without_sql := [repl | repl := base.replacements[_]; repl.source.fieldPath != "data.provisionSql"]
	wrong_sql := {
		"source": {"kind": "ConfigMap", "name": "cnpg-service-values-lorem", "fieldPath": "data.provisionSql"},
		"targets": [{
			"select": {"kind": "ConfigMap", "name": "cnpg-verification-provisioning-sql"},
			"fieldPaths": ["data.[provision-ipsum.sql]"],
			"options": {"create": true},
		}],
	}
	bad := object.union(base, {"replacements": array.concat(without_sql, [wrong_sql])})
	count(deny) > 0 with input as bad
}

test_component_wildcard_field_path_rejected if {
	bad := json.patch(valid_component("lorem"), [{"op": "replace", "path": "/replacements/0/targets/0/fieldPaths/0", "value": "spec.managed.roles.*.name"}])
	count(deny) > 0 with input as bad
}

test_valid_inventory_passes if {
	count(deny) == 0 with input as valid_inventory
}

test_service_values_file_not_wired_into_base_rejected if {
	count(deny) > 0 with input as array.concat(valid_inventory, [values_file("dolor"), component_file("dolor")])
}

test_base_references_service_with_no_values_file_rejected if {
	bad := [
		base_file(["lorem", "ipsum", "dolor"]),
		values_file("lorem"),
		values_file("ipsum"),
		component_file("lorem"),
		component_file("ipsum"),
		component_file("dolor"),
	]
	count(deny) > 0 with input as bad
}

test_duplicate_service_wiring_rejected if {
	bad := [
		base_file(["lorem", "ipsum", "ipsum"]),
		values_file("lorem"),
		values_file("ipsum"),
		component_file("lorem"),
		component_file("ipsum"),
	]
	count(deny) > 0 with input as bad
}

test_component_file_not_matching_directory_rejected if {
	misplaced := json.patch(component_file("ipsum"), [{"op": "replace", "path": "/path", "value": "gitops/datastores/cnpg-eso-verification/components/service-database/lorem/kustomization.yaml"}])
	bad := [base_file(["lorem", "ipsum"]), values_file("lorem"), values_file("ipsum"), component_file("lorem"), misplaced]
	count(deny) > 0 with input as bad
}

test_values_file_not_matching_directory_rejected if {
	misplaced := json.patch(values_file("ipsum"), [{"op": "replace", "path": "/path", "value": "gitops/datastores/cnpg-eso-verification/components/service-database/lorem/values.yaml"}])
	bad := [base_file(["lorem", "ipsum"]), values_file("lorem"), misplaced, component_file("lorem"), component_file("ipsum")]
	count(deny) > 0 with input as bad
}
