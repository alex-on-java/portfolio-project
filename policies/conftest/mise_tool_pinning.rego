package main

import rego.v1

deny contains msg if {
	some tool, version in input.tools
	not semver.is_valid(version)
	msg := sprintf(
		"mise tool '%s' has unpinned version '%s' — must be a valid semver (MAJOR.MINOR.PATCH)",
		[tool, version],
	)
}
