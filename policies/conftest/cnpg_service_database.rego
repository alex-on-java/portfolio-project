package rendered

import rego.v1

placeholder_fragments := {
	"ROLE0_",
	"ROLE1_",
	"ROLE2_",
	"ROLE3_",
	"ROLE4_",
	"ROLE5_",
	"ROLE6_",
	"ROLE7_",
	"ROLE8_",
	"SERVICE_SECRET_",
	"cnpg-eso-service",
	"cnpg-verification-service-",
	"cnpg-verification-provision-service",
	"provision-service.sql",
	"service_app",
}

required_job_env_names := {
	"PGDATABASE",
	"PGUSER",
	"PGPASSWORD",
	"PGOPTIONS",
	"PGHOST",
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	metadata_name(db) != sprintf("cnpg-eso-%s", [svc])
	msg := sprintf("%s: Database for service '%s' must be named cnpg-eso-%s", [path, svc, svc])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	spec := object.get(db, "spec", {})
	object.get(spec, "owner", "") != service_owner(svc)
	msg := sprintf("%s: Database/%s owner must be %s", [path, metadata_name(db), service_owner(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	spec := object.get(db, "spec", {})
	object.get(spec, "ensure", "") != "present"
	msg := sprintf("%s: Database/%s ensure must be present", [path, metadata_name(db)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	spec := object.get(db, "spec", {})
	object.get(spec, "databaseReclaimPolicy", "") != "delete"
	msg := sprintf("%s: Database/%s databaseReclaimPolicy must render as delete", [path, metadata_name(db)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	spec := object.get(db, "spec", {})
	object.get(spec, "schemas", []) != [{"name": svc, "owner": service_owner(svc), "ensure": "present"}]
	msg := sprintf("%s: Database/%s schemas must contain only the service-owned schema '%s'", [path, metadata_name(db), svc])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	cluster_name(db) == ""
	msg := sprintf("%s: Database/%s must render a non-empty spec.cluster.name", [path, metadata_name(db)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	not cluster_for_database(path, db)
	msg := sprintf("%s: Database/%s references missing Cluster/%s", [path, metadata_name(db), cluster_name(db)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	not external_secret(path, secret_name, metadata_namespace(db))
	msg := sprintf("%s: service '%s' is missing ExternalSecret/%s", [path, svc, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	spec := object.get(es, "spec", {})
	object.get(spec, "refreshPolicy", "") != "CreatedOnce"
	msg := sprintf("%s: ExternalSecret/%s refreshPolicy must be CreatedOnce", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	spec := object.get(es, "spec", {})
	object.get(spec, "refreshInterval", "") != "0s"
	msg := sprintf("%s: ExternalSecret/%s refreshInterval must be 0s", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	target := object.get(object.get(es, "spec", {}), "target", {})
	object.get(target, "name", "") != secret_name
	msg := sprintf("%s: ExternalSecret/%s target.name must match the rendered Secret name", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	target := object.get(object.get(es, "spec", {}), "target", {})
	object.get(target, "creationPolicy", "") != "Owner"
	msg := sprintf("%s: ExternalSecret/%s target.creationPolicy must be Owner", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	template := object.get(object.get(object.get(es, "spec", {}), "target", {}), "template", {})
	object.get(template, "type", "") != "kubernetes.io/basic-auth"
	msg := sprintf("%s: ExternalSecret/%s target.template.type must be kubernetes.io/basic-auth", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	template := object.get(object.get(object.get(es, "spec", {}), "target", {}), "template", {})
	labels := object.get(object.get(template, "metadata", {}), "labels", {})
	object.get(labels, "cnpg.io/reload", "") != "true"
	msg := sprintf("%s: ExternalSecret/%s target.template.metadata.labels.cnpg.io/reload must be true", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	template := object.get(object.get(object.get(es, "spec", {}), "target", {}), "template", {})
	template_data := object.get(template, "data", {})
	object.get(template_data, "username", "") != username
	msg := sprintf("%s: ExternalSecret/%s username must be %s", [path, secret_name, username])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some secret_name, username in expected_secret_usernames(svc)
	es := external_secret(path, secret_name, metadata_namespace(db))
	template := object.get(object.get(object.get(es, "spec", {}), "target", {}), "template", {})
	template_data := object.get(template, "data", {})
	object.get(template_data, "password", "") != "{{ .password }}"
	msg := sprintf("%s: ExternalSecret/%s password template must render the generated password", [path, secret_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	not provisioning_job(path, svc, metadata_namespace(db))
	msg := sprintf("%s: service '%s' is missing provisioning Job/%s", [path, svc, provisioning_job_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	not psql_container(job)
	msg := sprintf("%s: Job/%s must contain a psql container", [path, provisioning_job_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_name := required_job_env_names[_]
	not env_present(container, env_name)
	msg := sprintf("%s: Job/%s is missing env.%s", [path, provisioning_job_name(svc), env_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_value(container, "PGDATABASE") != svc
	msg := sprintf("%s: Job/%s PGDATABASE must be %s", [path, provisioning_job_name(svc), svc])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_value(container, "PGUSER") != service_role(svc, "mig_a")
	msg := sprintf("%s: Job/%s PGUSER must be %s", [path, provisioning_job_name(svc), service_role(svc, "mig_a")])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_secret_name(container, "PGPASSWORD") != service_secret(svc, "mig-a")
	msg := sprintf("%s: Job/%s PGPASSWORD must come from Secret/%s", [path, provisioning_job_name(svc), service_secret(svc, "mig-a")])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_secret_key(container, "PGPASSWORD") != "password"
	msg := sprintf("%s: Job/%s PGPASSWORD must read the password Secret key", [path, provisioning_job_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_value(container, "PGOPTIONS") != sprintf("-c role=%s", [service_owner(svc)])
	msg := sprintf("%s: Job/%s PGOPTIONS must set role %s", [path, provisioning_job_name(svc), service_owner(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	env_value(container, "PGHOST") != service_alias_name(svc)
	msg := sprintf("%s: Job/%s PGHOST must use Service/%s", [path, provisioning_job_name(svc), service_alias_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	job := provisioning_job(path, svc, metadata_namespace(db))
	container := psql_container(job)
	not command_contains(container, sprintf("--file=/sql/%s", [provision_sql_key(svc)]))
	msg := sprintf("%s: Job/%s command must read /sql/%s", [path, provisioning_job_name(svc), provision_sql_key(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	not provisioning_sql_config_map(path, metadata_namespace(db))
	msg := sprintf("%s: service '%s' is missing ConfigMap/cnpg-verification-provisioning-sql", [path, svc])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	config_map := provisioning_sql_config_map(path, metadata_namespace(db))
	config_map_data := object.get(config_map, "data", {})
	object.get(config_map_data, provision_sql_key(svc), "") != expected_sql(svc)
	msg := sprintf("%s: ConfigMap/cnpg-verification-provisioning-sql key %s must match the derived SQL body", [path, provision_sql_key(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some role_name in expected_role_names(svc)
	not managed_role(path, db, role_name)
	msg := sprintf("%s: Cluster/%s is missing managed role %s", [path, cluster_name(db), role_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some role_name in {service_owner(svc), service_role(svc, "ro"), service_role(svc, "rw")}
	role := managed_role(path, db, role_name)
	not stable_role_shape(role)
	msg := sprintf("%s: managed role %s must be a stable NOLOGIN NOINHERIT role", [path, role_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	role_name := service_role(svc, "mig")
	role := managed_role(path, db, role_name)
	not stable_role_shape(role)
	msg := sprintf("%s: managed role %s must be a stable NOLOGIN NOINHERIT role", [path, role_name])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	role_name := service_role(svc, "mig")
	role := managed_role(path, db, role_name)
	object.get(role, "inRoles", []) != [service_owner(svc)]
	msg := sprintf("%s: managed role %s must inherit only %s", [path, role_name, service_owner(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	some role_name, expectation in expected_login_roles(svc)
	role := managed_role(path, db, role_name)
	not login_role_shape(role, expectation.group, expectation.secret)
	msg := sprintf("%s: managed login role %s must match group membership and password Secret", [path, role_name])
}

deny contains msg if {
	path := selected_paths[_]
	doc := docs_for_path(path)[_]
	value := string_values(doc)[_]
	fragment := placeholder_fragments[_]
	contains(value, fragment)
	msg := sprintf("%s: rendered CNPG bundle still contains legacy placeholder fragment %s", [path, fragment])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	not service_alias(path, svc, metadata_namespace(db))
	msg := sprintf("%s: service '%s' is missing Service/%s", [path, svc, service_alias_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	alias := service_alias(path, svc, metadata_namespace(db))
	object.get(object.get(alias, "spec", {}), "type", "") != "ExternalName"
	msg := sprintf("%s: Service/%s type must be ExternalName", [path, service_alias_name(svc)])
}

deny contains msg if {
	path := selected_paths[_]
	db := service_databases(path)[_]
	svc := service_name(db)
	alias := service_alias(path, svc, metadata_namespace(db))
	expected := sprintf("%s-rw.%s.svc.cluster.local", [cluster_name(db), metadata_namespace(db)])
	object.get(object.get(alias, "spec", {}), "externalName", "") != expected
	msg := sprintf("%s: Service/%s externalName must be %s", [path, service_alias_name(svc), expected])
}

selected_paths contains path if {
	path := rendered_paths[_]
	count(service_databases(path)) > 0
}

rendered_paths contains path if {
	is_array(input)
	entry := input[_]
	path := object.get(entry, "path", "")
	path != ""
}

docs_for_path(path) := docs if {
	docs := [entry.contents |
		entry := input[_]
		object.get(entry, "path", "") == path
		is_object(entry.contents)
	]
}

service_databases(path) := dbs if {
	dbs := [doc |
		doc := docs_for_path(path)[_]
		is_service_database(doc)
	]
}

is_service_database(doc) if {
	object.get(doc, "apiVersion", "") == "postgresql.cnpg.io/v1"
	object.get(doc, "kind", "") == "Database"
	spec := object.get(doc, "spec", {})
	svc := object.get(spec, "name", "")
	regex.match("^[a-z][a-z0-9]*$", svc)
	startswith(metadata_name(doc), "cnpg-eso-")
}

is_service_database(doc) if {
	object.get(doc, "apiVersion", "") == "postgresql.cnpg.io/v1"
	object.get(doc, "kind", "") == "Database"
	spec := object.get(doc, "spec", {})
	svc := object.get(spec, "name", "")
	regex.match("^[a-z][a-z0-9]*$", svc)
	startswith(object.get(object.get(spec, "cluster", {}), "name", ""), "cnpg-eso-")
}

cluster_for_database(path, db) if {
	cluster(path, cluster_name(db), metadata_namespace(db))
}

cluster(path, name, namespace) := doc if {
	doc := docs_for_path(path)[_]
	object.get(doc, "apiVersion", "") == "postgresql.cnpg.io/v1"
	object.get(doc, "kind", "") == "Cluster"
	metadata_name(doc) == name
	metadata_namespace(doc) == namespace
}

external_secret(path, name, namespace) := doc if {
	doc := docs_for_path(path)[_]
	object.get(doc, "kind", "") == "ExternalSecret"
	metadata_name(doc) == name
	metadata_namespace(doc) == namespace
}

provisioning_job(path, svc, namespace) := doc if {
	doc := docs_for_path(path)[_]
	object.get(doc, "kind", "") == "Job"
	metadata_name(doc) == provisioning_job_name(svc)
	metadata_namespace(doc) == namespace
}

provisioning_sql_config_map(path, namespace) := doc if {
	doc := docs_for_path(path)[_]
	object.get(doc, "kind", "") == "ConfigMap"
	metadata_name(doc) == "cnpg-verification-provisioning-sql"
	metadata_namespace(doc) == namespace
}

service_alias(path, svc, namespace) := doc if {
	doc := docs_for_path(path)[_]
	object.get(doc, "kind", "") == "Service"
	metadata_name(doc) == service_alias_name(svc)
	metadata_namespace(doc) == namespace
}

managed_role(path, db, role_name) := role if {
	cluster_doc := cluster(path, cluster_name(db), metadata_namespace(db))
	role := object.get(object.get(cluster_doc, "spec", {}), "managed", {}).roles[_]
	object.get(role, "name", "") == role_name
}

psql_container(job) := container if {
	container := object.get(object.get(object.get(job, "spec", {}), "template", {}).spec, "containers", [])[_]
	object.get(container, "name", "") == "psql"
}

env_present(container, name) if {
	env := object.get(container, "env", [])[_]
	object.get(env, "name", "") == name
}

env_value(container, name) := value if {
	env := object.get(container, "env", [])[_]
	object.get(env, "name", "") == name
	value := object.get(env, "value", "")
}

env_secret_name(container, name) := secret_name if {
	env := object.get(container, "env", [])[_]
	object.get(env, "name", "") == name
	secret_name := object.get(object.get(object.get(env, "valueFrom", {}), "secretKeyRef", {}), "name", "")
}

env_secret_key(container, name) := secret_key if {
	env := object.get(container, "env", [])[_]
	object.get(env, "name", "") == name
	secret_key := object.get(object.get(object.get(env, "valueFrom", {}), "secretKeyRef", {}), "key", "")
}

command_contains(container, fragment) if {
	command := object.get(container, "command", [])[_]
	contains(command, fragment)
}

stable_role_shape(role) if {
	object.get(role, "ensure", "") == "present"
	object.get(role, "login", true) == false
	object.get(role, "inherit", true) == false
}

login_role_shape(role, group, secret) if {
	object.get(role, "ensure", "") == "present"
	object.get(role, "login", false) == true
	object.get(role, "inherit", false) == true
	object.get(role, "connectionLimit", 0) == -1
	object.get(role, "inRoles", []) == [group]
	object.get(object.get(role, "passwordSecret", {}), "name", "") == secret
}

string_values(doc) := values if {
	values := {value |
		walk(doc, [_, value])
		is_string(value)
	}
}

metadata_name(doc) := object.get(object.get(doc, "metadata", {}), "name", "")

metadata_namespace(doc) := object.get(object.get(doc, "metadata", {}), "namespace", "")

service_name(db) := object.get(object.get(db, "spec", {}), "name", "")

cluster_name(db) := object.get(object.get(object.get(db, "spec", {}), "cluster", {}), "name", "")

service_owner(svc) := sprintf("%s_app", [svc])

service_role(svc, suffix) := sprintf("%s_app_%s", [svc, suffix])

service_secret(svc, suffix) := sprintf("cnpg-verification-%s-app-%s", [svc, suffix])

service_alias_name(svc) := sprintf("%s-db-rw", [svc])

provisioning_job_name(svc) := sprintf("cnpg-verification-provision-%s", [svc])

provision_sql_key(svc) := sprintf("provision-%s.sql", [svc])

expected_secret_usernames(svc) := {
	service_secret(svc, "ro-a"): service_role(svc, "ro_a"),
	service_secret(svc, "ro-b"): service_role(svc, "ro_b"),
	service_secret(svc, "rw-a"): service_role(svc, "rw_a"),
	service_secret(svc, "rw-b"): service_role(svc, "rw_b"),
	service_secret(svc, "mig-a"): service_role(svc, "mig_a"),
}

expected_role_names(svc) := {
	service_owner(svc),
	service_role(svc, "ro"),
	service_role(svc, "rw"),
	service_role(svc, "mig"),
	service_role(svc, "ro_a"),
	service_role(svc, "ro_b"),
	service_role(svc, "rw_a"),
	service_role(svc, "rw_b"),
	service_role(svc, "mig_a"),
}

expected_login_roles(svc) := {
	service_role(svc, "ro_a"): {"group": service_role(svc, "ro"), "secret": service_secret(svc, "ro-a")},
	service_role(svc, "ro_b"): {"group": service_role(svc, "ro"), "secret": service_secret(svc, "ro-b")},
	service_role(svc, "rw_a"): {"group": service_role(svc, "rw"), "secret": service_secret(svc, "rw-a")},
	service_role(svc, "rw_b"): {"group": service_role(svc, "rw"), "secret": service_secret(svc, "rw-b")},
	service_role(svc, "mig_a"): {"group": service_role(svc, "mig"), "secret": service_secret(svc, "mig-a")},
}

expected_sql(svc) := sql if {
	owner := service_owner(svc)
	ro := service_role(svc, "ro")
	rw := service_role(svc, "rw")
	mig := service_role(svc, "mig")
	sql := concat("", [
		sprintf("REVOKE ALL ON DATABASE %s FROM PUBLIC;\n", [svc]),
		sprintf("GRANT CONNECT ON DATABASE %s TO %s, %s, %s, %s;\n", [svc, owner, ro, rw, mig]),
		"DROP SCHEMA IF EXISTS public;\n",
		"\n",
		sprintf("GRANT USAGE ON SCHEMA %s TO %s;\n", [svc, ro]),
		sprintf("GRANT USAGE ON SCHEMA %s TO %s;\n", [svc, rw]),
		"\n",
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [owner, svc]),
		sprintf("  GRANT SELECT ON TABLES TO %s;\n", [ro]),
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [owner, svc]),
		sprintf("  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %s;\n", [rw]),
		sprintf("ALTER DEFAULT PRIVILEGES FOR ROLE %s IN SCHEMA %s\n", [owner, svc]),
		sprintf("  GRANT USAGE, SELECT ON SEQUENCES TO %s;\n", [rw]),
	])
}
