#!/bin/bash
# ==============================================================================
# Customer OpenWrt Build System - Step 3: 硬件架构、内核加速与应用配置 (.config)
# 作用：定义 NanoPi R3S 目标机型、-O3 性能优化、现代代理生态与内核模块
# ==============================================================================

set -e

echo "=== [Customer Step 3] 正在生成 NanoPi R3S 专属定制 .config 配置文件 ==="

cat > .config <<EOF
# ------------------------------------------------------------------------------
# 1. 目标平台与芯片架构定义 (Rockchip RK3566 / ARMv8 / FriendlyARM NanoPi R3S)
# ------------------------------------------------------------------------------
CONFIG_TARGET_rockchip=y
CONFIG_TARGET_rockchip_armv8=y
CONFIG_TARGET_rockchip_armv8_DEVICE_friendlyarm_nanopi-r3s=y

# 根分区大小：4096MB (4GB)
CONFIG_TARGET_ROOTFS_PARTSIZE=4096

# ------------------------------------------------------------------------------
# 2. 编译器级性能压榨与极速链接器优化 (-O3 + Cortex-A55 硬件微架构优化 & Mold 极速链接)
# ------------------------------------------------------------------------------
CONFIG_DEVEL=y
CONFIG_OPTIMIZE_FLAG="-O3"
CONFIG_EXTRA_OPTIMIZATION="-mcpu=cortex-a55+crypto+crc -pipe"
CONFIG_USE_MOLD=y

# ------------------------------------------------------------------------------
# 3. Web UI 界面、Argon 现代主题与中文化组件
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_luci=y
CONFIG_PACKAGE_luci-theme-argon=y
CONFIG_PACKAGE_luci-app-argon-config=y
CONFIG_PACKAGE_luci-i18n-base-zh-cn=y
CONFIG_PACKAGE_luci-i18n-argon-config-zh-cn=y
CONFIG_LUCI_LANG_zh_Hans=y
CONFIG_PACKAGE_default-settings=y
CONFIG_PACKAGE_autocore-arm=y

# ------------------------------------------------------------------------------
# 4. 现代代理分流、DNS 加速与打洞组件生态
# ------------------------------------------------------------------------------
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
CONFIG_PACKAGE_luci-app-wireguard=y
CONFIG_PACKAGE_luci-i18n-wireguard-zh-cn=y
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
CONFIG_PACKAGE_kmod-bpf=y
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

# ------------------------------------------------------------------------------
# 10. 显式屏蔽与剔除内存大户 (严禁在 1GB 内存设备上装载)
# ------------------------------------------------------------------------------
CONFIG_PACKAGE_luci-app-openclash=n
CONFIG_PACKAGE_irqbalance=n
CONFIG_PACKAGE_docker=n
CONFIG_PACKAGE_dockerd=n
EOF

# 自动补全所有依赖并验证
make defconfig
echo "✔ [Customer] 全套 .config 配置生成并依赖展开完毕。"
