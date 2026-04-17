package main

import rego.v1

_valid_pin := `^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9_, .-]+\])?==[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.+]*(\s*;\s*.+)?$`

deny contains msg if {
	some dep in input.project.dependencies
	not regex.match(_valid_pin, dep)
	msg := sprintf(
		"pyproject.toml [project].dependencies entry '%s' is not pinned to an exact patch version (expected name==X.Y.Z with optional PEP 440 suffix and environment marker)",
		[dep],
	)
}

deny contains msg if {
	some group_name, deps in input["dependency-groups"]
	some dep in deps
	not regex.match(_valid_pin, dep)
	msg := sprintf(
		"pyproject.toml [dependency-groups].%s entry '%s' is not pinned to an exact patch version (expected name==X.Y.Z with optional PEP 440 suffix and environment marker)",
		[group_name, dep],
	)
}
