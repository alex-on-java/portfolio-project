#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

# explicit-context-guard.sh — PreToolUse hook for Bash.
# Blocks commands that mutate implicit infrastructure targeting defaults.
# Enforces the "Explicit Context" principle: always specify --context, -chdir=, etc.
#
# Input:  JSON on stdin (PreToolUse payload with tool_input.command)
# Output: JSON with permissionDecision: deny (to override allow from other hooks)

input=$(cat)

command_str=$(echo "$input" | jq -r '.tool_input.command // ""')

# deny_with_reason outputs JSON that Claude Code treats as a formal deny decision.
# This ensures deny-first precedence wins even when another hook returns allow.
deny_with_reason() {
  local reason="$1"
  jq -n --arg reason "$reason" '{
    "hookSpecificOutput": {
      "hookEventName": "PreToolUse",
      "permissionDecision": "deny",
      "permissionDecisionReason": $reason
    }
  }'
  exit 0
}

# --- 1. Kubernetes context switching ---

if echo "$command_str" | grep -qiE 'kubectl\s.*config\s.*use-context'; then
  deny_with_reason "BLOCKED: kubectl config use-context mutates the implicit kube context. Use \`kubectl --context <name>\` on each command instead. This applies to scripts too — pass --context explicitly, never switch the default."
fi

if echo "$command_str" | grep -qiE 'kubectl\s.*config\s.*set-context' && echo "$command_str" | grep -qi -- '--current'; then
  deny_with_reason "BLOCKED: kubectl config set-context --current modifies the active context in-place. Specify the context name explicitly: \`kubectl config set-context <name> ...\`"
fi

if echo "$command_str" | grep -qiE '(^|\s|;|&&|\|)kubectx(\s|$|;)'; then
  deny_with_reason "BLOCKED: kubectx switches the implicit kube context. Use \`kubectl --context <name>\` on each command instead."
fi

# --- 2. Docker context switching ---

if echo "$command_str" | grep -qiE 'docker\s.*context\s.*use\b'; then
  deny_with_reason "BLOCKED: docker context use switches the implicit Docker daemon target. Use \`docker --context <name>\` per command or set \`DOCKER_HOST=\` instead."
fi

# --- 3. Terraform workspace switching ---

if echo "$command_str" | grep -qiE 'terraform\s.*workspace\s.*select'; then
  deny_with_reason "BLOCKED: terraform workspace select switches the implicit Terraform workspace. Use \`terraform -chdir=<path>\` to target the correct root directory instead."
fi

# --- 4. Destructive cluster operations (bypass of ordered teardown) ---

if echo "$command_str" | grep -qiE 'kind\s.*delete\s.*cluster'; then
  deny_with_reason "BLOCKED: kind delete cluster bypasses ordered teardown and orphans Terraform state. Use \`nx run platform:destroy-local\` or \`platform/scripts/destroy-local.sh\` instead."
fi

exit 0
