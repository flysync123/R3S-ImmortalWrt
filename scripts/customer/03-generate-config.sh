#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 3: 硬件架构、内核加速与应用配置 (.config)
# 作用：定义 NanoPi R3S 目标机型、代理应用与内核模块，并检查依赖解析结果
# ==============================================================================

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
TARGET=${TARGET:-rockchip}
SUBTARGET=${SUBTARGET:-armv8}
PROFILE=${PROFILE:-friendlyarm_nanopi-r3s}
ROOTFS_PARTSIZE=${ROOTFS_PARTSIZE:-4096}
BUILD_MODE=${BUILD_MODE:-full}
case "$BUILD_MODE" in
    full|lite) ;;
    *) echo "ERROR: BUILD_MODE 必须为 full 或 lite。" >&2; exit 1 ;;
esac
for value in "$TARGET" "$SUBTARGET" "$PROFILE"; do
    [[ "$value" =~ ^[a-zA-Z0-9_-]+$ ]] || { echo "ERROR: 非法目标配置: $value" >&2; exit 1; }
done
[[ "$ROOTFS_PARTSIZE" =~ ^[0-9]+$ ]] && [ "$ROOTFS_PARTSIZE" -ge 128 ] || {
    echo "ERROR: ROOTFS_PARTSIZE 必须是至少 128 MiB 的整数。" >&2
    exit 1
}

echo "=== [Customer Step 3] 正在生成 NanoPi R3S 专属定制 .config 配置文件 ==="

cat > .config <<EOF
# ------------------------------------------------------------------------------
# 1. 目标平台与芯片架构定义 (Rockchip RK3566 / ARMv8 / FriendlyARM NanoPi R3S)
# ------------------------------------------------------------------------------
CONFIG_TARGET_${TARGET}=y
CONFIG_TARGET_${TARGET}_${SUBTARGET}=y
CONFIG_TARGET_${TARGET}_${SUBTARGET}_DEVICE_${PROFILE}=y

# 根分区大小（MiB，由 ROOTFS_PARTSIZE 配置，默认 4096）
CONFIG_TARGET_ROOTFS_PARTSIZE=${ROOTFS_PARTSIZE}

# ------------------------------------------------------------------------------
# 2. 现代链接器优化 (Mold 极速链接)
# ------------------------------------------------------------------------------
CONFIG_DEVEL=y
CONFIG_USE_MOLD=y
CONFIG_CCACHE=y

# ------------------------------------------------------------------------------
# 3. Web UI 界面、Argon 现代主题与中文化组件
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_luci=y
CONFIG_PACKAGE_luci-theme-argon=y
CONFIG_PACKAGE_luci-app-argon-config=y
CONFIG_PACKAGE_luci-i18n-base-zh-cn=y
CONFIG_PACKAGE_luci-i18n-argon-config-zh-cn=y
CONFIG_LUCI_LANG_zh_Hans=y
CONFIG_PACKAGE_autocore-arm=y

# ------------------------------------------------------------------------------
# 4. 现代代理分流、DNS 加速与打洞组件生态
# ------------------------------------------------------------------------------
# 解决 PassWall 依赖与基础 dnsmasq 冲突
CONFIG_PACKAGE_dnsmasq=n
CONFIG_PACKAGE_dnsmasq-full=y

# HomeProxy + sing-box 核心
CONFIG_PACKAGE_luci-app-homeproxy=y
CONFIG_PACKAGE_luci-i18n-homeproxy-zh-cn=y
CONFIG_PACKAGE_sing-box=y

# Nikki 现代客户端 (Mihomo 内核)
CONFIG_PACKAGE_luci-app-nikki=y
CONFIG_PACKAGE_luci-i18n-nikki-zh-cn=y
CONFIG_PACKAGE_nikki=y
CONFIG_PACKAGE_mihomo-meta=y

# PassWall 套件
CONFIG_PACKAGE_luci-app-passwall=y
CONFIG_PACKAGE_luci-i18n-passwall-zh-cn=y

# MosDNS 分流解析加速与地理规则库
CONFIG_PACKAGE_luci-app-mosdns=y
CONFIG_PACKAGE_luci-i18n-mosdns-zh-cn=y
CONFIG_PACKAGE_mosdns=y
CONFIG_PACKAGE_v2ray-geoip=y
CONFIG_PACKAGE_v2ray-geosite=y
CONFIG_PACKAGE_geo2txt=y
CONFIG_PACKAGE_ucode-mod-digest=y
CONFIG_PACKAGE_yq=y

