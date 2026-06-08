package main

import rego.v1

deny contains msg if {
	walk(input, [path, value])
	path[count(path) - 1] == "image"
	is_string(value)
	not contains(value, "${{")
	not contains(value, "{{")
	not _valid_digest_pin(value)
	tag := _extract_tag(value)
	tag != ""
	not _valid_container_tag(tag)
	msg := sprintf(
		"Container image '%s' has unpinned tag '%s' — must be 'sha256-placeholder' or a valid semver (MAJOR.MINOR.PATCH)",
		[value, tag],
	)
}

deny contains msg if {
	walk(input, [path, value])
	path[count(path) - 1] == "image"
	is_string(value)
	not contains(value, "${{")
	not contains(value, "{{")
	not _valid_digest_pin(value)
	_extract_tag(value) == ""
	msg := sprintf(
		"Container image '%s' has no tag — must include a pinned version tag",
		[value],
	)
}

_valid_digest_pin(image) if {
	parts := split(image, "@")
	count(parts) == 2
	regex.match("^sha256:[a-f0-9]{64}$", parts[1])
	_extract_tag(parts[0]) != ""
}

_extract_tag(image) := tag if {
	segments := split(image, "/")
	last := segments[count(segments) - 1]
	contains(last, ":")
	parts := split(last, ":")
	tag := parts[count(parts) - 1]
}

_extract_tag(image) := "" if {
	segments := split(image, "/")
	last := segments[count(segments) - 1]
	not contains(last, ":")
}

_valid_container_tag(tag) if {
	tag == "sha256-placeholder"
}

_valid_container_tag(tag) if {
	semver.is_valid(tag)
}
