package rendered_sources

import rego.v1

import data.policy.container_images

deny contains msg if {
	is_array(input)
	entry := input[_]
	is_object(entry.contents)
	walk(entry.contents, [path, value])
	container_images.image_key(path[count(path) - 1])
	is_string(value)
	not container_images.skipped_string(value)
	image_msg := container_images.deny_message(value)
	msg := sprintf("%s: %s", [object.get(entry, "path", "unknown"), image_msg])
}
