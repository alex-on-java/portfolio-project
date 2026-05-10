package main

import rego.v1

_npm_dependency_groups := [
	"dependencies",
	"devDependencies",
	"peerDependencies",
	"optionalDependencies",
]

_npm_override_groups := [
	["overrides"],
	["pnpm", "overrides"],
]

_valid_npm_pin := `^[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+-]*$`

deny contains msg if {
	some group in _npm_dependency_groups
	some name, version in input[group]
	not regex.match(_valid_npm_pin, version)
	msg := sprintf(
		"package.json %s entry '%s: %s' is not pinned to an exact version (expected X.Y.Z with optional PEP 440-style suffix; ranges, ^, ~, *, and tags are not allowed)",
		[group, name, version],
	)
}

deny contains msg if {
	is_object(input)
	some group_path in _npm_override_groups
	overrides := object.get(input, group_path, {})
	walk(overrides, [path, version])
	count(path) > 0
	is_string(version)
	not regex.match(_valid_npm_pin, version)
	msg := sprintf(
		"package.json %s override entry '%s: %s' is not pinned to an exact version (expected X.Y.Z with optional PEP 440-style suffix; ranges, ^, ~, *, and tags are not allowed)",
		[concat(".", group_path), concat(".", path), version],
	)
}
