package main

import rego.v1

deny contains msg if {
	some img in input.images
	img.newTag
	not _valid_kustomize_tag(img.newTag)
	msg := sprintf(
		"Kustomize image '%s' has unpinned newTag '%s' — must be 'sha256:placeholder' or a valid digest (sha256:<64 hex chars>)",
		[img.name, img.newTag],
	)
}

_valid_kustomize_tag(tag) if {
	tag == "sha256:placeholder"
}

_valid_kustomize_tag(tag) if {
	regex.match(`^sha256:[a-f0-9]{64}$`, tag)
}
