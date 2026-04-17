package main

import rego.v1

test_pyproject_runtime_pinned if {
	count(deny) == 0 with input as {"project": {"dependencies": ["pyyaml==6.0.3"]}}
}

test_pyproject_dev_group_pinned if {
	count(deny) == 0 with input as {"dependency-groups": {"dev": ["mypy==1.20.1"]}}
}

test_pyproject_ranged_specifier_rejected if {
	count(deny) > 0 with input as {"project": {"dependencies": ["pyyaml>=6.0.3"]}}
}

test_pyproject_bare_name_rejected if {
	count(deny) > 0 with input as {"project": {"dependencies": ["pyyaml"]}}
}

test_pyproject_multi_clause_rejected if {
	count(deny) > 0 with input as {"dependency-groups": {"dev": ["mypy==1.20.1,!=1.20.0"]}}
}

test_pyproject_inline_comment_rejected if {
	count(deny) > 0 with input as {"dependency-groups": {"dev": ["mypy==1.20.1 # ok"]}}
}

test_pyproject_direct_url_rejected if {
	count(deny) > 0 with input as {"dependency-groups": {"dev": ["foo @ https://example.com/foo.whl"]}}
}

test_pyproject_extras_pinned_accepted if {
	count(deny) == 0 with input as {"project": {"dependencies": ["requests[socks]==2.32.3"]}}
}

test_pyproject_pep440_prerelease_accepted if {
	count(deny) == 0 with input as {"project": {"dependencies": ["pkg==1.2.3rc1"]}}
}

test_pyproject_pep440_local_accepted if {
	count(deny) == 0 with input as {"project": {"dependencies": ["torch==2.2.0+cpu"]}}
}

test_pyproject_env_marker_accepted if {
	count(deny) == 0 with input as {"project": {"dependencies": [`pkg==1.2.3 ; python_version >= "3.10"`]}}
}

test_pyproject_incomplete_version_rejected if {
	count(deny) > 0 with input as {"project": {"dependencies": ["pkg==1.2"]}}
}

test_pyproject_requires_python_not_flagged if {
	count(deny) == 0 with input as {"project": {
		"requires-python": ">=3.13,<3.14",
		"dependencies": ["pyyaml==6.0.3"],
	}}
}

test_pyproject_mise_shape_input_is_noop if {
	count(deny) == 0 with input as {"tools": {"kubectl": "1.35.1", "python": "3.13.12"}}
}

test_pyproject_empty_dependencies_pass if {
	count(deny) == 0 with input as {"project": {"dependencies": []}, "dependency-groups": {"dev": []}}
}
