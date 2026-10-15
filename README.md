# NanoPi R3S / LTS 固件自动构建

基于 GitHub Actions 的 FriendlyElec NanoPi R3S / R3S LTS 自动化固件构建系统，针对 1GB 内存与双千兆网口深度调优，开箱即用。

---

## 🛠️ 构建工作流

| 工作流 | 源码基准 | 构建方式 | 耗时 | 输出固件命名规范 |
| :--- | :--- | :--- | :---: | :--- |
| **`Build ImmortalWrt 25.12.2 for NanoPi R3S`** | ImmortalWrt 25.12.2 | ImageBuilder 极速组装 | 1~2 分钟 | `ImmortalWrt-25.12.2-NanoPi-R3S-[squashfs/ext4]-sysupgrade-YYYY.MM.DD.img.gz` |
| **`Build Customer (Official OpenWrt Base)`** | 官方 OpenWrt *(v25.12.5)* | 全源码编译 + 现代生态 | 1.5~2.5 小时 | `OpenWrt-Customer-NanoPi-R3S-[squashfs/ext4]-sysupgrade-YYYY.MM.DD.img.gz` |
| **`Build ImmortalWrt from Source (Full Build)`** | ImmortalWrt 官方源码 | 全源码标准交叉编译 | 1.5~2.5 小时 | `ImmortalWrt-Source-NanoPi-R3S-[squashfs/ext4]-sysupgrade-YYYY.MM.DD.img.gz` |

> 构建完成后，固件及对应的 `sha256sums.txt` 校验文件会自动发布至 **Releases** 页面。

---

## 🌟 默认系统信息

- **后台地址**：`http://10.0.0.1`（防光猫 192.168.1.1 冲突）
- **默认凭据**：用户名 `root` / 密码 `password`
- **根分区大小**：预分配 4GB（初次启动自动扩容全盘）
- **系统核心调优**：
  - **网络加速**：强制启用 TCP BBR、7.5MB UDP 缓冲区、Flow Offloading（软件流量分载）、RPS 软中断四核均衡
  - **1GB 内存防护**：启用 `zram-swap` 内存压缩（`swappiness=5`），杜绝 OOM 崩溃
  - **预置代理生态**：HomeProxy (sing-box)、Nikki (Mihomo)、PassWall、MosDNS、Argon 现代主题
  - **硬件适配**：LTS 物理 Power 键安全刷盘关机、终端内置 `emmc-install` 一键刷机工具

---

## 🚀 快速使用

### 1. 云端构建
1. Fork 本仓库，进入 **Settings ➔ Actions ➔ General**，将 **Workflow permissions** 设置为 **Read and write permissions**。
2. 在 **Actions** 页面选择对应的工作流，点击 **Run workflow**。
3. 构建完成后在 **Releases** 页面下载固件。

### 2. 刷入 eMMC
- **方式 A（网页刷机）**：使用官方 [eFlasher 固件](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh) 写入 TF 卡启动，浏览器访问 `http://<设备IP>:8080` 上传固件写入 eMMC，拔卡重启。
- **方式 B（命令行刷机）**：TF 卡启动后将固件上传至 `/tmp/` 目录，在终端执行：
  ```sh
  emmc-install /tmp/固件名称.img.gz
  ```
  完成后断电，**拔出 TF 卡**，重新上电即可从 32GB eMMC 启动。

---

## 📂 项目结构

```text
.
├── .github/workflows/
│   ├── build-imagebuilder-r3s.yml    # ImageBuilder 极速打包 (1~2 分钟)
│   ├── build-customer-r3s.yml        # Customer 全源码编译 (官方 OpenWrt 基准)
│   └── build-source-r3s.yml          # ImmortalWrt 官方源码全编译
├── scripts/customer/                 # Customer DIY 编译流水线脚本
│   ├── 01-diy-feeds.sh               # 扩展 Feeds 注入
│   ├── 02-diy-packages.sh            # 工具链检查、软件包定制与 files 注入
│   └── 03-generate-config.sh         # 架构配置与依赖展开
├── files/                            # 编译期直接固化打入固件的优化层
│   ├── etc/rc.button/power           # LTS 物理电源键关机监听
│   ├── etc/sysctl.d/99-custom.conf   # BBR、UDP 缓冲与内核调优
│   ├── etc/uci-defaults/99-r3s-optimize # 开机自销毁初始化配置 (10.0.0.1 等)
│   └── usr/bin/emmc-install          # 终端 eMMC 一键刷机工具
└── README.md
```
