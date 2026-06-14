package rendered

import rego.v1

sentinel_remote_ref_key := "REPLACE_IN_OVERLAY"

production_key_suffix := "-prd"

main_lifecycle_segment := "main"

supported_namespace_envs := {"dev", "stg", "prd"}

workload_gsm_contracts := {
	"web-app-demo-gsm": {
		"workload": "web-app",
		"name": "web-app-demo-gsm",
		"store_kind": "ClusterSecretStore",
		"store_name": "gcp-secret-manager",
		"required": {
			"any/dev": {"namespace": "dev", "key": "portfolio-project-web-app-demo-dev"},
			"any/stg": {"namespace": "stg", "key": "portfolio-project-web-app-demo-stg"},
			"ephemeral/prd": {"namespace": "prd", "key": "portfolio-project-web-app-demo-stg"},
			"main/prd": {"namespace": "prd", "key": "portfolio-project-web-app-demo-prd"},
		},
	},
}

deny contains msg if {
	entry := input[_]
	is_external_secret(entry.contents)
	key := data_remote_ref_keys(entry.contents)[_]
	key == sentinel_remote_ref_key
	msg := sprintf("%s: ExternalSecret/%s spec.data[].remoteRef.key must not be %s", [entry_basename(entry), metadata_name(entry.contents), sentinel_remote_ref_key])
}

deny contains msg if {
	subject := workload_gsm_subjects[_]
	not subject_has_contract(subject)
	msg := sprintf("%s: ExternalSecret/%s is a workload GSM subject but has no rendered secret contract for workload %s", [subject.basename, metadata_name(subject.doc), subject.workload])
}

deny contains msg if {
	subject := declared_workload_gsm_subjects[_]
	not subject.overlay_key in object.keys(subject.contract.required)
	msg := sprintf("%s: ExternalSecret/%s overlay %s is not declared in its rendered secret contract", [subject.basename, metadata_name(subject.doc), subject.overlay_key])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	namespace := metadata_namespace(subject.doc)
	namespace == ""
	msg := sprintf("%s: ExternalSecret/%s must render metadata.namespace", [subject.basename, metadata_name(subject.doc)])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	namespace := metadata_namespace(subject.doc)
	namespace != ""
	not namespace in supported_namespace_envs
	msg := sprintf("%s: ExternalSecret/%s namespace %s is not a supported workload environment", [subject.basename, metadata_name(subject.doc), namespace])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	namespace := metadata_namespace(subject.doc)
	expected := subject.required.namespace
	namespace != ""
	namespace in supported_namespace_envs
	namespace != expected
	msg := sprintf("%s: ExternalSecret/%s namespace %s must match rendered path environment %s", [subject.basename, metadata_name(subject.doc), namespace, expected])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	target := object.get(object.get(subject.doc, "spec", {}), "target", {})
	object.get(target, "name", "") != subject.contract.name
	msg := sprintf("%s: ExternalSecret/%s target.name must be %s", [subject.basename, metadata_name(subject.doc), subject.contract.name])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	data_from_find(subject.doc)
	msg := sprintf("%s: ExternalSecret/%s spec.dataFrom[].find is unsupported for workload GSM contracts", [subject.basename, metadata_name(subject.doc)])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	data_from_extract_key := data_from_extract_keys(subject.doc)[_]
	msg := sprintf("%s: ExternalSecret/%s spec.dataFrom[].extract.key=%s is unsupported; use spec.data[].remoteRef.key for workload GSM contracts", [subject.basename, metadata_name(subject.doc), data_from_extract_key])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	subject.lifecycle != main_lifecycle_segment
	key := data_remote_ref_keys(subject.doc)[_]
	endswith(key, production_key_suffix)
	msg := sprintf("%s: ExternalSecret/%s ephemeral-reachable overlay must not reference production GSM key %s", [subject.basename, metadata_name(subject.doc), key])
}

deny contains msg if {
	subject := declared_required_workload_gsm_subjects[_]
	expected := subject.required.key
	not expected in data_remote_ref_keys(subject.doc)
	msg := sprintf("%s: ExternalSecret/%s must use GSM key %s for overlay %s", [subject.basename, metadata_name(subject.doc), expected, subject.overlay_key])
}

deny contains msg if {
	render_contract_data_available
	some contract_id, contract in workload_gsm_contracts
	some overlay_key, required in contract.required
	not discovered_contract_overlay(contract.workload, overlay_key)
	msg := sprintf("overlays/%s: workload %s required GSM contract %s was not discovered", [overlay_key, contract.workload, contract_id])
}

