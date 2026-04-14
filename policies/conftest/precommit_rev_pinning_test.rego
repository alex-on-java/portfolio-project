package main

import rego.v1

test_precommit_pinned_rev if {
	count(deny) == 0 with input as {"repos": [
		{"repo": "https://github.com/pre-commit/pre-commit-hooks", "rev": "v6.0.0"},
	]}
}

test_precommit_unpinned_rev if {
	count(deny) > 0 with input as {"repos": [
		{"repo": "https://github.com/example/hooks", "rev": "main"},
	]}
}

test_precommit_empty_rev if {
	count(deny) > 0 with input as {"repos": [
		{"repo": "https://github.com/example/hooks", "rev": ""},
	]}
}

test_precommit_local_repo_skipped if {
	count(deny) == 0 with input as {"repos": [
		{"repo": "local", "hooks": [{"id": "my-hook"}]},
	]}
}

test_precommit_mixed_repos if {
	count(deny) == 0 with input as {"repos": [
		{"repo": "https://github.com/pre-commit/pre-commit-hooks", "rev": "v6.0.0"},
		{"repo": "local", "hooks": [{"id": "my-hook"}]},
	]}
}

test_precommit_sha_rev_rejected if {
	count(deny) > 0 with input as {"repos": [
		{"repo": "https://github.com/example/hooks", "rev": "abc123def456"},
	]}
}

test_precommit_four_component_version if {
	count(deny) == 0 with input as {"repos": [
		{"repo": "https://github.com/shellcheck-py/shellcheck-py", "rev": "v0.11.0.1"},
	]}
}
