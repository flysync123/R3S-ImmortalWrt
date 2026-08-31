#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 1: Feeds 源配置 (DIY Part 1)
# 作用：为官方原版 OpenWrt 注入高质量社区生态 Feeds 源
# ==============================================================================

set -e

echo "=== [Customer Step 1] 正在配置扩展 Feeds 软件源 ==="

if [ -f "feeds.conf.default" ]; then
    # 清理已有的同名配置项
    sed -i '/passwall_packages/d; /passwall/d; /nikki/d; /mosdns/d' feeds.conf.default

    # 注入高质量网络与代理分流生态源（置于顶部以确保优先检索）
    sed -i '1i src-git mosdns https://github.com/sbwml/luci-app-mosdns.git;v5' feeds.conf.default
    sed -i '1i src-git nikki https://github.com/nikkinikki-org/OpenWrt-nikki.git;main' feeds.conf.default
    sed -i '1i src-git passwall https://github.com/Openwrt-Passwall/openwrt-passwall.git;main' feeds.conf.default
    sed -i '1i src-git passwall_packages https://github.com/Openwrt-Passwall/openwrt-passwall-packages.git;main' feeds.conf.default

    echo "✔ 已成功注入 passwall_packages, passwall, nikki, mosdns 扩展源"
fi

echo "=== [Customer Step 1] Feeds 配置完成 ==="
