#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 1: Feeds 源配置 (DIY Part 1)
# 作用：为官方原版 OpenWrt 注入高质量社区生态 Feeds 源
# ==============================================================================

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
. "$SCRIPT_DIR/00-dependencies.sh"

echo "=== [Customer Step 1] 正在配置扩展 Feeds 软件源 ==="

FEEDS_CONFIG=feeds.conf.default
if [ -f feeds.conf ]; then
    FEEDS_CONFIG=feeds.conf
fi
[ -f "$FEEDS_CONFIG" ] || { echo "ERROR: 未找到 OpenWrt feeds 配置。" >&2; exit 1; }

# 只清理同名源，不删除注释或其他源中偶然含有插件名称的内容。
sed -i -E '/^src-[^[:space:]]+[[:space:]]+(passwall_packages|passwall|nikki|mosdns)[[:space:]]/d' "$FEEDS_CONFIG"
FEEDS_TEMP=$(mktemp "${FEEDS_CONFIG}.XXXXXX")
trap 'rm -f "$FEEDS_TEMP"' EXIT
while IFS='|' read -r kind name url revision path; do
    [ "$kind" = feed ] || continue
    # OpenWrt scripts/feeds 使用 ^commit 固定提交；;branch 会随上游移动。
    printf 'src-git %s %s^%s\n' "$name" "$url" "$revision" >> "$FEEDS_TEMP"
done < <(customer_dependencies)
cat "$FEEDS_CONFIG" >> "$FEEDS_TEMP"
mv "$FEEDS_TEMP" "$FEEDS_CONFIG"

echo "✔ 已注入固定提交的 passwall_packages, passwall, nikki, mosdns 扩展源"

echo "=== [Customer Step 1] Feeds 配置完成 ==="
