package main

import rego.v1

required_service_value_keys := {
	"serviceName",
	"databaseResourceName",
	"databaseName",
	"databaseOwner",
	"schemaName",
	"schemaOwner",
	"roleApp",
	"roleAppRo",
	"roleAppRw",
	"roleAppMig",
	"roleAppRoA",
	"roleAppRoB",
	"roleAppRwA",
	"roleAppRwB",
	"roleAppMigA",
	"secretRoA",
	"secretRoB",
	"secretRwA",
	"secretRwB",
	"secretMigA",
	"provisionJobName",
	"provisionSqlKey",
	"provisionSql",
}

expected_component_source_fields := {
	"data.databaseName",
	"data.databaseOwner",
	"data.databaseResourceName",
	"data.provisionJobName",
	"data.provisionSql",
	"data.provisionSqlKey",
	"data.roleApp",
	"data.roleAppMig",
	"data.roleAppMigA",
	"data.roleAppRo",
	"data.roleAppRoA",
	"data.roleAppRoB",
	"data.roleAppRw",
	"data.roleAppRwA",
	"data.roleAppRwB",
	"data.schemaName",
	"data.schemaOwner",
	"data.secretMigA",
	"data.secretRoA",
	"data.secretRoB",
	"data.secretRwA",
	"data.secretRwB",
}

deny contains msg if {
	is_service_values(input)
	some key in required_service_value_keys
	value := object.get(input.data, key, "")
	trim(sprintf("%v", [value]), " \t\r\n") == ""
	msg := sprintf("CNPG service values '%s' are missing non-empty data.%s", [input.metadata.name, key])
}

deny contains msg if {
	is_service_values(input)
	svc := object.get(input.data, "serviceName", "")
	not regex.match("^[a-z][a-z0-9]*$", svc)
	msg := sprintf("CNPG service values '%s' have invalid serviceName '%s'", [input.metadata.name, svc])
}

deny contains msg if {
	is_service_values(input)
	svc := input.data.serviceName
	input.metadata.name != sprintf("cnpg-service-values-%s", [svc])
	msg := sprintf("CNPG service values metadata.name '%s' must be cnpg-service-values-%s", [input.metadata.name, svc])
}

deny contains msg if {
	is_service_values(input)
	annotations := object.get(input.metadata, "annotations", {})
	object.get(annotations, "config.kubernetes.io/local-config", "") != "true"
	msg := sprintf("CNPG service values '%s' must be marked config.kubernetes.io/local-config=true", [input.metadata.name])
}

deny contains msg if {
	is_service_values(input)
	svc := input.data.serviceName
	expected := expected_values(svc)
	some key, value in expected
	actual := object.get(input.data, key, "")
	actual != value
	msg := sprintf("CNPG service values '%s' data.%s must be '%s', got '%s'", [input.metadata.name, key, value, actual])
}

deny contains msg if {
	is_service_values(input)
	svc := input.data.serviceName
	input.data.provisionSql != expected_sql(svc)
	msg := sprintf("CNPG service values '%s' data.provisionSql does not match the expected SQL body for service '%s'", [input.metadata.name, svc])
}

deny contains msg if {
	is_service_values(input)
	roles := [
		input.data.roleApp,
		input.data.roleAppRo,
		input.data.roleAppRw,
		input.data.roleAppMig,
		input.data.roleAppRoA,
		input.data.roleAppRoB,
		input.data.roleAppRwA,
		input.data.roleAppRwB,
		input.data.roleAppMigA,
	]
	count(roles) != count({role | role := roles[_]})
	msg := sprintf("CNPG service values '%s' must define nine distinct role names", [input.metadata.name])
}

deny contains msg if {
	is_service_values(input)
	secrets := [
		input.data.secretRoA,
		input.data.secretRoB,
		input.data.secretRwA,
		input.data.secretRwB,
		input.data.secretMigA,
	]
	count(secrets) != count({secret | secret := secrets[_]})
	msg := sprintf("CNPG service values '%s' must define five distinct secret names", [input.metadata.name])
}

