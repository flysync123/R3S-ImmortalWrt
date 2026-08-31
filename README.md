# NanoPi R3S / R3S LTS · ImmortalWrt & OpenWrt 固件全自动云构建

<p align="center">
  <img src="https://img.shields.io/badge/Device-NanoPi%20R3S%20%2F%20LTS-0366d6?style=flat-square&logo=linux" alt="Device">
  <img src="https://img.shields.io/badge/SoC-Rockchip%20RK3566-ff6a00?style=flat-square&logo=arm" alt="SoC">
  <img src="https://img.shields.io/badge/RAM-1GB%20LPDDR4X-orange?style=flat-square" alt="RAM">
  <img src="https://img.shields.io/badge/eMMC-32GB%20High--Speed-yellow?style=flat-square" alt="eMMC">
  <img src="https://img.shields.io/badge/Build-GitHub%20Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white" alt="Actions">
  <img src="https://img.shields.io/badge/Linker-Mold%20Fast%20Linker-brightgreen?style=flat-square" alt="Mold">
</p>

本项目基于 **GitHub Actions** 为 **FriendlyElec NanoPi R3S / NanoPi R3S LTS**（Rockchip RK3566 / 1GB LPDDR4X / 32GB eMMC / 双千兆网口）打造了一站式、多轨并行的自动化固件云编译与打包系统。

固件内置专属底层优化、代理分流生态与开箱即用脚本，刷机后**无需二次繁琐配置即可满血运行**。

---

## 🛠️ 三大构建工作流对比与选型

进入仓库的 [Actions 页面](../../actions)，根据实际需求一键触发：

| 构建工作流 | 源码基准 | 核心机制与特色 | 预计耗时 | 推荐场景 |
| :--- | :--- | :--- | :---: | :--- |
| **`Build ImmortalWrt 25.12.1 for NanoPi R3S`** | **ImmortalWrt 25.12.1** | ⚡ **ImageBuilder 官方镜像组装器**<br>· 声明式增量包组装<br>· 注入 files 优化层与 HomeProxy | **1 ~ 2 分钟** | ⭐ **日常最推荐！**<br>出包极快、零编译报错，日常升级首选。 |
| **`Build Customer (Official OpenWrt Base)`** | **官方原版 OpenWrt**<br>*(默认 v25.12.5)* | 🚀 **Customer 深度定制全源码编译**<br>· **`-O3` 性能压榨优化** + **Mold 极速链接**<br>· **Go 1.24+** 工具链<br>· HomeProxy + Nikki + MosDNS + PassWall | **1.5 ~ 2.5 小时** | 🛠️ **性能党与极客首选！**<br>纯净官方基线，追求极致性能与全套代理生态。 |
| **`Build ImmortalWrt from Source (Full Build)`** | **ImmortalWrt 官方源码**<br>*(openwrt-25.12 / master)* | 🧱 **ImmortalWrt 标准全量交叉编译**<br>· 官方原生 Feeds 与全包编译<br>· 自由切换分支与深度定制 | **1.5 ~ 2.5 小时** | 📦 **深度定制开发**<br>跟进 ImmortalWrt 官方分支或二次开发源码。 |

---

## 🌟 核心特性与调优亮点

### 1. 现代代理分流与网络生态
* **代理分流**：预置 **`HomeProxy`**（sing-box 内核，支持 VLESS-Reality 与 ARMv8 AES 指令加速）、**`Nikki`**（Mihomo 内核）、**`PassWall`**。
* **DNS 与穿透**：**`MosDNS`** 国内外秒级分流解析（内置 v2ray-geodata 规则）、**`NATMap`** 全锥型 STUN 打洞、**`WireGuard`** 安全隧道。
* **现代 Web UI**：预置 **`luci-theme-argon`** 毛玻璃主题与 `luci-app-argon-config` 定制插件。

### 2. 针对 1GB 内存的抗 OOM 护城河
* **虚拟内存压缩**：预置 **`zram-swap`** 设定 **`vm.swappiness=5`**，平时不占用，濒临 OOM 崩溃时由压缩内存兜底。
* **轻量化收敛**：坚持使用极轻量 `uhttpd`（仅占 2MB 内存），显式屏蔽 Docker、OpenClash 等高常驻内存组件。

