# NanoPi R3S / LTS 固件自动构建

面向 FriendlyElec NanoPi R3S / R3S LTS 的固件构建配置、首启默认设置和 eMMC 迁移工具。内核、设备树、驱动和引导程序来自对应上游；LTS 的具体硬件版本、按键事件与断电行为仍需实机确认。

## 构建路线

| 工作流 | 默认基准 | 软件组合 |
|---|---|---|
| Build ImmortalWrt 25.12.2 for NanoPi R3S | 官方 ImmortalWrt 25.12.2 ImageBuilder | HomeProxy / sing-box、Argon、流量统计、CPU 调频界面、zram 等 |
| Build ImmortalWrt from Source (Full Build) | ImmortalWrt v25.12.2 标签，可输入分支 | 从源码构建，主要软件组合接近 ImageBuilder |
| Build Customer (Official OpenWrt Base) | 官方 OpenWrt v25.12.5，可输入 Tag | HomeProxy、Nikki / Mihomo、PassWall、MosDNS、NATMap、WireGuard 协议界面、网页终端等 |

三条路线都使用 `rockchip/armv8`、`friendlyarm_nanopi-r3s`，默认根分区 **4096 MiB**，并合并 `files/`。构建耗时取决于上游下载、所选应用和 Runner 资源。

Customer 的第三方依赖固定在 `scripts/customer/00-dependencies.sh` 中，更新前应核对提交和包兼容性。固定提交表示源码来源明确，不代表已经通过完整固件编译。Source 默认使用固定版本标签；需要跟随开发时可输入 `openwrt-25.12`，实际提交记录在发布清单中。

Customer 使用稳定版 `mihomo-meta`。软件源定制时移除未使用的 `mihomo-alpha` 定义并刷新索引，避免两者的互斥声明形成 Kconfig 循环依赖。当前 OpenWrt 6.12 内核已内置 BPF，不请求不存在的 `kmod-bpf` 包；其余必需配置仍在依赖展开后严格检查。

源码构建的版本输入会在准备环境前校验。`v25.12.2` 是版本标签，`openwrt-25.12` 是系列分支；输入 `25.12.2` 或 `openwrt-25.12.2` 时，如果原名不存在但 `v25.12.2` 存在，会规范为该标签。未知版本或网络错误会立即报错，不会改用其他版本。修改工作流后，请从 `main` 重新点 **Run workflow**；原失败记录的 **Re-run** 使用当时的工作流和输入。

代理应用在当前锁定上游配置中默认未启用。先选择并配置一种代理，再按需启用 MosDNS；同时启用多个透明代理前，应处理 DNS、端口及防火墙规则冲突。

## 首次启动与保留配置升级

- 明确全新安装时，LAN 管理地址设为 `http://10.0.0.1`，网段 `/24`；DHCP 地址池 `.100`–`.249`，租期 12 小时。
- 全新安装设置主机名 `NanoPi-R3S`、上海时区、DNS 缓存、packet steering 和软件流量卸载。现有配置、恢复备份或无法确定安装状态时，保留用户配置。
- **本项目不写入公共默认密码 `password`。** 新装继承上游账户状态，请在首次本地访问后设置 root 密码；保留配置升级沿用已有密码。
- 初始化标记保存在 `/etc/config/r3s`，并明确列入升级保留清单。旧固件没有此标记时，通过早期启动阶段捕获恢复状态，避免误判为全新安装。
- 关键设置失败会写入系统日志并保留初始化脚本。若首次初始化被中断，后续启动优先保留现有配置，未完成的初始默认项应根据 `logread -e r3s-defaults` 人工检查；已有配置的数据格式迁移失败仍会重试。
- nlbwmon 使用列表型监控范围，跟随 LAN 的 IPv4/IPv6 网络；数据库落盘用于持久化，服务仍使用运行时内存。
- CPU 保留上游或用户设置的有效调频策略。若需 `performance`，请通过相应界面按 policy 配置，并核对实际 `scaling_governor` 与温度。

## 性能与分区说明

`files/etc/sysctl.d/99-custom.conf` 包含 BBR、缓冲区、连接跟踪和虚拟内存参数。实际效果取决于负载、温度及应用组合，应以普通转发、代理 TCP/UDP、并发连接的实测结果为准。BBR 不会自动改变所有普通 NAT 转发客户端的拥塞控制。

