#!/bin/bash
# Customer third-party source lock. Revisions checked against public Git refs on
# 2026-10-15; a revision lock alone does not certify a complete firmware build.
# Format: kind|name|repository|commit|build-tree path

customer_dependencies() {
    cat <<'EOF'
feed|passwall_packages|https://github.com/Openwrt-Passwall/openwrt-passwall-packages.git|1af0a5c4fb3a227201683b64d32f61c65db9be72|feeds/passwall_packages
feed|passwall|https://github.com/Openwrt-Passwall/openwrt-passwall.git|356dc9c4111daf602cc3ec852f6fbaabd194a16b|feeds/passwall
feed|nikki|https://github.com/nikkinikki-org/OpenWrt-nikki.git|78e1a751d55ed0762811f054ee699049473da7b8|feeds/nikki
feed|mosdns|https://github.com/sbwml/luci-app-mosdns.git|bd40245303cd0ba56804d49eed5dbc4be2a082ca|feeds/mosdns
package|luci-theme-argon|https://github.com/jerrykuku/luci-theme-argon.git|c4a8b4eadcd17cad348a1312954a4852c21395f6|package/custom/luci-theme-argon
package|luci-app-argon-config|https://github.com/jerrykuku/luci-app-argon-config.git|445af53fbee6e00fa6efc0ae33f8b2854df65500|package/custom/luci-app-argon-config
package|homeproxy|https://github.com/immortalwrt/homeproxy.git|98a6ad9e71484528008ff435694fd107591f3a1d|package/custom/luci-app-homeproxy
package|autocore|https://github.com/sbwml/autocore-arm.git|9b52f345ee2db331ce2fefcdcc50a9d6120c11a3|package/custom/autocore
toolchain|golang|https://github.com/sbwml/packages_lang_golang.git|dba928c4f25b3290090d5937fcc6271f01a2ec91|feeds/packages/lang/golang
EOF
}

customer_find_dependency() {
    customer_dependencies | awk -F '|' -v name="$1" '$2 == name { print; found=1; exit } END { if (!found) exit 1 }'
}

customer_record_dependency() {
    local entry kind name url revision path actual
    entry=$(customer_find_dependency "$1") || return 1
    IFS='|' read -r kind name url revision path <<< "$entry"
    actual=$(git -C "$path" rev-parse HEAD) || return 1
    if [ "$actual" != "$revision" ]; then
        echo "ERROR: $name expected $revision, found $actual. Re-run the locked feed update." >&2
        return 1
    fi
    printf '%s\t%s\t%s\n' "$name" "$url" "$actual" >> customer-dependencies.tsv
}

customer_clone_dependency() {
    local entry kind name url revision path
    entry=$(customer_find_dependency "$1") || return 1
    IFS='|' read -r kind name url revision path <<< "$entry"
    git clone --depth 1 --no-checkout "$url" "$path" || return 1
    git -C "$path" fetch --depth 1 origin "$revision" || return 1
    git -C "$path" -c advice.detachedHead=false checkout --detach "$revision" || return 1
    customer_record_dependency "$name"
}