deny contains msg if {
	is_service_component(input)
	input.resources != ["values.yaml"]
	msg := "CNPG service component resources must be exactly [values.yaml]"
}

deny contains msg if {
	is_service_component(input)
	input.components != ["../_shared"]
	msg := "CNPG service component components must be exactly [../_shared]"
}

deny contains msg if {
	is_service_component(input)
	count(component_services(input)) != 1
	msg := "CNPG service component must reference exactly one cnpg-service-values-* source"
}

deny contains msg if {
	is_service_component(input)
	missing := expected_component_source_fields - component_source_fields(input)
	count(missing) > 0
	msg := sprintf("CNPG service component is missing replacement sources %v", [sort(missing)])
}

deny contains msg if {
	is_service_component(input)
	count(component_services(input)) == 1
	svc := component_services(input)[_]
	not component_has_sql_data_field(input, svc)
	msg := sprintf("CNPG service component for '%s' must write ConfigMap data.[provision-%s.sql]", [svc, svc])
}

deny contains msg if {
	is_service_component(input)
	count(component_services(input)) == 1
	svc := component_services(input)[_]
	not component_has_sql_key_command_replacement(input)
	msg := sprintf("CNPG service component for '%s' must copy data.provisionSqlKey into the provisioning job command", [svc])
}

deny contains msg if {
	is_service_component(input)
	repl := input.replacements[_]
	target := repl.targets[_]
	field_path := target.fieldPaths[_]
	contains(field_path, "*")
	msg := sprintf("CNPG service component must not use wildcard replacement fieldPath '%s'", [field_path])
}

deny contains msg if {
	is_shared_component(input)
	input.resources != ["external-secrets.yaml", "database.yaml", "provisioning-job.yaml"]
	msg := "CNPG shared service component resources must stay canonical"
}

deny contains msg if {
	is_shared_component(input)
	not shared_component_has_role_patch(input)
	msg := "CNPG shared service component must include the managed-roles JSON6902 patch"
}

deny contains msg if {
	is_combined_cnpg_inventory
	not base_kustomization_present
	msg := "CNPG service database inventory must include base/kustomization.yaml"
}

deny contains msg if {
	is_combined_cnpg_inventory
	base_kustomization_present
	not "provisioning-sql.yaml" in base_doc.resources
	msg := "CNPG service database base must include provisioning-sql.yaml as the shared SQL ConfigMap"
}

deny contains msg if {
	is_combined_cnpg_inventory
	base_kustomization_present
	component := base_doc.components[_]
	component == "../components/service-database/generated"
	msg := "CNPG service database base must not reference the generated component"
}

deny contains msg if {
	is_combined_cnpg_inventory
	base_kustomization_present
	components := base_service_components
	count(components) != count({svc | svc := components[_]})
	msg := sprintf("CNPG service database base has duplicate service component wiring: %v", [components])
}

deny contains msg if {
	is_combined_cnpg_inventory
	service_value_count > 0
	values := value_file_services
	count(values) != count({svc | svc := values[_]})
	msg := sprintf("CNPG service database values contain duplicate service names: %v", [values])
}

deny contains msg if {
	is_combined_cnpg_inventory
	svc := value_file_services[_]
	not svc in base_service_component_set
	msg := sprintf("CNPG service values for '%s' exist but base does not wire ../components/service-database/%s", [svc, svc])
}

deny contains msg if {
	is_combined_cnpg_inventory
	svc := base_service_components[_]
	not svc in value_file_service_set
	msg := sprintf("CNPG service database base wires '%s' but no values.yaml was provided for that service", [svc])
}

deny contains msg if {
	is_combined_cnpg_inventory
	svc := base_service_components[_]
	not svc in service_component_file_set
	msg := sprintf("CNPG service database base wires '%s' but no service kustomization.yaml was provided", [svc])
}

