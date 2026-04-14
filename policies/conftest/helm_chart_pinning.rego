package main

import rego.v1

deny contains msg if {
	some source in input.spec.template.spec.sources
	source.chart
	not semver.is_valid(source.targetRevision)
	msg := sprintf(
		"Helm chart '%s' has unpinned targetRevision '%s' — must be a valid semver (MAJOR.MINOR.PATCH)",
		[source.chart, source.targetRevision],
	)
}
