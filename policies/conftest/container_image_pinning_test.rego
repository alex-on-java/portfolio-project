package main

import rego.v1

test_container_pinned_semver if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "nginx:1.27.4"},
	]}}
}

test_container_pinned_semver_prerelease if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "nginx:1.27.4-alpine"},
	]}}
}

test_container_sha256_placeholder if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "ghcr.io/alex-on-java/web-app:sha256-placeholder"},
	]}}
}

test_container_latest_rejected if {
	count(deny) > 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "nginx:latest"},
	]}}
}

test_container_no_tag_rejected if {
	count(deny) > 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "ghcr.io/alex-on-java/web-app"},
	]}}
}

test_container_missing_patch_rejected if {
	count(deny) > 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "python:3.12"},
	]}}
}

test_container_kargo_template_skipped if {
	count(deny) == 0 with input as {"spec": {"steps": [
		{"config": {"images": [{"image": "${{ vars.warehouseImageURL }}"}]}},
	]}}
}

test_container_argocd_template_skipped if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "{{ .Values.image }}"},
	]}}
}

test_container_image_object_skipped if {
	count(deny) == 0 with input as {"spec": {"subscriptions": [
		{"image": {"repoURL": "ghcr.io/example/app", "imageSelectionStrategy": "NewestBuild"}},
	]}}
}

test_container_deeply_nested if {
	count(deny) > 0 with input as {"spec": {"template": {"spec": {"containers": [
		{"name": "app", "image": "node:lts"},
	]}}}}
}

test_container_registry_with_port if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "registry:5000/myapp:1.0.0"},
	]}}
}
