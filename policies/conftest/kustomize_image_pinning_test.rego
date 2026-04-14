package main

import rego.v1

test_kustomize_placeholder_tag if {
	count(deny) == 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app", "newTag": "sha256:placeholder"},
	]}
}

test_kustomize_valid_digest if {
	count(deny) == 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app", "newTag": "sha256:a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"},
	]}
}

test_kustomize_latest_tag if {
	count(deny) > 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app", "newTag": "latest"},
	]}
}

test_kustomize_semver_tag if {
	count(deny) > 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app", "newTag": "v1.0.0"},
	]}
}

test_kustomize_no_newtag_skipped if {
	count(deny) == 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app"},
	]}
}

test_kustomize_short_digest_rejected if {
	count(deny) > 0 with input as {"images": [
		{"name": "ghcr.io/example/app", "newName": "ghcr.io/example/app", "newTag": "sha256:abcdef"},
	]}
}
