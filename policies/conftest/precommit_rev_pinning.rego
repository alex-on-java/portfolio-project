package main

import rego.v1

deny contains msg if {
	some repo in input.repos
	repo.repo != "local"
	not _valid_precommit_rev(repo.rev)
	msg := sprintf(
		"Pre-commit repo '%s' has unpinned rev '%s' — must be a valid semver or numeric multi-component version",
		[repo.repo, repo.rev],
	)
}

_valid_precommit_rev(rev) if {
	semver.is_valid(rev)
}

_valid_precommit_rev(rev) if {
	regex.match(`^v?\d+\.\d+\.\d+(\.\d+)+$`, rev)
}