deny contains msg if {
	render_contract_data_available
	some contract_id, contract in workload_gsm_contracts
	some overlay_key, required in contract.required
	not rendered_contract_subject(contract, overlay_key)
	msg := sprintf("overlays/%s: workload %s required rendered ExternalSecret/%s was not found", [overlay_key, contract.workload, contract.name])
}

declared_required_workload_gsm_subjects contains subject if {
	base := declared_workload_gsm_subjects[_]
	required := base.contract.required[base.overlay_key]
	subject := object.union(base, {"required": required})
}

declared_workload_gsm_subjects contains subject if {
	base := workload_gsm_subjects[_]
	contract := contract_for_subject(base)
	subject := object.union(base, {"contract": contract})
}

workload_gsm_subjects contains subject if {
	entry := input[_]
	doc := entry.contents
	is_external_secret(doc)
	overlay := rendered_workload_overlay(entry.path)
	secret_store_ref(doc, "ClusterSecretStore", "gcp-secret-manager")
	subject := {
		"basename": entry_basename(entry),
		"doc": doc,
		"workload": overlay.workload,
		"lifecycle": overlay.lifecycle,
		"env": overlay.env,
		"overlay_key": sprintf("%s/%s", [overlay.lifecycle, overlay.env]),
	}
}

contract_for_subject(subject) := contract if {
	some contract_id
	contract := workload_gsm_contracts[contract_id]
	contract.workload == subject.workload
	contract.name == metadata_name(subject.doc)
}

subject_has_contract(subject) if {
	contract_for_subject(subject)
}

rendered_contract_subject(contract, overlay_key) if {
	subject := declared_required_workload_gsm_subjects[_]
	subject.contract == contract
	subject.overlay_key == overlay_key
}

discovered_contract_overlay(workload, overlay_key) if {
	overlay := data.render_contract.discovered_overlays[_]
	parsed := source_workload_overlay(overlay.path)
	parsed.workload == workload
	sprintf("%s/%s", [parsed.lifecycle, parsed.env]) == overlay_key
}

render_contract_data_available if {
	count(object.get(data.render_contract, "discovered_overlays", [])) > 0
}

rendered_workload_overlay(path) := overlay if {
	base := basename(path)
	startswith(base, "kustomize--")
	endswith(base, ".yaml")
	stem := trim_suffix(trim_prefix(base, "kustomize--"), ".yaml")
	tokens := split(stem, "-")
	workloads_index := token_index(tokens, "workloads")
	overlays_index := token_index(tokens, "overlays")
	overlays_index > workloads_index + 1
	count(tokens) > overlays_index + 2
	workload_tokens := array.slice(tokens, workloads_index + 1, overlays_index)
	overlay := {
		"workload": concat("-", workload_tokens),
		"lifecycle": tokens[overlays_index + 1],
		"env": tokens[overlays_index + 2],
	}
}

source_workload_overlay(path) := overlay if {
	parts := split(path, "/")
	workloads_index := token_index(parts, "workloads")
	overlays_index := token_index(parts, "overlays")
	overlays_index == workloads_index + 2
	count(parts) > overlays_index + 2
	overlay := {
		"workload": parts[workloads_index + 1],
		"lifecycle": parts[overlays_index + 1],
		"env": parts[overlays_index + 2],
	}
}

token_index(tokens, token) := idx if {
	some idx
	tokens[idx] == token
}

is_external_secret(doc) if {
	object.get(doc, "kind", "") == "ExternalSecret"
}

secret_store_ref(doc, kind, name) if {
	ref := object.get(object.get(doc, "spec", {}), "secretStoreRef", {})
	object.get(ref, "kind", "") == kind
	object.get(ref, "name", "") == name
}

data_remote_ref_keys(doc) := keys if {
	keys := {key |
		item := object.get(object.get(doc, "spec", {}), "data", [])[_]
		key := object.get(object.get(item, "remoteRef", {}), "key", "")
		key != ""
	}
}

data_from_extract_keys(doc) := keys if {
	keys := {key |
		item := object.get(object.get(doc, "spec", {}), "dataFrom", [])[_]
		key := object.get(object.get(item, "extract", {}), "key", "")
		key != ""
	}
}

data_from_find(doc) if {
	item := object.get(object.get(doc, "spec", {}), "dataFrom", [])[_]
	"find" in object.keys(item)
}

entry_basename(entry) := basename(object.get(entry, "path", "unknown"))

basename(path) := base if {
	parts := split(path, "/")
	base := parts[count(parts) - 1]
}

metadata_name(doc) := object.get(object.get(doc, "metadata", {}), "name", "unknown")

metadata_namespace(doc) := object.get(object.get(doc, "metadata", {}), "namespace", "")
