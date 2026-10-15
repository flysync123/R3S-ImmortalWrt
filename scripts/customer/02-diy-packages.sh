#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 2: 软件包定制、工具链升级与系统参数 (DIY Part 2)
# 作用：智能适配 Go 工具链、清理冲突包、按固定提交克隆插件与注入 files/ 目录
# ==============================================================================

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
. "$SCRIPT_DIR/00-dependencies.sh"

printf 'name\trepository\tcommit\n' > customer-dependencies.tsv
while IFS='|' read -r kind name url revision path; do
    [ "$kind" = feed ] || continue
    customer_record_dependency "$name"
done < <(customer_dependencies)

echo "=== [Customer Step 2] 正在进行工具链升级、依赖去重与系统级参数定制 ==="

# Nikki 固定使用稳定版 Mihomo；缺少定义时停止，避免误删后继续构建。
if [ ! -f "feeds/nikki/mihomo-meta/Makefile" ]; then
    echo "ERROR: Missing feeds/nikki/mihomo-meta/Makefile. Re-run the locked feed update." >&2
    exit 1
fi

# 1. 检查并适配 Golang 编译工具链
# 关键原理：OpenWrt 25.12+ 官方源已内置现代化 Go 1.26+ 工具链 (golang1.26/golang-bootstrap/golang-version.mk)
#           若强制使用旧结构仓库覆盖，会导致 feeds 索引损坏并缺失 golang-version.mk 从而造成编译失败。
#           因此：当检测到官方 25.12+ 现代 Go 工具链时保持原生；仅当为旧版 OpenWrt (24.10及以前) 时才升级。
if [ -d "feeds/packages/lang/golang/golang1.27" ] || [ -d "feeds/packages/lang/golang/golang1.26" ] || [ -d "feeds/packages/lang/golang/golang1.25" ] || [ -f "feeds/packages/lang/golang/golang-version.mk" ]; then
    echo "✔ 检测到当前 OpenWrt 已内置现代 Golang 工具链，保持原生结构以确保编译通过。"
elif [ -d "feeds/packages/lang/golang" ]; then
    echo "正在为旧版环境升级 Golang 编译环境至 26.x..."
    rm -rf feeds/packages/lang/golang
    customer_clone_dependency golang
fi

# 2. 清除官方基础源中的旧版/冲突包定义（避免与 passwall_packages / mosdns 源产生重复声明冲突）
echo "正在清理官方旧版冲突包定义..."
rm -rf feeds/luci/applications/luci-app-passwall 2>/dev/null || true
rm -rf feeds/luci/applications/luci-app-mosdns 2>/dev/null || true
rm -rf feeds/packages/net/sing-box 2>/dev/null || true
rm -rf feeds/packages/net/mosdns 2>/dev/null || true
rm -rf feeds/packages/net/v2ray-geodata 2>/dev/null || true
# 两个 Mihomo 定义的双向 CONFLICTS 会在 OpenWrt 25.12 生成循环 Kconfig 依赖。
# 只保留 meta 的包定义，并清除重复执行时可能残留的 alpha 安装链接。
if [ -L "package/feeds/nikki/mihomo-alpha" ]; then
    rm -f package/feeds/nikki/mihomo-alpha
elif [ -e "package/feeds/nikki/mihomo-alpha" ]; then
    echo "ERROR: package/feeds/nikki/mihomo-alpha is not a feed symlink." >&2
    exit 1
fi
rm -rf feeds/nikki/mihomo-alpha
./scripts/feeds update -i packages luci nikki

# 3. 克隆独立单包至 package/custom 目录
echo "正在拉取独立社区插件至 package/custom 目录..."
mkdir -p package/custom

# Argon 现代主题与配套配置插件
rm -rf package/custom/luci-theme-argon package/custom/luci-app-argon-config
customer_clone_dependency luci-theme-argon
customer_clone_dependency luci-app-argon-config

# HomeProxy 代理分流客户端
rm -rf package/custom/luci-app-homeproxy
customer_clone_dependency homeproxy

# autocore-arm (针对 Rockchip / ARMv8 状态显示与温度监控深度调优)
rm -rf package/custom/autocore package/custom/default-settings
customer_clone_dependency autocore

# 4. 仅调整默认主题。网络、主机名与时区由首次初始化脚本处理，保留升级配置。
# 不修改上游 shadow，也不写入公共默认密码或 CPU governor。

# 设置默认主题为 Argon
if [ -f "feeds/luci/collections/luci/Makefile" ]; then
    sed -i 's/luci-theme-bootstrap/luci-theme-argon/g' feeds/luci/collections/luci/Makefile 2>/dev/null || true
    echo "✔ 默认主题已配置为 Argon"
fi

# 5. 注入 custom files 覆盖层 (含 BBR / 7.5MB UDP 缓冲 / emmc-install 一键刷机 / 按键脚本)
if [ -n "${GITHUB_WORKSPACE:-}" ] && [ -d "$GITHUB_WORKSPACE/files" ]; then
    mkdir -p files
    cp -rf "$GITHUB_WORKSPACE/files/." files/
    echo "✔ 已成功注入 files/ 目录下的全栈优化与 emmc-install 刷机工具。"
fi

echo "=== [Customer Step 2] 软件包定制与参数调优完成 ==="
