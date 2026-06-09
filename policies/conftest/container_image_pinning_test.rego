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

test_container_digest_pin if {
	count(deny) == 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "postgres:18.3@sha256:7e32e9833a6fb1c92c32552794cb6ed569d51b445a54907d35fc112ef39684db"},
	]}}
}

test_container_digest_without_tag_rejected if {
	count(deny) > 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "postgres@sha256:7e32e9833a6fb1c92c32552794cb6ed569d51b445a54907d35fc112ef39684db"},
	]}}
}

test_container_malformed_digest_rejected if {
	count(deny) > 0 with input as {"spec": {"containers": [
		{"name": "app", "image": "postgres:18.3@sha256:not-a-digest"},
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

test_cnpg_cluster_imagename_digest_pinned if {
	count(deny) == 0 with input as {"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster", "spec": {"imageName": "ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie@sha256:0f29b435fb501ee534cd0c555d122a6b8e90de477de8e8381c82c5e10d9a9de4"}}
}

test_cnpg_cluster_imagename_floating_tag_rejected if {
	count(deny) > 0 with input as {"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster", "spec": {"imageName": "ghcr.io/cloudnative-pg/postgresql:18.3-system-trixie"}}
}

test_cnpg_cluster_imagename_no_tag_rejected if {
	count(deny) > 0 with input as {"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster", "spec": {"imageName": "ghcr.io/cloudnative-pg/postgresql"}}
}

test_cnpg_cluster_imagename_object_skipped if {
	count(deny) == 0 with input as {"apiVersion": "postgresql.cnpg.io/v1", "kind": "Cluster", "spec": {"imageCatalogRef": {"imageName": {"kind": "ImageCatalog"}}}}
}
