package main

import rego.v1

test_npm_pinned_exact if {
	count(deny) == 0 with input as {"devDependencies": {"nx": "22.7.1"}}
}

test_npm_pinned_with_prerelease if {
	count(deny) == 0 with input as {"dependencies": {"pkg": "1.2.3-rc.1"}}
}

test_npm_caret_rejected if {
	count(deny) > 0 with input as {"devDependencies": {"nx": "^22.7.1"}}
}

test_npm_tilde_rejected if {
	count(deny) > 0 with input as {"devDependencies": {"nx": "~22.7.1"}}
}

test_npm_range_rejected if {
	count(deny) > 0 with input as {"dependencies": {"pkg": ">=1.0.0"}}
}

test_npm_star_rejected if {
	count(deny) > 0 with input as {"dependencies": {"pkg": "*"}}
}

test_npm_dist_tag_rejected if {
	count(deny) > 0 with input as {"dependencies": {"pkg": "latest"}}
}

test_npm_missing_patch_rejected if {
	count(deny) > 0 with input as {"dependencies": {"pkg": "1.2"}}
}

test_npm_empty_version_rejected if {
	count(deny) > 0 with input as {"dependencies": {"pkg": ""}}
}

test_npm_peer_dependencies_validated if {
	count(deny) > 0 with input as {"peerDependencies": {"react": "^18.0.0"}}
}

test_npm_optional_dependencies_validated if {
	count(deny) > 0 with input as {"optionalDependencies": {"fsevents": "^2.0.0"}}
}

test_npm_no_deps_passes if {
	count(deny) == 0 with input as {"name": "pkg", "private": true}
}

test_npm_multiple_one_bad if {
	count(deny) == 1 with input as {"devDependencies": {"nx": "22.7.1", "pkg": "^1.0.0"}}
}

test_npm_overrides_validated if {
	count(deny) > 0 with input as {"overrides": {"transitive": "^1.2.3"}}
}

test_npm_nested_overrides_validated if {
	count(deny) > 0 with input as {"overrides": {"parent": {".": "1.0.0", "child": "~2.0.0"}}}
}

test_npm_pnpm_overrides_validated if {
	count(deny) > 0 with input as {"pnpm": {"overrides": {"transitive": "latest"}}}
}

test_npm_overrides_pinned_exact if {
	count(deny) == 0 with input as {"overrides": {"parent": {".": "1.0.0", "child": "2.0.0"}}}
}
