# NanoPi R3S / LTS · ImmortalWrt & OpenWrt 固件自动构建

<p align="center">
  <img src="https://img.shields.io/badge/Device-NanoPi%20R3S%20%2F%20LTS-0366d6?style=flat-square&logo=linux" alt="Device">
  <img src="https://img.shields.io/badge/SoC-Rockchip%20RK3566-ff6a00?style=flat-square&logo=arm" alt="SoC">
  <img src="https://img.shields.io/badge/RAM-1GB%20LPDDR4X-orange?style=flat-square" alt="RAM">
  <img src="https://img.shields.io/badge/eMMC-32GB-yellow?style=flat-square" alt="eMMC">
  <img src="https://img.shields.io/badge/Build-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="Actions">
  <img src="https://img.shields.io/badge/Linker-Mold-brightgreen?style=flat-square" alt="Mold">
</p>

基于 **GitHub Actions** 为 **FriendlyElec NanoPi R3S / R3S LTS** 打造的自动化固件编译系统。预置网络底层优化与代理生态，开箱即用。

---

## 🛠️ 三大构建工作流

在 [Actions 页面](../../actions) 点击相应工作流即可一键触发：

| 工作流 | 源码基准 | 构建机制与特色 | 耗时 | 推荐场景 |
| :--- | :--- | :--- | :---: | :--- |
| **`Build ImmortalWrt 25.12.1 for NanoPi R3S`** | ImmortalWrt 25.12.1 | ⚡ **ImageBuilder 镜像组装**<br>· 官方预编译包快速组装 + files 优化注入 | **1~2 分钟** | ⭐ **日常推荐**<br>出包极快，日常使用首选 |
| **`Build Customer (Official OpenWrt Base)`** | 官方 OpenWrt<br>*(v25.12.5)* | 🚀 **Customer 全源码编译**<br>· **`-O3` / Cortex-A55 矢量优化** + **Mold 链接**<br>· **Go 1.24+** + Nikki + HomeProxy + MosDNS | **1.5~2.5 小时** | 🛠️ **极客首选**<br>纯净官方基线，追求极致性能 |
| **`Build ImmortalWrt from Source (Full Build)`** | ImmortalWrt 官方源码<br>*(openwrt-25.12)* | 🧱 **ImmortalWrt 全源码编译**<br>· 原生 Feeds 全量交叉编译，支持自由切换分支 | **1.5~2.5 小时** | 📦 **二次开发**<br>定制 ImmortalWrt 源码 |

---

## 🌟 核心特性

* **代理分流**：集成 `HomeProxy` (sing-box 内核)、`Nikki` (Mihomo 内核)、`PassWall`、`MosDNS` (内置分流规则)、`NATMap`、`WireGuard`。
* **现代 UI**：预置 `luci-theme-argon` 毛玻璃主题与 `luci-app-argon-config`。
* **1GB 内存防护**：`zram-swap` 内存压缩（`swappiness=5`），杜绝大并发与大规则集导致的 OOM 崩溃。
* **网络加速**：强制启用 **TCP BBR**、**7.5MB UDP 缓冲区** (满足 QUIC / Hysteria2 满速)、**Flow Offloading** 与 **RPS 软中断四核均衡**。
* **开箱即用**：
  * 后台地址：**`http://10.0.0.1`**（防光猫 192.168.1.1 冲突）
  * 默认凭据：`root` / **`password`**
  * 开机自动将根分区扩满板载 **32GB eMMC**
  * LTS 机身物理 Power 键安全关机
  * 内置 **`emmc-install`** 终端一键刷机工具

---

## 🚀 使用指南

### 1. 云端构建
1. **Fork 本仓库** ➔ 在仓库 **Settings ➔ Actions ➔ General** 勾选 **`Read and write permissions`**。
2. 在 **Actions** 页面选择工作流，点击 **`Run workflow`**。
3. 构建完成后在 **[Releases](../../releases)** 页面下载 `.img.gz` 固件。

### 2. 刷入 eMMC
* **网页刷机**：烧录官方 [eFlasher 固件](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh) 至 TF 卡启动，浏览器访问 `http://<设备IP>:8080` 上传固件烧入 eMMC，拔卡重启。
* **命令行刷机**：TF 卡启动后将固件上传至 `/tmp/firmware.img.gz`，执行：
  ```sh
  emmc-install /tmp/firmware.img.gz
  ```
  完成后断电**拔出 TF 卡**，重新通电即可。

---

## 📂 项目结构

```text
.
├── .github/workflows/
│   ├── build-r3s.yml             # ImageBuilder 极速打包 (1~2分钟)
│   ├── build-customer-r3s.yml    # Customer 全源码编译 (官方 OpenWrt + -O3)
│   └── build-source-r3s.yml      # ImmortalWrt 官方源码全编译
├── scripts/customer/             # Customer DIY 编译流水线脚本
│   ├── 01-diy-feeds.sh           # 扩展 Feeds 注入
│   ├── 02-diy-packages.sh        # Go 1.24 升级、依赖去重、插件拉取、IP/时区定制
│   └── 03-generate-config.sh     # 目标架构配置、-O3/Mold 优化与依赖展开
├── files/                        # 固化底层优化层 (BBR / 扩容 / 按键 / 刷机工具)
└── README.md
```

---

## 🤝 致谢

[ImmortalWrt](https://github.com/immortalwrt/immortalwrt) · [OpenWrt](https://openwrt.org/) · [FriendlyElec](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh) · [sbwml/builder](https://github.com/sbwml/builder) · [P3TERX](https://github.com/P3TERX/Actions-OpenWrt) · [jerrykuku](https://github.com/jerrykuku/luci-theme-argon)