# NATMap 全锥型 STUN 打洞穿透
CONFIG_PACKAGE_luci-app-natmap=y
CONFIG_PACKAGE_luci-i18n-natmap-zh-cn=y

# WireGuard 安全隧道
CONFIG_PACKAGE_luci-proto-wireguard=y
CONFIG_PACKAGE_kmod-wireguard=y

# ------------------------------------------------------------------------------
# 5. 1GB 内存抗 OOM 核心防护机制
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_zram-swap=y

# ------------------------------------------------------------------------------
# 6. 内核加速、eBPF 与网络驱动模块 (BBR / Flow Offload / TProxy / PCIe 网卡微码)
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_kmod-tcp-bbr=y
CONFIG_PACKAGE_kmod-nft-offload=y
CONFIG_PACKAGE_kmod-nft-tproxy=y
CONFIG_PACKAGE_kmod-nft-socket=y
CONFIG_PACKAGE_kmod-tun=y
CONFIG_PACKAGE_kmod-dummy=y
CONFIG_PACKAGE_kmod-inet-diag=y
# OpenWrt 6.12 内核已内置 BPF；该版本没有独立的 kmod-bpf 软件包。
CONFIG_PACKAGE_kmod-r8169=y
CONFIG_PACKAGE_r8169-firmware=y

# ------------------------------------------------------------------------------
# 7. 硬件按键与算力跑分
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_kmod-gpio-button-hotplug=y
CONFIG_PACKAGE_coremark=y

# ------------------------------------------------------------------------------
# 8. 轻量设备流量统计 (nlbwmon) 与 Web 终端 (ttyd)
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_luci-app-nlbwmon=y
CONFIG_PACKAGE_luci-i18n-nlbwmon-zh-cn=y
CONFIG_PACKAGE_nlbwmon=y
CONFIG_PACKAGE_luci-app-ttyd=y
CONFIG_PACKAGE_luci-i18n-ttyd-zh-cn=y
CONFIG_PACKAGE_ttyd=y

# ------------------------------------------------------------------------------
# 9. SSL 安全证书、终端工具与分区工具
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_ca-bundle=y
CONFIG_PACKAGE_ca-certificates=y
CONFIG_PACKAGE_libustream-openssl=y
CONFIG_PACKAGE_openssl-util=y
CONFIG_PACKAGE_htop=y
CONFIG_PACKAGE_curl=y
CONFIG_PACKAGE_fdisk=y
CONFIG_PACKAGE_e2fsprogs=y
CONFIG_PACKAGE_partx-utils=y
CONFIG_PACKAGE_zstd=y
CONFIG_PACKAGE_fwtool=y
CONFIG_PACKAGE_jsonfilter=y

# ------------------------------------------------------------------------------
# 10. 显式屏蔽与剔除内存大户 (严禁在 1GB 内存设备上装载)
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_luci-app-openclash=n
CONFIG_PACKAGE_irqbalance=n
CONFIG_PACKAGE_docker=n
CONFIG_PACKAGE_dockerd=n
EOF

if [[ "$BUILD_MODE" == lite ]]; then
    # PassWall defaults select sslocal; disable both the selectors and all variants.
    cat >> .config <<'EOF'
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Shadowsocks_Rust_Client=n
CONFIG_PACKAGE_luci-app-passwall_INCLUDE_Shadowsocks_Rust_Server=n
CONFIG_PACKAGE_shadowsocks-rust-sslocal=n
CONFIG_PACKAGE_shadowsocks-rust-ssserver=n
CONFIG_PACKAGE_shadowsocks-rust-ssmanager=n
CONFIG_PACKAGE_shadowsocks-rust-ssservice=n
CONFIG_PACKAGE_shadowsocks-rust-ssurl=n
EOF
fi

# 自动补全所有依赖，并在未知包、依赖冲突或目标不支持时立即报错。
cp .config .config.requested
make defconfig RECURSIVE_DEP_IS_ERROR=1
bash "$SCRIPT_DIR/../build/check-config.sh" .config.requested .config
if [[ "$BUILD_MODE" == lite ]] && grep -Eq '^CONFIG_PACKAGE_(shadowsocks-rust-[^=]+|luci-app-passwall_INCLUDE_Shadowsocks_Rust_(Client|Server))=[ym]$' .config; then
    echo "ERROR: 精简模式仍选中了 Rust Shadowsocks，请检查上游依赖。" >&2
    exit 1
fi
echo "✔ [Customer] $BUILD_MODE 模式 .config 配置生成并依赖展开完毕。"