deny contains msg if {
	is_combined_cnpg_inventory
	entry := service_value_entries[_]
	path_svc := service_from_values_path(entry.path)
	path_svc != entry.contents.data.serviceName
	msg := sprintf("%s lives under service '%s' but declares serviceName '%s'", [entry.path, path_svc, entry.contents.data.serviceName])
}

deny contains msg if {
	is_combined_cnpg_inventory
	entry := service_component_entries[_]
	path_svc := service_from_component_path(entry.path)
	component_services(entry.contents) != {path_svc}
	msg := sprintf("%s must source only cnpg-service-values-%s", [entry.path, path_svc])
}

is_service_values(doc) if {
	is_object(doc)
	object.get(doc, "apiVersion", "") == "v1"
	object.get(doc, "kind", "") == "ConfigMap"
	startswith(object.get(object.get(doc, "metadata", {}), "name", ""), "cnpg-service-values-")
}

is_service_component(doc) if {
	is_object(doc)
	object.get(doc, "apiVersion", "") == "kustomize.config.k8s.io/v1alpha1"
	object.get(doc, "kind", "") == "Component"
	"values.yaml" in object.get(doc, "resources", [])
}

is_shared_component(doc) if {
	is_object(doc)
	object.get(doc, "apiVersion", "") == "kustomize.config.k8s.io/v1alpha1"
	object.get(doc, "kind", "") == "Component"
	"external-secrets.yaml" in object.get(doc, "resources", [])
}

shared_component_has_role_patch(doc) if {
	patch := doc.patches[_]
	patch.path == "managed-roles-patch.yaml"
	patch.target.group == "postgresql.cnpg.io"
	patch.target.version == "v1"
	patch.target.kind == "Cluster"
	patch.target.name == "cnpg-eso-multidb-verification"
}

component_services(doc) := services if {
	services := {svc |
		repl := doc.replacements[_]
		name := repl.source.name
		startswith(name, "cnpg-service-values-")
		svc := replace(name, "cnpg-service-values-", "")
	}
}

component_source_fields(doc) := fields if {
	fields := {field |
		repl := doc.replacements[_]
		field := repl.source.fieldPath
	}
}

component_has_sql_data_field(doc, svc) if {
	repl := doc.replacements[_]
	repl.source.fieldPath == "data.provisionSql"
	target := repl.targets[_]
	target.select.kind == "ConfigMap"
	target.select.name == "cnpg-verification-provisioning-sql"
	field_path := target.fieldPaths[_]
	field_path == sprintf("data.[provision-%s.sql]", [svc])
	target.options.create == true
}

component_has_sql_key_command_replacement(doc) if {
	repl := doc.replacements[_]
	repl.source.fieldPath == "data.provisionSqlKey"
	target := repl.targets[_]
	target.select.kind == "Job"
	target.select.name == "cnpg-verification-provision-service"
	field_path := target.fieldPaths[_]
	field_path == "spec.template.spec.containers.[name=psql].command.2"
	target.options.delimiter == "/sql/"
	target.options.index == 1
}

is_combined_cnpg_inventory if {
	is_array(input)
	some entry in input
	startswith(entry.path, "gitops/datastores/cnpg-eso-verification/")
}

base_kustomization_present if {
	some entry in input
	entry.path == "gitops/datastores/cnpg-eso-verification/base/kustomization.yaml"
}

base_doc := doc if {
	some entry in input
	entry.path == "gitops/datastores/cnpg-eso-verification/base/kustomization.yaml"
	doc := entry.contents
}

base_service_components := services if {
	base_kustomization_present
	services := [svc |
		component := base_doc.components[_]
		matches := regex.find_all_string_submatch_n(`^\.\./components/service-database/([a-z][a-z0-9]*)$`, component, 1)
		count(matches) > 0
		svc := matches[0][1]
	]
}

base_service_component_set contains svc if {
	svc := base_service_components[_]
}

service_value_entries contains entry if {
	is_combined_cnpg_inventory
	some entry in input
	is_service_values(entry.contents)
	regex.match(`^gitops/datastores/cnpg-eso-verification/components/service-database/[a-z][a-z0-9]*/values\.yaml$`, entry.path)
}

