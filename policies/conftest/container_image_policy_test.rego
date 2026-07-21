package policy.container_images

import rego.v1

test_extract_tag_handles_registry_port if {
	extract_tag("registry.example.invalid:5000/fixture/app:1.2.3") == "1.2.3"
}

test_valid_digest_pin_requires_tag if {
	not valid_image_ref("registry.example.invalid/fixture/app@sha256:1111111111111111111111111111111111111111111111111111111111111111")
}

test_malformed_digest_does_not_fall_back_to_semver_tag if {
	not valid_image_ref("registry.example.invalid/fixture/app:1.2.3@sha256:not-a-digest")
}

test_source_placeholder_tag_passes if {
	valid_image_ref("registry.example.invalid/fixture/app:sha256-placeholder")
}

test_rendered_source_placeholder_passes_as_full_reference if {
	valid_image_ref("registry.example.invalid/fixture/app:sha256:placeholder")
}

test_placeholder_suffix_is_not_plain_tag_support if {
	not semver.is_valid(extract_tag("registry.example.invalid/fixture/app:sha256:placeholder"))
}

test_latest_tag_fails if {
	not valid_image_ref("registry.example.invalid/fixture/app:latest")
}
