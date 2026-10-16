#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 2: 软件包定制、工具链升级与系统参数 (DIY Part 2)
# 作用：固定现代 Go 工具链、清理冲突包、按固定提交克隆插件与注入 files/ 目录
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

# 1. 保留已验证的官方 Go 1.27.2，供 sing-box、Mihomo、MosDNS 等使用。
# 源码克隆在 package/ 与 feeds/ 扫描范围之外，只复制 lang/golang 子树。
build_root=$(pwd -P)
for owned_path in customer-sources/golang feeds/packages/lang/golang package/feeds/packages; do
    if [ "$(readlink -m -- "$owned_path")" != "$build_root/$owned_path" ]; then
        echo "ERROR: Refusing unexpected symlink path: $owned_path" >&2
        exit 1
    fi
done
[ -d feeds/packages/lang ] || { echo "ERROR: Missing feeds/packages/lang." >&2; exit 1; }
if [ -e feeds/packages/lang/golang ] && [ ! -d feeds/packages/lang/golang ]; then
    echo "ERROR: feeds/packages/lang/golang is not a directory." >&2
    exit 1
fi

# 先验证所有已安装 Go 包链接，再执行删除；保留用户实体目录和指向其他源的链接。
golang_links=()
for installed in package/feeds/packages/golang*; do
    [ -e "$installed" ] || [ -L "$installed" ] || continue
    if [ ! -L "$installed" ]; then
        echo "ERROR: $installed is not a feed symlink." >&2
        exit 1
    fi
    case "$(readlink -m -- "$installed")" in
        "$build_root/feeds/packages/lang/golang/"*) golang_links+=("$installed") ;;
        *) echo "ERROR: $installed points outside the Go feed subtree." >&2; exit 1 ;;
    esac
done

mkdir -p customer-sources
rm -rf -- "$build_root/customer-sources/golang"
customer_clone_dependency golang
golang_source=customer-sources/golang/lang/golang
for required in golang-version.mk golang-values.mk golang-package.mk golang-host-build.mk \
    golang-compiler.mk golang-build.sh go-gcc-helper go-strip-helper \
    golang-bootstrap/Makefile golang-bootstrap/Config.in golang/Makefile golang1.27/Makefile; do
    [ -f "$golang_source/$required" ] || {
        echo "ERROR: Missing modern Go toolchain file: $golang_source/$required" >&2
        exit 1
    }
done
if ! grep -Eq '^GO_DEFAULT_VERSION[[:space:]]*:=[[:space:]]*1\.27[[:space:]]*$' "$golang_source/golang-values.mk" ||
   ! grep -Eq '^PKG_NAME[[:space:]]*:=[[:space:]]*golang1\.27[[:space:]]*$' "$golang_source/golang1.27/Makefile" ||
   ! grep -Eq '^GO_VERSION_MAJOR_MINOR[[:space:]]*:=[[:space:]]*1\.27[[:space:]]*$' "$golang_source/golang1.27/Makefile" ||
   ! grep -Eq '^GO_VERSION_PATCH[[:space:]]*:=[[:space:]]*2[[:space:]]*$' "$golang_source/golang1.27/Makefile"; then
    echo "ERROR: Locked Go toolchain must provide default Go 1.27.2." >&2
    exit 1
fi

if [ "${#golang_links[@]}" -gt 0 ]; then
    rm -f -- "${golang_links[@]}"
fi
rm -rf -- "$build_root/feeds/packages/lang/golang"
mkdir -p feeds/packages/lang/golang
cp -R "$golang_source/." feeds/packages/lang/golang/
echo "✔ 已固定官方 Go 1.27.2 工具链及现代 bootstrap/helper 布局。"

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
