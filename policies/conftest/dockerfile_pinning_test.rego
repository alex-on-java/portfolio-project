package main

import rego.v1

test_dockerfile_pinned_semver if {
	count(deny) == 0 with input as [{"Cmd": "from", "Value": ["nginx:1.27.4-alpine"]}]
}

test_dockerfile_pinned_no_prerelease if {
	count(deny) == 0 with input as [{"Cmd": "from", "Value": ["python:3.12.1"]}]
}

test_dockerfile_latest_rejected if {
	count(deny) > 0 with input as [{"Cmd": "from", "Value": ["nginx:latest"]}]
}

test_dockerfile_no_tag_rejected if {
	count(deny) > 0 with input as [{"Cmd": "from", "Value": ["nginx"]}]
}

test_dockerfile_missing_patch_rejected if {
	count(deny) > 0 with input as [{"Cmd": "from", "Value": ["python:3.12"]}]
}

test_dockerfile_scratch_skipped if {
	count(deny) == 0 with input as [{"Cmd": "from", "Value": ["scratch"]}]
}

test_dockerfile_with_as_stage if {
	count(deny) == 0 with input as [{"Cmd": "from", "Value": ["golang:1.22.0", "as", "builder"]}]
}

test_dockerfile_non_from_skipped if {
	count(deny) == 0 with input as [{"Cmd": "run", "Value": ["echo hello"]}]
}