service_component_entries contains entry if {
	is_combined_cnpg_inventory
	some entry in input
	is_service_component(entry.contents)
	regex.match(`^gitops/datastores/cnpg-eso-verification/components/service-database/[a-z][a-z0-9]*/kustomization\.yaml$`, entry.path)
}

service_value_count := count(service_value_entries)

value_file_services := services if {
	services := [entry.contents.data.serviceName | entry := service_value_entries[_]]
}

value_file_service_set contains svc if {
	svc := value_file_services[_]
}

service_component_file_set contains svc if {
	entry := service_component_entries[_]
	svc := service_from_component_path(entry.path)
}

service_from_values_path(path) := svc if {
	matches := regex.find_all_string_submatch_n(`^gitops/datastores/cnpg-eso-verification/components/service-database/([a-z][a-z0-9]*)/values\.yaml$`, path, 1)
	svc := matches[0][1]
}

service_from_component_path(path) := svc if {
	matches := regex.find_all_string_submatch_n(`^gitops/datastores/cnpg-eso-verification/components/service-database/([a-z][a-z0-9]*)/kustomization\.yaml$`, path, 1)
	svc := matches[0][1]
}

expected_values(svc) := values if {
	values := {
		"databaseResourceName": sprintf("cnpg-eso-%s", [svc]),
		"databaseName": svc,
		"databaseOwner": sprintf("%s_app", [svc]),
		"schemaName": svc,
		"schemaOwner": sprintf("%s_app", [svc]),
		"roleApp": sprintf("%s_app", [svc]),
		"roleAppRo": sprintf("%s_app_ro", [svc]),
		"roleAppRw": sprintf("%s_app_rw", [svc]),
		"roleAppMig": sprintf("%s_app_mig", [svc]),
		"roleAppRoA": sprintf("%s_app_ro_a", [svc]),
		"roleAppRoB": sprintf("%s_app_ro_b", [svc]),
		"roleAppRwA": sprintf("%s_app_rw_a", [svc]),
		"roleAppRwB": sprintf("%s_app_rw_b", [svc]),
		"roleAppMigA": sprintf("%s_app_mig_a", [svc]),
		"secretRoA": sprintf("cnpg-verification-%s-app-ro-a", [svc]),
		"secretRoB": sprintf("cnpg-verification-%s-app-ro-b", [svc]),
		"secretRwA": sprintf("cnpg-verification-%s-app-rw-a", [svc]),
		"secretRwB": sprintf("cnpg-verification-%s-app-rw-b", [svc]),
		"secretMigA": sprintf("cnpg-verification-%s-app-mig-a", [svc]),
		"provisionJobName": sprintf("cnpg-verification-provision-%s", [svc]),
		"provisionSqlKey": sprintf("provision-%s.sql\n", [svc]),
	}
}

expected_sql(svc) := sql if {
	app := sprintf("%s_app", [svc])
	ro := sprintf("%s_app_ro", [svc])
	rw := sprintf("%s_app_rw", [svc])
	mig := sprintf("%s_app_mig", [svc])
	sql := concat("", [
		sprintf("REVOKE ALL ON DATABASE %s FROM PUBLIC;\n", [svc]),
		sprintf("GRANT CONNECT ON DATABASE %s TO %s, %s, %s, %s;\n", [svc, app, ro, rw, mig]),
		"DROP SCHEMA IF EXISTS public;\n",
		"\n",
		sprintf("GRANT USAGE ON SCHEMA %s TO %s;\n", [svc, ro]),
		sprintf("GRANT USAGE ON SCHEMA %s TO %s;\n", [svc, rw]),
		"\n",
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [app, svc]),
		sprintf("  GRANT SELECT ON TABLES TO %s;\n", [ro]),
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [app, svc]),
		sprintf("  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %s;\n", [rw]),
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [app, svc]),
		sprintf("  GRANT USAGE, SELECT ON SEQUENCES TO %s;\n", [rw]),
	])
}