### 3. 内核转发与网络加速
* **TCP BBR**：路由器本机代理出站强制启用 BBR 拥塞控制，降低跨境弱网丢包。
* **7.5MB 核心 UDP 缓冲**：设定 `rmem/wmem_max = 7500000`，畅享 Hysteria2 / QUIC 类 UDP 协议全速转发。
* **流分载与软中断均衡**：开启 **Flow Offloading** 与 **Packet Steering (RPS)**，实现四核软中断绝对均衡。
* **eBPF 与网卡微码**：内核开启 `kmod-bpf`，预装 `r8169-firmware` 保证 PCIe RTL8111H 千兆满载不掉速。

### 4. 极致的开箱即用体验
* 🔌 **默认 IP**：LAN 口后台管理 IP 为 **`10.0.0.1`**（防与光猫 192.168.1.1 冲突）。
* 💾 **全盘无损扩容**：开机自销毁脚本全自动将根分区扩满板载 **32GB eMMC**。
* ⚡ **一键 eMMC 刷机**：内置 **`emmc-install`** 工具，TF 卡启动下一条命令即可把固件写入 eMMC。
* 🔘 **硬件按键关机**：按下机身物理 Power 键，自动触发 `sync` 安全刷盘并执行关机。

---

## 🚀 极速构建与刷机指南

### 1. 云端构建步骤
1. **Fork 本仓库** 到个人 GitHub 账号。
2. 开启 Actions 写入权限：**Settings ➔ Actions ➔ General ➔ Workflow permissions ➔ 勾选 `Read and write permissions` ➔ Save**。
3. 进入 **Actions** 页面，选中目标工作流，点击 **`Run workflow`**。
4. 构建完成后，前往 **[Releases](../../releases)** 页面下载 `.img.gz` 固件。

### 2. 首次登录
* **后台地址**：`http://10.0.0.1`
* **默认账户**：`root`
* **默认密码**：`password`

### 3. eMMC 刷机方法
* **方法 A（图形化，推荐小白）**：使用友善官方 [eFlasher 镜像](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh) 写入 TF 卡启动，浏览器访问 `http://<开发板IP>:8080` 上传固件烧录至 eMMC，拔卡重启。
* **方法 B（命令行，一条命令）**：用 balenaEtcher 将固件刷入 TF 卡开机，通过 SCP 上传固件至 `/tmp/firmware.img.gz`，SSH 执行：
  ```sh
  emmc-install /tmp/firmware.img.gz
  ```
  提示完成后关机，**拔掉 TF 卡**，重新通电即可从 eMMC 极速启动。

---

## 📂 项目工程架构

```text
.
├── .github/workflows/
│   ├── build-r3s.yml             # 1. ImageBuilder 极速云打包 (1~2分钟)
│   ├── build-customer-r3s.yml    # 2. Customer 深度定制全源码编译 (官方 OpenWrt 基线 + -O3)
│   └── build-source-r3s.yml      # 3. ImmortalWrt 官方标准全源码交叉编译
├── scripts/
│   └── customer/                 # Customer 模块化构建流水线
│       ├── 01-diy-feeds.sh       # Step 1: 挂载 Nikki/PassWall/MosDNS 扩展 Feeds
│       ├── 02-diy-packages.sh    # Step 2: 升级 Go 1.24、清理冲突包、拉取单包插件、定制 IP/时区
│       └── 03-generate-config.sh # Step 3: 目标架构声明、-O3/Mold 优化与 .config 依赖展开
├── files/                        # 固化打入固件的底层优化层
│   ├── etc/
│   │   ├── rc.button/power       # LTS 物理电源按键安全关机脚本
│   │   ├── sysctl.d/99-custom.conf # BBR / 7.5MB UDP 缓冲 / 连接数优化 / swappiness=5
│   │   └── uci-defaults/99-r3s-optimize # 开机自销毁初始化 (10.0.0.1 / 全盘扩容 / 流分载 / RPS)
│   └── usr/bin/
│       └── emmc-install          # 终端 eMMC 一键刷机工具
└── README.md
```

---

## 🤝 致谢

* [ImmortalWrt 项目](https://github.com/immortalwrt/immortalwrt) · [OpenWrt 官方社区](https://openwrt.org/)
* [sbwml/builder 极客项目](https://github.com/sbwml/builder) · [FriendlyElec 友善之臂](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh)
* [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt) · [jerrykuku/luci-theme-argon](https://github.com/jerrykuku/luci-theme-argon)
