package main

import rego.v1

deny contains msg if {
	some cmd in input
	cmd.Cmd == "from"
	image_ref := cmd.Value[0]
	lower(image_ref) != "scratch"
	tag := _extract_dockerfile_tag(image_ref)
	tag != ""
	not semver.is_valid(tag)
	msg := sprintf(
		"Dockerfile FROM image '%s' has unpinned tag '%s' — must be a valid semver (MAJOR.MINOR.PATCH)",
		[image_ref, tag],
	)
}

deny contains msg if {
	some cmd in input
	cmd.Cmd == "from"
	image_ref := cmd.Value[0]
	lower(image_ref) != "scratch"
	_extract_dockerfile_tag(image_ref) == ""
	msg := sprintf(
		"Dockerfile FROM image '%s' has no tag — must include a pinned version tag",
		[image_ref],
	)
}

_extract_dockerfile_tag(image_ref) := tag if {
	segments := split(image_ref, "/")
	last := segments[count(segments) - 1]
	contains(last, ":")
	parts := split(last, ":")
	tag := parts[count(parts) - 1]
}

_extract_dockerfile_tag(image_ref) := "" if {
	segments := split(image_ref, "/")
	last := segments[count(segments) - 1]
	not contains(last, ":")
}
