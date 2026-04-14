package main

import rego.v1

test_mise_pinned_version if {
	count(deny) == 0 with input as {"tools": {"kubectl": "1.33.9"}}
}

test_mise_pinned_aqua_prefix if {
	count(deny) == 0 with input as {"tools": {"aqua:argoproj/argo-cd": "3.3.4"}}
}

test_mise_unpinned_latest if {
	count(deny) > 0 with input as {"tools": {"node": "latest"}}
}

test_mise_unpinned_missing_patch if {
	count(deny) > 0 with input as {"tools": {"python": "3.12"}}
}

test_mise_empty_version if {
	count(deny) > 0 with input as {"tools": {"kubectl": ""}}
}

test_mise_multiple_tools_one_bad if {
	count(deny) == 1 with input as {"tools": {"kubectl": "1.33.9", "node": "latest"}}
}
