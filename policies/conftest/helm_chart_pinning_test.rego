package main

import rego.v1

test_helm_chart_pinned_semver if {
	count(deny) == 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": "v1.20.1"},
	]}}}}
}

test_helm_chart_pinned_no_v_prefix if {
	count(deny) == 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": "0.4.0"},
	]}}}}
}

test_helm_chart_unpinned_star if {
	count(deny) > 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": "*"},
	]}}}}
}

test_helm_chart_unpinned_missing_patch if {
	count(deny) > 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": "1.20"},
	]}}}}
}

test_helm_chart_unpinned_empty if {
	count(deny) > 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": ""},
	]}}}}
}

test_helm_git_source_skipped if {
	count(deny) == 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://github.com/example/repo.git", "targetRevision": "{{metadata.annotations.target-revision}}", "ref": "values"},
	]}}}}
}

test_helm_mixed_sources if {
	count(deny) == 0 with input as {"spec": {"template": {"spec": {"sources": [
		{"repoURL": "https://charts.example.io", "chart": "my-chart", "targetRevision": "v1.20.1"},
		{"repoURL": "https://github.com/example/repo.git", "targetRevision": "{{metadata.annotations.target-revision}}", "ref": "values"},
	]}}}}
}
