package policy.container_images

import rego.v1

image_key("image")

skipped_string(value) if {
	contains(value, "{{")
}

valid_image_ref(image) if {
	source_template_placeholder(image)
}

valid_image_ref(image) if {
	valid_digest_pin(image)
}

valid_image_ref(image) if {
	not contains(image, "@")
	tag := extract_tag(image)
	tag != ""
	semver.is_valid(tag)
}

source_template_placeholder(image) if {
	extract_tag(image) == "sha256-placeholder"
}

source_template_placeholder(image) if {
	not contains(image, "@")
	segments := split(image, "/")
	last := segments[count(segments) - 1]
	endswith(last, ":sha256:placeholder")
}

valid_digest_pin(image) if {
	parts := split(image, "@")
	count(parts) == 2
	regex.match("^sha256:[a-f0-9]{64}$", parts[1])
	extract_tag(parts[0]) != ""
}

extract_tag(image) := tag if {
	segments := split(image, "/")
	last := segments[count(segments) - 1]
	contains(last, ":")
	parts := split(last, ":")
	tag := parts[count(parts) - 1]
}

extract_tag(image) := "" if {
	segments := split(image, "/")
	last := segments[count(segments) - 1]
	not contains(last, ":")
}

deny_message(image) := msg if {
	not valid_image_ref(image)
	contains(image, "@")
	msg := sprintf(
		"Container image '%s' has malformed digest pin — must include a tag and a sha256 digest (tag@sha256:<64 hex chars>)",
		[image],
	)
}

deny_message(image) := msg if {
	not valid_image_ref(image)
	not contains(image, "@")
	extract_tag(image) == ""
	msg := sprintf(
		"Container image '%s' has no tag — must include a pinned version tag",
		[image],
	)
}

deny_message(image) := msg if {
	not valid_image_ref(image)
	not contains(image, "@")
	tag := extract_tag(image)
	tag != ""
	msg := sprintf(
		"Container image '%s' has unpinned tag '%s' — must be 'sha256-placeholder', 'sha256:placeholder', a valid semver (MAJOR.MINOR.PATCH), or a tag plus sha256 digest",
		[image, tag],
	)
}