zram 可以缓解部分内存压力，不能保证不发生 OOM。packet steering 和软件卸载也不保证所有场景四核均衡或固定幅度的吞吐提升。

**本项目当前不提供自动扩容全盘。** 写入更大的 TF 卡或 eMMC 后，镜像根分区仍按构建大小使用；Ext4 根分区与 SquashFS overlay 的扩容方式不同，应另行备份并处理。

电源按键脚本收到 `released` 事件后执行同步与关机，没有长按时长判断。是否收到正确事件、是否真正断电，需在具体硬件上确认。

## 云端构建与产物

1. Fork 仓库，在 Actions 页面选择对应工作流并手动运行。工作流已声明发布所需的 `contents: write`；组织策略若禁用此权限，需要管理员允许。
2. 构建成功后，从 Actions Artifacts 或 Releases 下载产物。
3. 发布标签包含构建路线、版本或分支、上游短提交号（源码构建）及运行编号。同日重跑使用不同标签。

发布内容包括：

- 以发布标签为前缀的原始固件文件，保留完整设备和文件系统标识。
- `sha256sums.txt`：发布文件的校验表。
- `build-info.txt`、`source-revisions.tsv`：目标、构建参数和实际源码来源。
- 软件包 manifest、官方 buildinfo；源码构建还包含 `final.config` 和 `requested.config`。
- Customer 附带 `customer-dependencies.tsv`；ImageBuilder 附带官方构建器与基准信息校验记录。

ImageBuilder 的官方 buildinfo 描述其预编译基准；实际装入固件的软件组合应以发布 manifest 和 `build-info.txt` 中的 PACKAGES 为准。下载构建器时会先核对同一官方目录的 SHA256。

## 从 TF 卡迁移到 eMMC

先从 TF 卡启动本固件，确认目标 eMMC 的所有分区均未挂载、未作为交换空间或映射设备使用。将 **固件 `.img.gz` 与同一 Release 的 `sha256sums.txt`** 上传至同一目录，保持固件文件名不变，然后执行：

```sh
emmc-install /tmp/完整固件文件名.img.gz
```

工具会核对校验表、设备型号元数据、解压完整性、MBR 两分区布局和目标容量，再要求输入屏幕显示的目标设备名确认。随后流式写入并回读整个镜像，比较 SHA256；只有全部成功才提示完成。

也可显式传入从可信发布记录获得的 SHA256：

```sh
emmc-install /tmp/firmware.img.gz 实际的64位SHA256
```

`--yes` 仅跳过交互确认，不跳过任何安全检查。该工具只接受带 R3S 元数据的 `.img.gz`；原始 `.img`、`.zst`、无元数据镜像和未知分区布局会被拒绝。探测不到唯一 MMC 设备时，不按设备编号猜测。

校验成功后正常关机，断电后拔出 TF 卡，再上电。校验失败或写入中断时，继续从 TF 卡启动并处理目标盘。

## 本地验证

在 Linux 环境安装 Python 3、Bash、dash、Git 和常用 GNU 命令后执行：

```sh
python3 -m unittest discover -s tests -v
```

测试用模拟配置和临时普通文件覆盖初始化迁移、刷机失败路径、配置依赖检查与发布收集，不操作真实块设备。Windows 可通过 Git for Windows 的 Bash/dash 运行；中断测试也通过该环境发送 POSIX 信号。

`validate.yml` 在推送、PR 和手动运行时检查脚本语法并运行这些测试。完整固件交叉编译仍由三条手动构建流程完成；依赖展开后丢失请求的软件包或目标配置会立即报错。

修改版仍需完成完整固件构建，以及 TF / eMMC 启动、保留配置升级、硬件按键和典型网络负载的实机验收。

## 目录

```text
.github/workflows/       构建、发布及离线验证
scripts/build/           配置检查、产物和来源收集
scripts/customer/        固定第三方依赖、软件定制和配置生成
files/lib/preinit/       早期捕获新装/恢复状态
files/lib/upgrade/keep.d/ 初始化标记的升级保留清单
files/etc/uci-defaults/  首启设置与兼容迁移
files/etc/sysctl.d/      可测试的网络及内存参数
files/etc/rc.button/     电源按键处理
files/usr/bin/           eMMC 安装工具
tests/                  无真实设备写入的回归测试
```
