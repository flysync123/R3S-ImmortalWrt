#!/usr/bin/env bash
# Resolve existing branch/tag names first; accept common release-version inputs.
# Stdout is only the resolved name, suitable for GITHUB_ENV or git clone --branch.
set -euo pipefail

repository=${1:?Usage: resolve-ref.sh repository branch-or-version}
requested=${2:?Usage: resolve-ref.sh repository branch-or-version}
git check-ref-format "refs/heads/$requested" >/dev/null 2>&1 || {
    echo '::error::版本或分支名称格式无效，请使用 v25.12.2 或 openwrt-25.12 这样的名称。' >&2
    exit 1
}

ref_exists() {
    local name=$1 status
    if git ls-remote --refs --exit-code "$repository" "refs/heads/$name" "refs/tags/$name" >/dev/null; then
        return 0
    else
        status=$?
        if [[ "$status" == 2 ]]; then
            return 1
        fi
        echo '::error::无法读取上游引用，请检查仓库地址、访问权限或网络连接。' >&2
        exit "$status"
    fi
}

if ref_exists "$requested"; then
    printf '%s\n' "$requested"
    exit 0
fi

version=${requested#openwrt-}
if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-rc[0-9]+)?$ ]]; then
    candidate="v$version"
    if ref_exists "$candidate"; then
        printf '::notice::将版本输入 %s 规范为上游标签 %s。\n' "$requested" "$candidate" >&2
        printf '%s\n' "$candidate"
        exit 0
    fi
fi

printf '::error::上游不存在引用 %s。稳定版应使用 v<版本号>，系列分支使用 openwrt-<主版本.次版本>；请确认上游确有该版本。\n' "$requested" >&2
exit 1
