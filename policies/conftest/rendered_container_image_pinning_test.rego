package rendered_sources

import rego.v1

rendered_image_path := "rendered-fixture.yaml"

test_rendered_container_semver_passes if {
	count(rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "nginx:1.27.4"}]}})) == 0
}

test_rendered_container_digest_pin_passes if {
	count(rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "postgres:18.3@sha256:1111111111111111111111111111111111111111111111111111111111111111"}]}})) == 0
}

test_rendered_source_placeholder_tag_passes if {
	count(rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "registry.example.invalid/fixture/app:sha256-placeholder"}]}})) == 0
}

test_rendered_kustomize_placeholder_reference_passes if {
	count(rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "registry.example.invalid/fixture/app:sha256:placeholder"}]}})) == 0
}

test_rendered_container_latest_fails if {
	msg := "rendered-fixture.yaml: Container image 'nginx:latest' has unpinned tag 'latest' — must be 'sha256-placeholder', 'sha256:placeholder', a valid semver (MAJOR.MINOR.PATCH), or a tag plus sha256 digest"
	msg in rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "nginx:latest"}]}})
}

test_rendered_container_no_tag_fails if {
	msg := "rendered-fixture.yaml: Container image 'registry.example.invalid/fixture/app' has no tag — must include a pinned version tag"
	msg in rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "registry.example.invalid/fixture/app"}]}})
}

test_rendered_container_malformed_digest_fails if {
	msg := "rendered-fixture.yaml: Container image 'registry.example.invalid/fixture/postgres:18.3@sha256:not-a-digest' has malformed digest pin — must include a tag and a sha256 digest (tag@sha256:<64 hex chars>)"
	msg in rendered_image_deny({"kind": "Pod", "spec": {"containers": [{"name": "app", "image": "registry.example.invalid/fixture/postgres:18.3@sha256:not-a-digest"}]}})
}

test_rendered_template_string_skipped if {
	count(rendered_image_deny({"kind": "ConfigMap", "spec": {"template": {"image": "${{ vars.warehouseImageURL }}"}}})) == 0
}

test_rendered_image_object_skipped if {
	count(rendered_image_deny({"kind": "Warehouse", "spec": {"subscriptions": [{"image": {"repoURL": "registry.example.invalid/fixture/app"}}]}})) == 0
}

rendered_image_deny(doc) := result if {
	result := deny with input as [{"path": rendered_image_path, "contents": doc}] with data.render_contract as {"discovered_overlays": []} with data.rendered_sources.workload_gsm_contracts as {}
}
