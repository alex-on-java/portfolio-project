#!/usr/bin/env bash
set -Eeuo pipefail
# shellcheck disable=SC2154  # shellcheck can't see variables in string; this is an exceptional case, suppressing any linter check is a last resort, and must always be explicitly allowed by a human
trap 'pcs=("${PIPESTATUS[@]}" "$?"); rc=${pcs[-1]}; unset "pcs[-1]"; cmd=$BASH_COMMAND; file="${BASH_SOURCE[0]}"; ((${#BASH_SOURCE[@]} > 1)) && file="${BASH_SOURCE[1]}"; line="${BASH_LINENO[0]}"; [[ $line -eq 0 ]] && line="$LINENO"; printf "ERROR %d at %s:%s: %s  PIPESTATUS=%s\n" "$rc" "$file" "$line" "$cmd" "${pcs[*]}" >&2' ERR

readonly WORKTREES_DIR="pp-worktrees"

error() { printf 'Error: %s\n' "$*" >&2; }
warn()  { printf 'Warning: %s\n' "$*" >&2; }
info()  { printf '%s\n' "$*"; }

usage() {
    cat <<'EOF'
Usage: create-worktree.sh <command> [options]

Commands:
    add <branch>       Create a worktree for the branch
    remove <branch>    Remove worktree for the branch
    list-ignored       List ignored/excluded items that exist on disk

Options:
    -h, --help         Show this help message
EOF
}

get_main_repo_root() {
    local git_common_dir
    git_common_dir=$(git rev-parse --git-common-dir 2>/dev/null) || return 1

    if [[ "$git_common_dir" == ".git" ]]; then
        git rev-parse --show-toplevel
    else
        dirname "$git_common_dir"
    fi
}

sanitize_branch_name() {
    echo "${1//\//-}"
}

get_worktrees_parent() {
    local repo_root="$1"
    local parent_dir
    parent_dir=$(dirname "$repo_root")
    echo "$parent_dir/$WORKTREES_DIR"
}

