#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 2: 软件包定制、工具链升级与系统参数 (DIY Part 2)
# 作用：升级 Go 1.25、清理冲突包、克隆独立插件、配置 IP/主机名/时区与注入 files/ 目录
# ==============================================================================

set -e

echo "=== [Customer Step 2] 正在进行工具链升级、依赖去重与系统级参数定制 ==="

# 1. 升级与替换 Golang 编译工具链至最新 25.x 分支（确保 sing-box / mosdns / nikki 编译兼容性，满足 go >= 1.25.5 依赖）
if [ -d "feeds/packages/lang/golang" ]; then
    echo "正在替换 Golang 编译环境为 25.x (Go 1.25+)..."
    rm -rf feeds/packages/lang/golang
    git clone --depth 1 https://github.com/sbwml/packages_lang_golang -b 25.x feeds/packages/lang/golang
fi

# 2. 清除官方基础源中的旧版/冲突包定义（避免与 passwall_packages / mosdns 源产生重复声明冲突）
echo "正在清理官方旧版冲突包定义..."
rm -rf feeds/luci/applications/luci-app-passwall 2>/dev/null || true
rm -rf feeds/luci/applications/luci-app-mosdns 2>/dev/null || true
rm -rf feeds/packages/net/sing-box 2>/dev/null || true
rm -rf feeds/packages/net/mosdns 2>/dev/null || true
rm -rf feeds/packages/net/v2ray-geodata 2>/dev/null || true

# 3. 克隆独立单包至 package/custom 目录
echo "正在拉取独立社区插件至 package/custom 目录..."
mkdir -p package/custom

# Argon 现代主题与配套配置插件
rm -rf package/custom/luci-theme-argon package/custom/luci-app-argon-config
git clone --depth 1 https://github.com/jerrykuku/luci-theme-argon.git package/custom/luci-theme-argon
git clone --depth 1 https://github.com/jerrykuku/luci-app-argon-config.git package/custom/luci-app-argon-config

# HomeProxy 代理分流客户端
rm -rf package/custom/luci-app-homeproxy
git clone --depth 1 https://github.com/immortalwrt/homeproxy.git package/custom/luci-app-homeproxy

# autocore-arm 与 default-settings (针对 Rockchip / ARMv8 深度调优)
rm -rf package/custom/autocore package/custom/default-settings
git clone --depth 1 https://github.com/sbwml/autocore-arm.git -b openwrt-25.12 package/custom/autocore
git clone --depth 1 https://github.com/sbwml/default-settings.git -b openwrt-25.12 package/custom/default-settings

# 4. 系统级配置微调 (LAN IP / 主机名 / 时区 / 默认主题 / 默认密码 password)
CONFIG_GEN="package/base-files/files/bin/config_generate"

if [ -f "$CONFIG_GEN" ]; then
    # 设置默认后台管理 IP 为 10.0.0.1 (防与光猫 192.168.1.1 产生冲突)
    sed -i 's/192.168.1.1/10.0.0.1/g' "$CONFIG_GEN"
    echo "✔ 默认 LAN IP 已设置为 10.0.0.1"

    # 设置默认主机名为 NanoPi-R3S
    sed -i 's/OpenWrt/NanoPi-R3S/g' "$CONFIG_GEN"
    sed -i 's/ImmortalWrt/NanoPi-R3S/g' "$CONFIG_GEN"
    echo "✔ 默认主机名已设置为 NanoPi-R3S"

    # 设置默认时区为中国上海 (Asia/Shanghai / CST-8)
    sed -i "s/'UTC'/'CST-8'\n\t\tset system.@system[-1].zonename='Asia\/Shanghai'/g" "$CONFIG_GEN"
    sed -i "s/'GMT0'/'CST-8'\n\t\tset system.@system[-1].zonename='Asia\/Shanghai'/g" "$CONFIG_GEN"
    echo "✔ 默认时区已设置为 Asia/Shanghai"
fi

# 设置默认 root 密码为 password ($1$V4UetPzk$CY6r64CJN8OzjmG6qwAbx.)
if [ -f "package/base-files/files/etc/shadow" ]; then
    sed -i 's#root:::0:99999:7:::#'root:\$1\$V4UetPzk\$CY6r64CJN8OzjmG6qwAbx.:0:99999:7:::'#g' package/base-files/files/etc/shadow 2>/dev/null || true
    sed -i 's#root:\*::0:99999:7:::#'root:\$1\$V4UetPzk\$CY6r64CJN8OzjmG6qwAbx.:0:99999:7:::'#g' package/base-files/files/etc/shadow 2>/dev/null || true
    echo "✔ 默认 root 密码已预设为 password"
fi

# 设置默认主题为 Argon
if [ -f "feeds/luci/collections/luci/Makefile" ]; then
    sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile 2>/dev/null || true
    echo "✔ 默认主题已配置为 Argon"
fi

# 5. 注入 custom files 覆盖层 (含 BBR / 7.5MB UDP 缓冲 / emmc-install 一键刷机 / 按键脚本)
if [ -d "$GITHUB_WORKSPACE/files" ]; then
    cp -r "$GITHUB_WORKSPACE/files" ./files
    echo "✔ 已成功注入 files/ 目录下的全栈优化与 emmc-install 刷机工具。"
fi

echo "=== [Customer Step 2] 软件包定制与参数调优完成 ==="
