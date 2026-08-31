#!/bin/bash
# ==============================================================================
# sbwml-style Step 1: 准备与定制 Feeds 源
# 作用：在 ./scripts/feeds update 之前执行，用于添加外部插件源
# ==============================================================================

set -e

echo "=== [Step 1] 正在配置自定义 Feeds 源 ==="

# 确保在 openwrt 源码根目录中执行
if [ -f "feeds.conf.default" ]; then
    # 示例：追加外部 passwall 依赖包源（如需要）
    # echo 'src-git passwall_packages https://github.com/xiaorouji/openwrt-passwall-packages.git;main' >> feeds.conf.default
    echo "Feeds 配置文件检查完毕。"
fi