get_exclude_paths() {
    local main_repo="$1"
    local exclude_file="$main_repo/.git/info/exclude"

    [[ -f "$exclude_file" ]] || return 0

    while IFS= read -r line; do
        [[ -z "$line" || "$line" == \#* ]] && continue
        line="${line%/}"
        if [[ "$line" == *[\*\?\[]* ]]; then
            warn "Skipping glob pattern in exclude: $line"
            continue
        fi
        printf '%s\n' "$line"
    done < "$exclude_file"
}

sync_excluded() {
    local main_repo="$1"
    local worktree_path="$2"

    while IFS= read -r entry; do
        [[ -z "$entry" ]] && continue

        local src="$main_repo/$entry"
        local dst="$worktree_path/$entry"

        [[ -e "$src" ]] || continue
        [[ -e "$dst" || -L "$dst" ]] && continue

        mkdir -p "$(dirname "$dst")"

        if [[ -d "$src" ]]; then
            ln -s "$src" "$dst"
            info "Synced (symlink): $entry/" >&2
        else
            ln "$src" "$dst"
            info "Synced (hardlink): $entry" >&2
        fi
    done < <(get_exclude_paths "$main_repo")
}

cmd_add() {
    local branch="${1:-}"

    if [[ -z "$branch" ]]; then
        error "Branch name required"
        echo "Usage: create-worktree.sh add <branch>"
        return 1
    fi

    local main_repo
    main_repo=$(get_main_repo_root) || { error "Not inside a git repository"; return 1; }

    local sanitized_branch
    sanitized_branch=$(sanitize_branch_name "$branch")

    local worktrees_parent
    worktrees_parent=$(get_worktrees_parent "$main_repo")

    local worktree_path="$worktrees_parent/${sanitized_branch}"

    mkdir -p "$worktrees_parent"

    if [[ -e "$worktree_path" ]]; then
        error "Destination already exists: $worktree_path"
        return 1
    fi

    local current_branch
    current_branch=$(git -C "$main_repo" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
    if [[ "$branch" == "$current_branch" ]]; then
        error "Branch '$branch' is already checked out in the main worktree"
        return 1
    fi

    if git -C "$main_repo" worktree list | grep -qF "[$branch]"; then
        error "Branch '$branch' is already checked out in another worktree"
        return 1
    fi

    if git -C "$main_repo" show-ref --verify --quiet "refs/heads/$branch"; then
        git -C "$main_repo" worktree add "$worktree_path" "$branch" \
            || { error "git worktree add failed"; return 1; }
    elif git -C "$main_repo" show-ref --verify --quiet "refs/remotes/origin/$branch"; then
        git -C "$main_repo" worktree add --track -b "$branch" "$worktree_path" "origin/$branch" \
            || { error "git worktree add (tracking remote) failed"; return 1; }
    else
        git -C "$main_repo" worktree add -b "$branch" "$worktree_path" \
            || { error "git worktree add -b failed"; return 1; }
    fi

    sync_excluded "$main_repo" "$worktree_path"

    echo "$worktree_path"
}

cmd_remove() {
    local branch="${1:-}"

    if [[ -z "$branch" ]]; then
        error "Branch name required"
        echo "Usage: create-worktree.sh remove <branch>"
        return 1
    fi

    local main_repo
    main_repo=$(get_main_repo_root) || { error "Not inside a git repository"; return 1; }

    local sanitized_branch
    sanitized_branch=$(sanitize_branch_name "$branch")

    local worktrees_parent
    worktrees_parent=$(get_worktrees_parent "$main_repo")

    local worktree_path="$worktrees_parent/${sanitized_branch}"

    if [[ ! -d "$worktree_path" ]]; then
        error "Worktree not found: $worktree_path"
        return 1
    fi

    local current_dir
    current_dir=$(pwd)
    if [[ "$current_dir" == "$worktree_path" || "$current_dir" == "$worktree_path/"* ]]; then
        error "Cannot remove worktree while inside it"
        return 1
    fi

    if ! git -C "$worktree_path" diff --quiet HEAD 2>/dev/null || \
       ! git -C "$worktree_path" diff --cached --quiet HEAD 2>/dev/null; then
        warn "Worktree has uncommitted changes:"
        git -C "$worktree_path" status --short >&2
    fi

    trash "$worktree_path"
    git -C "$main_repo" worktree prune

    info "Worktree removed: $worktree_path"

    if git -C "$main_repo" branch -d "$branch" 2>/dev/null; then
        info "Branch '$branch' deleted (fully merged)"
    else
        warn "Branch '$branch' not deleted (not fully merged). Force-delete with: git branch -D $branch"
    fi
}

cmd_list_ignored() {
    local main_repo
    main_repo=$(get_main_repo_root) || { error "Not inside a git repository"; return 1; }

    local -A seen_dirs=()
    local -A exclude_set=()
    while IFS= read -r entry; do
        [[ -n "$entry" ]] && exclude_set["$entry"]=1
    done < <(get_exclude_paths "$main_repo")

    while IFS= read -r item; do
        item="${item%/}"
        [[ -z "$item" ]] && continue

        if [[ -n "${exclude_set[$item]+x}" ]]; then
            [[ -d "$main_repo/$item" ]] && seen_dirs["$item"]=1
            continue
        fi
        local excluded_parent=false
        local excl_check="$item"
        while [[ "$excl_check" == */* ]]; do
            excl_check="${excl_check%/*}"
            if [[ -n "${exclude_set[$excl_check]+x}" ]]; then
                excluded_parent=true
                break
            fi
        done
        $excluded_parent && continue

        local skip=false
        local check_path="$item"
        while [[ "$check_path" == */* ]]; do
            check_path="${check_path%/*}"
            if [[ -n "${seen_dirs[$check_path]+x}" ]]; then
                skip=true
                break
            fi
        done
        $skip && continue

        local full_path="$main_repo/$item"
        local item_type="file"
        if [[ -d "$full_path" ]]; then
            item_type="dir"
            seen_dirs["$item"]=1
        fi

        local source_file="unknown"
        local check_output
        if check_output=$(git -C "$main_repo" check-ignore -v -- "$item" 2>/dev/null); then
            source_file=$(echo "$check_output" | cut -d: -f1)
            source_file="${source_file#"$main_repo/"}"
        fi

        printf '%s\t%s\t%s\n' "$item_type" "$item" "$source_file"
    done < <(git -C "$main_repo" ls-files --others --ignored --exclude-standard --directory 2>/dev/null | sort)
}

main() {
    if [[ $# -eq 0 ]]; then
        usage
        exit 1
    fi

    local command="$1"
    shift

    case "$command" in
        add)        cmd_add "${1:-}" ;;
        remove)     cmd_remove "${1:-}" ;;
        list-ignored) cmd_list_ignored ;;
        -h|--help)  usage ;;
        *)
            error "Unknown command: $command"
            usage
            exit 1
            ;;
    esac
}

main "$@"
