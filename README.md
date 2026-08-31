# NanoPi R3S / R3S LTS · ImmortalWrt 固件自动构建

<p align="center">
  <img src="https://img.shields.io/badge/Device-NanoPi%20R3S%20LTS-blue?style=flat-square" alt="Device">
  <img src="https://img.shields.io/badge/SoC-Rockchip%20RK3566-orange?style=flat-square" alt="SoC">
  <img src="https://img.shields.io/badge/OS-ImmortalWrt%2025.12-green?style=flat-square" alt="ImmortalWrt">
  <img src="https://img.shields.io/badge/Package%20Manager-apk-brightgreen?style=flat-square" alt="apk">
  <img src="https://img.shields.io/badge/Build-GitHub%20Actions-blueviolet?style=flat-square" alt="Actions">
</p>

本项目基于 **GitHub Actions** 为 **FriendlyElec NanoPi R3S / R3S LTS**（Rockchip RK3566 / 1GB LPDDR4X / 32GB eMMC / 双千兆）提供全自动化的 **ImmortalWrt 固件云编译与打包**。

内置专属性能优化与常用网络插件，刷机后**开箱即用，免二次繁琐配置**。

---

## 🌟 核心特性与预置优化

* ⚡ **系统内核与包管理**：基于 ImmortalWrt 25.12+ 稳定分支（Linux 6.12 内核，全面切换为现代 Alpine 风格的 **`apk`** 包管理器）。
* 🚀 **代理与分流生态**：预置 `luci-app-homeproxy` 与 `sing-box`，支持 VLESS-Reality、Shadowsocks (ARMv8 AES 硬件指令加速) 等协议。
* 🛡️ **1GB 内存抗 OOM 防护**：集成 `zram-swap` 内存压缩机制，设定 `vm.swappiness=5` 极低换页门槛，保证大并发突发流量下系统坚如磐石。
* 🔥 **网络与转发调优**：
  * 开启 **TCP BBR** 拥塞控制算法，提升代理出站 TCP 连接质量与抗丢包能力。
  * 扩大核心 UDP 套接字缓冲区至 **7.5MB**（满足 quic-go 标准，畅享 Hysteria2 / QUIC 高速连接）。
  * 默认开启 **Software Flow Offloading**（软件流量分载，降低 NAT 转发 CPU 开销 30%~50%）。
  * 开启 **Packet Steering (RPS)**，实现四核软中断完全均衡负载。
* 🔌 **开箱即用体验**：
  * 默认 LAN 口后台管理 IP 为 **`10.0.0.1`**（避免与光猫 192.168.1.1 产生冲突）。
  * 内置开机自动识别并无损扩满 **32GB eMMC** 根分区。
  * 适配 R3S LTS 机身**物理电源按键**（按下释放触发 `sync` 安全刷盘并关机）。

---

## 🛠️ 构建方式（两种 Actions 工作流）

在仓库的 [Actions 页面](../../actions) 支持选择以下两种构建方式：

| 构建工作流 | 构建方式 | 预计耗时 | 特点与适用场景 |
| :--- | :--- | :---: | :--- |
| **`Build ImmortalWrt 25.12.1 for NanoPi R3S`** | **ImageBuilder 极速打包** | ⚡ **1 ~ 2 分钟** | **日常最推荐！** 基于官方预编译稳定二进制快速组装，打包极速，零报错风险。 |
| **`Build ImmortalWrt from Source (Full Build)`** | **全源码交叉编译** | ⏳ **1.5 ~ 2.5 小时** | 完整编译 Linux 内核及所有软件包，支持自由选择源码分支（如 `openwrt-25.12` / `master`）。 |

---

## 🚀 如何使用本项目构建你自己的固件

1. **Fork 本仓库** 到你的 GitHub 账号下。
2. 进入仓库 **Settings ➔ Actions ➔ General ➔ Workflow permissions**，勾选 **`Read and write permissions`** 并保存。
3. 点击 **Actions** 标签页，选择你想要的工作流，点击 **`Run workflow`**。
4. 构建完成后，前往仓库首页右侧的 **[Releases](../../releases)** 页面直接下载以日期命名的 `.img.gz` 固件。

---

## 📥 刷机与初始化说明

1. **首次刷入 32GB eMMC**：
   * **方式 A (推荐)**：使用友善官方的 eFlasher TF 卡启动，在浏览器访问 `http://<开发板IP>:8080` 的 **eMMC 刷机助手网页界面** 上传固件一键烧录。
   * **方式 B (命令行)**：将固件刷入 TF 卡启动后，通过终端执行 `zcat /tmp/firmware.img.gz | dd of=/dev/mmcblk0 bs=4M conv=fsync` 写入 eMMC。
   * *烧录完成后拔出 TF 卡，即可从 32GB eMMC 极速启动。*
2. **首次登录后台**：
   * 浏览器访问：**`http://10.0.0.1`**
   * 默认账户：`root`（默认无密码，首次登录后请及时设置密码）。

---

## 📂 项目结构说明

```text
.
├── .github/workflows/
│   ├── build-r3s.yml             # ImageBuilder 极速云打包工作流 (1~2分钟)
│   └── build-source-r3s.yml      # 全源码交叉编译工作流 (1.5~2.5小时)
├── files/                        # 编译期直接固化打入固件的优化文件
│   └── etc/
│       ├── rc.button/
│       │   └── power             # LTS 物理按键安全关机脚本
│       ├── sysctl.d/
│       │   └── 99-custom.conf    # BBR / 7.5MB UDP 缓冲 / conntrack / swappiness
│       └── uci-defaults/
│           └── 99-r3s-optimize   # 开机自销毁初始化 (10.0.0.1 / 全盘扩容 / 流分载等)
└── README.md
```

---

## 🤝 致谢与参考

* [ImmortalWrt 官方项目](https://github.com/immortalwrt/immortalwrt)
* [FriendlyElec 友善之臂 Wiki](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_R3S/zh)
* [OpenWrt 项目](https://openwrt.org/)
* [P3TERX/Actions-OpenWrt](https://github.com/P3TERX/Actions-OpenWrt)
