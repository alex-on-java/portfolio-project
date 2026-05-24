# LL-0051: `roles/compute.networkAdmin` Grants Read-Only Access to Firewalls, Not Delete

**Summary**: The predefined GCP role `roles/compute.networkAdmin` reads as a network-administrator grant by name, but its firewall surface is read-only: `compute.firewalls.get`, `.list`, `.listEffectiveTags`, and `.listTagBindings`. It does not grant `compute.firewalls.create`, `.update`, or `.delete`. A CI service account bound to `roles/compute.networkAdmin` therefore fails `gcloud compute firewall-rules delete` with `PERMISSION_DENIED`, even though every read and listing of firewall rules succeeds. The narrowest predefined role that includes `.delete` is `roles/compute.securityAdmin`, which carries 168 permissions in total and is the seat of all firewall mutation.

## What Happened

A new sweep step in the ephemeral-cluster teardown workflow identified an orphan CCM firewall rule and invoked `gcloud compute firewall-rules delete` against it. The CI service account `portfolio-project-github@cv-driven-dev-e-commerce.iam.gserviceaccount.com` held `roles/compute.networkAdmin` alongside ten other project roles in `infra/iam/main.tf`. On the first invocation of the sweep whose filter ever matched a row, the gap surfaced:

```
ERROR: ... Required 'compute.firewalls.delete' permission for
'projects/.../firewalls/k8s-6092493700879eb8-node-http-hc'
```

Audit logs captured `PERMISSION_DENIED` with status code 7 against `v1.compute.firewalls.delete`, with no preceding warning. The list call that fed the delete had succeeded normally, because `roles/compute.networkAdmin` does grant `.list`. Role name and list-call success together produced the false impression that delete would also succeed.

## Root Cause

`roles/compute.networkAdmin` enumerates 944 permissions, of which exactly four name `compute.firewalls.*`: `get`, `list`, `listEffectiveTags`, `listTagBindings`. Official documentation describes the role as covering "create, modify, and delete networking resources, except for firewall rules and SSL certificates"; the exception clause is load-bearing. Mutate operations on firewalls live in a different predefined role, `roles/compute.securityAdmin`, alongside SSL certificates, security policies, and packet mirrorings.

Role naming is the trap. A reader scanning the catalog assigns `compute.networkAdmin` the obvious scope by analogy with `container.admin` or `storage.admin`: anything under `compute.firewalls.*` ought to belong to it. Yet the firewall surface of that role contradicts the analogy, and the contradiction is invisible at binding time. Static IAM analysis tools that report "the SA has Network Admin" do not flag the gap, because the role itself is present and intact.

## Resolution

The smallest grant that closes the gap is a custom role with a single permission:

```hcl
resource "google_project_iam_custom_role" "ci_firewall_sweeper" {
  project     = var.project_id
  role_id     = "ciFirewallSweeper"
  title       = "CI Firewall Sweeper"
  description = "Delete CCM-orphan cluster-scoped firewalls during ephemeral cluster teardown"
  permissions = ["compute.firewalls.delete"]
  stage       = "GA"
}

resource "google_project_iam_member" "ci_firewall_sweeper" {
  project = var.project_id
  role    = google_project_iam_custom_role.ci_firewall_sweeper.id
  member  = "serviceAccount:${google_service_account.ci.email}"
}
```

The predefined alternative is `roles/compute.securityAdmin`. That role grants `compute.firewalls.delete` along with 167 other permissions covering firewall policies, SSL certificates, security policies, packet mirrorings, and SSL policies. None of the other 167 permissions are needed by the sweep step. Granting `roles/compute.securityAdmin` to obtain one permission widens the blast radius of a compromised CI token across the entire compute-security surface of the project, with no operational benefit.

Audit logs from the next destroy run confirmed the fix: two `v1.compute.firewalls.delete` entries (request acceptance and operation completion), both with empty `status.code`. The pre-fix run on the same SHA logged `status.code=7`.

## How to Detect

Symptoms that distinguish this failure from a generic IAM gap:

- The CI service account is bound to `roles/compute.networkAdmin` (or a similarly-named role) and every `gcloud compute firewall-rules list` succeeds, but `delete` returns `PERMISSION_DENIED`.
- Audit logs record a `v1.compute.firewalls.delete` entry with `status.code=7` and a `Required '<perm>' permission` message naming `compute.firewalls.delete`.
- `gcloud iam roles describe roles/compute.networkAdmin | grep firewalls` returns only `get`, `list`, `listEffectiveTags`, and `listTagBindings`.

The cleanest live check is `gcloud iam roles describe <role>` against the live IAM API. Role definitions are global, but the command resolves them against the same API the workload will hit, so the answer matches what the binding will produce at run time.

## Adoption Rule

When binding a predefined role to a service account, do not infer the permission set from the role name. Run `gcloud iam roles describe <role>` and read the `includedPermissions:` list. For grants narrower than a full predefined role, prefer `google_project_iam_custom_role` with the exact permissions required. The resource shape used here, paired `_custom_role` and `_member` blocks, is the precedent for future narrow grants in this repository.

The same trap appears elsewhere in the GCP role catalog:

- `roles/compute.networkUser` grants `use` on networks and subnetworks but not on firewalls.
- `roles/storage.objectAdmin` grants object-level mutation but not bucket-level mutation.
- `roles/iam.securityReviewer` grants read on IAM policies but no role-binding mutation.

For any predefined role whose name suggests a scope wider than the operation in question, the `includedPermissions:` list is the only authoritative reference.
