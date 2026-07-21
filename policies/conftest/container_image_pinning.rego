package raw_sources

import rego.v1

import data.policy.container_images

deny contains msg if {
	walk(input, [path, value])
	container_images.image_key(path[count(path) - 1])
	is_string(value)
	not container_images.skipped_string(value)
	msg := container_images.deny_message(value)
}
