#!/bin/bash
# ==============================================================================
# sbwml-style Step 2: 软件包与系统参数微调
# 作用：在 ./scripts/feeds install 之后执行，用于修改默认主题、默认 IP、编译优化选项
# ==============================================================================

set -e

echo "=== [Step 2] 正在微调软件包与默认配置 ==="

# 1. 设置默认登录后台 IP 为 10.0.0.1 (防与光猫 192.168.1.1 冲突)
if [ -f "package/base-files/files/bin/config_generate" ]; then
    sed -i 's/192.168.1.1/10.0.0.1/g' package/base-files/files/bin/config_generate
    echo "默认后台 IP 已设置为 10.0.0.1"
fi

# 2. 设置主机名为 NanoPi-R3S
if [ -f "package/base-files/files/bin/config_generate" ]; then
    sed -i 's/ImmortalWrt/NanoPi-R3S/g' package/base-files/files/bin/config_generate
fi

# 3. 检查并同步 custom files 目录
if [ -d "$GITHUB_WORKSPACE/files" ]; then
    cp -r "$GITHUB_WORKSPACE/files" ./files
    echo "已成功注入 custom files 覆盖层。"
fi
