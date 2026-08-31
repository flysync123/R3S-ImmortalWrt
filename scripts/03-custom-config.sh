#!/bin/bash
# ==============================================================================
# sbwml-style Step 3: 生成 NanoPi R3S 目标硬件与插件编译配置 (.config)
# ==============================================================================

set -e

echo "=== [Step 3] 正在生成 NanoPi R3S LTS 专属 .config 配置 ==="

cat > .config <<EOF
# 目标硬件平台与架构：Rockchip RK3566 / ARMv8 / NanoPi R3S
CONFIG_TARGET_rockchip=y
CONFIG_TARGET_rockchip_armv8=y
CONFIG_TARGET_rockchip_armv8_DEVICE_friendlyarm_nanopi-r3s=y

# 根分区大小设置：4096MB (4GB)
CONFIG_TARGET_ROOTFS_PARTSIZE=4096

# LuCI 界面与基础中文语言包
CONFIG_PACKAGE_luci=y
CONFIG_PACKAGE_luci-i18n-base-zh-cn=y
CONFIG_PACKAGE_default-settings-chn=y
CONFIG_PACKAGE_autocore=y

# 代理与分流套件 (HomeProxy + sing-box)
CONFIG_PACKAGE_luci-app-homeproxy=y
CONFIG_PACKAGE_luci-i18n-homeproxy-zh-cn=y
CONFIG_PACKAGE_sing-box=y

# 1GB 内存抗 OOM 核心组件
CONFIG_PACKAGE_zram-swap=y

# 网络加速与内核模块 (TCP BBR / Flow Offload / TProxy / PCIe 网卡微码)
CONFIG_PACKAGE_kmod-tcp-bbr=y
CONFIG_PACKAGE_kmod-nft-offload=y
CONFIG_PACKAGE_kmod-nft-tproxy=y
CONFIG_PACKAGE_kmod-r8169=y
CONFIG_PACKAGE_r8169-firmware=y

# 硬件按键与系统调优
CONFIG_PACKAGE_kmod-gpio-button-hotplug=y
CONFIG_PACKAGE_luci-app-cpufreq=y
CONFIG_PACKAGE_luci-i18n-cpufreq-zh-cn=y

# 轻量流量统计 (nlbwmon)
CONFIG_PACKAGE_luci-app-nlbwmon=y
CONFIG_PACKAGE_luci-i18n-nlbwmon-zh-cn=y
CONFIG_PACKAGE_nlbwmon=y

# 实用终端工具与磁盘分区扩展工具
CONFIG_PACKAGE_htop=y
CONFIG_PACKAGE_curl=y
CONFIG_PACKAGE_fdisk=y
CONFIG_PACKAGE_e2fsprogs=y
CONFIG_PACKAGE_partx-utils=y
CONFIG_PACKAGE_zstd=y
EOF

# 运行 defconfig 自动补全所有子依赖与符号
make defconfig
echo ".config 生成完毕并已完成依赖展开。"
