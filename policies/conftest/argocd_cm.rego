package rendered

import rego.v1

argocd_bootstrap_overlays := {
	"main": {
		"source_path": "gitops/platform/argocd/bootstrap/overlays/main",
		"rendered_file": "kustomize--gitops-platform-argocd-bootstrap-overlays-main.yaml",
	},
	"ephemeral": {
		"source_path": "gitops/platform/argocd/bootstrap/overlays/ephemeral",
		"rendered_file": "kustomize--gitops-platform-argocd-bootstrap-overlays-ephemeral.yaml",
	},
}

argocd_cm_forbidden_data_keys := {
	"timeout.reconciliation",
	"timeout.reconciliation.jitter",
	"timeout.hard.reconciliation",
	"resource.customizations.health.postgresql.cnpg.io_Database",
}

argocd_cm_required_data := {"application.instanceLabelKey": "argocd.argoproj.io/instance"}

argocd_cm_required_data_keys := {
	"resource.exclusions",
	"resource.customizations.ignoreResourceUpdates.all",
}

deny contains msg if {
	overlay_name := argocd_required_overlay_names[_]
	overlay := argocd_bootstrap_overlays[overlay_name]
	count(argocd_cm_entries(overlay)) != 1
	msg := sprintf("%s: bootstrap overlay must render exactly one ConfigMap/argocd-cm", [overlay_name])
}

deny contains msg if {
	overlay := argocd_bootstrap_overlays.main
	entry := argocd_rendered_entries(overlay)[_]
	not argocd_is_cm(entry.contents)
	msg := sprintf("%s: main bootstrap overlay must render only ConfigMap/argocd-cm; found %s/%s", [entry.path, object.get(entry.contents, "kind", "unknown"), argocd_metadata_name(entry.contents)])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	argocd_metadata_namespace(subject.cm) != "argocd"
	msg := sprintf("%s: ConfigMap/argocd-cm metadata.namespace must be argocd", [subject.path])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	labels := object.get(argocd_metadata(subject.cm), "labels", {})
	object.get(labels, "app.kubernetes.io/part-of", "") != "argocd"
	msg := sprintf("%s: ConfigMap/argocd-cm label app.kubernetes.io/part-of must be argocd", [subject.path])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	annotations := object.get(argocd_metadata(subject.cm), "annotations", {})
	object.get(annotations, "argocd.argoproj.io/sync-wave", "") != "-90"
	msg := sprintf("%s: ConfigMap/argocd-cm annotation argocd.argoproj.io/sync-wave must be -90", [subject.path])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	cm_data := object.get(subject.cm, "data", {})
	some key, expected in argocd_cm_required_data
	object.get(cm_data, key, "") != expected
	msg := sprintf("%s: ConfigMap/argocd-cm data.%s must be %s", [subject.path, key, expected])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	cm_data := object.get(subject.cm, "data", {})
	key := argocd_cm_required_data_keys[_]
	not key in object.keys(cm_data)
	msg := sprintf("%s: ConfigMap/argocd-cm must include data.%s", [subject.path, key])
}

deny contains msg if {
	subject := argocd_cm_subjects[_]
	cm_data := object.get(subject.cm, "data", {})
	key := argocd_cm_forbidden_data_keys[_]
	key in object.keys(cm_data)
	msg := sprintf("%s: ConfigMap/argocd-cm must not include data.%s", [subject.path, key])
}

argocd_cm_subjects contains subject if {
	some overlay_name, overlay in argocd_bootstrap_overlays
	entry := argocd_cm_entries(overlay)[_]
	subject := {
		"overlay": overlay_name,
		"path": entry.path,
		"cm": entry.contents,
	}
}

argocd_required_overlay_names contains overlay_name if {
	some overlay_name, overlay in argocd_bootstrap_overlays
	argocd_discovered_overlay(overlay.source_path)
}

argocd_rendered_entries(overlay) := entries if {
	entries := [entry |
		entry := input[_]
		argocd_entry_basename(entry) == overlay.rendered_file
	]
}

argocd_cm_entries(overlay) := entries if {
	entries := [entry |
		entry := argocd_rendered_entries(overlay)[_]
		argocd_is_cm(entry.contents)
	]
}

argocd_discovered_overlay(source_path) if {
	overlay := data.render_contract.discovered_overlays[_]
	object.get(overlay, "path", "") == source_path
}

argocd_is_cm(doc) if {
	object.get(doc, "kind", "") == "ConfigMap"
	argocd_metadata_name(doc) == "argocd-cm"
}

argocd_metadata(doc) := object.get(doc, "metadata", {})

argocd_metadata_name(doc) := object.get(argocd_metadata(doc), "name", "unknown")

argocd_metadata_namespace(doc) := object.get(argocd_metadata(doc), "namespace", "")

argocd_entry_basename(entry) := base if {
	parts := split(object.get(entry, "path", ""), "/")
	base := parts[count(parts) - 1]
}
