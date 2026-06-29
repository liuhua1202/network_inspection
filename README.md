# 网络设备巡检工具 · Network Device Inspector

[![Version](https://img.shields.io/badge/version-v2.1-0078d4?style=flat-square)](#-变更摘要)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d4?style=flat-square)](#-特性)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square)](https://www.python.org/)
[![Netmiko](https://img.shields.io/badge/netmiko-4.x-FF6F00?style=flat-square)](https://github.com/ktbyers/netmiko)
[![Tkinter](https://img.shields.io/badge/tkinter-builtin-2C5E8E?style=flat-square)](#-技术栈)

基于 Python + Tkinter 的网络设备批量巡检工具，支持 SSH / Telnet 协议、并发执行、结果导出 Excel、GBK / UTF-8 中文输出识别。

![screenshot](docs/screenshot.png)

## ✨ 特性

- 🖥️ **现代化 GUI**：浅色卡片式布局，标题/工具栏/日志区/状态栏清晰分区，可切换高对比度模式
- 🌐 **多厂商支持**：华为、思科、H3C、Juniper、锐捷、Linux 主机等 6+ 设备类型
- 📡 **多协议**：SSH 与 Telnet 同时支持，单台设备协议可独立配置
- ⚡ **批量并发**：`ThreadPoolExecutor` 控制并发数（默认 5，可调 1-50）
- ⏱ **可配置超时**：连通性测试支持 1-60s 单设备超时，无响应立即判定为超时
- 🔤 **编码感知**：三级优先级（设备列 > 设备类型默认 > UI 默认），自动检测默认 GBK；命令输出含 Unicode 替换字符时主动告警
- 🔍 **实时过滤**：设备列表支持名称 / IP / 类型 / 协议 实时搜索
- 🚦 **重型命令**：commands 文件支持 `# @heavy` 与 `# @timeout N` 标记，自动应用更长超时
- 📊 **结果导出**：巡检结果与统计报告一键导出为 Excel（`.xlsx`）
- 📁 **配置灵活**：设备列表 / 设备类型 / 命令文件均可用 CSV 或 TXT，每台设备可指定独立编码
- 📋 **详细日志**：每台设备的执行明细实时写入 `InspectionLogs/<日期>/`，并附带 UTF-8 BOM 报告
- 🛑 **优雅停止**：随时停止巡检，未完成的设备立即中断，不留后台残留

## 📦 下载

前往 [Releases 页面](https://github.com/liuhua1202/network_inspection/releases) 下载最新版（产物文件名带版本号）：

| 平台 | 文件 | 大小 | 说明 |
|---|---|---|---|
| Windows | [`NetworkInspector-v2.1.exe`](https://github.com/liuhua1202/network_inspection/releases/download/v2.1/NetworkInspector-v2.1.exe) | ~14 MB | 单文件便携版，零安装，双击即用 |
| 源码 | `Source code (zip)` / `Source code (tar.gz)` | — | GitHub 自动生成 |

**v2.1 SHA256**：
```
7febe7cf21aedf408da62df716b650f6f5505dbdbfafae33d30606e6bee26ee1  NetworkInspector-v2.1.exe
```

> Windows：双击即用，无需安装。首次启动可能被 SmartScreen 拦截，点"更多信息 → 仍要运行"即可。  
> 校验：`Get-FileHash .\NetworkInspector-v2.1.exe -Algorithm SHA256`（PowerShell）或 `certutil -hashfile NetworkInspector-v2.1.exe SHA256`。

不需要 Windows 二进制的话也可以直接跑源码：

```bash
git clone https://github.com/liuhua1202/network_inspection.git
cd network_inspection
pip install -r requirements.txt
python network_inspection.py
```

## 🚀 本地开发

### 环境要求

- Python ≥ 3.8（3.10+ 推荐）
- Tkinter（Windows / macOS 自带；Linux 需 `sudo apt install python3-tk`）
- 可选：`pandas` + `openpyxl`（仅"导出结果"功能需要）

### 安装

```bash
git clone https://github.com/liuhua1202/network_inspection.git
cd network_inspection
pip install -r requirements.txt
```

### 启动

```bash
python network_inspection.py
```

### 打包便携 .exe（可选）

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name NetworkInspector \
    --add-data "config;config" \
    --add-data "favicon.ico;." \
    network_inspection.py
# 产物：dist/NetworkInspector.exe（~30 MB）
```

## 🏗️ 技术栈

- **[Python 3.8+](https://www.python.org/)** — 主语言
- **[Tkinter](https://docs.python.org/3/library/tkinter.html)** — GUI（标准库，无需安装）
- **[Netmiko 4.x](https://github.com/ktbyers/netmiko)** — SSH / Telnet 设备连接
- **[pandas](https://pandas.pydata.org/) + [openpyxl](https://openpyxl.readthedocs.io/)** — Excel 导出（可选依赖）
- **[ThreadPoolExecutor](https://docs.python.org/3/library/concurrent.futures.html)** — 并发执行
- 单文件 `network_inspection.py`（约 3500 行），无第三方 GUI 框架

### 编码处理的三级优先级

```
device['encoding']  >  device_type['encoding']  >  UI 下拉框  >  'gbk' 兜底
```

`devices.csv` 第 9 列（CSV）或最后字段（`|` 分隔）可逐台指定编码。中文设备用 GBK，现代设备用 UTF-8。编码错误时主动在日志中以 `[WARNING]` 标记含 Unicode 替换字符的命令。

### 重型命令标记

`config/commands/*.txt` 支持以下注释指令：

```bash
# @heavy                       ← 下一条命令用 180s 超时（替代默认 60s）
display current-configuration

# @timeout 90                  ← 下一条命令用 90s 超时（最优先）
show tech-support

show version                   ← 普通命令，60s 超时
```

## 📂 项目结构

```
network_inspection/
├── network_inspection.py        # 主程序（单文件，~3500 行）
├── favicon.ico                  # 窗口图标
├── requirements.txt             # 依赖清单
├── LICENSE                      # MIT
├── README.md                    # 本文件
├── .gitignore
├── config/                      # 运行时配置（CSV / TXT）
│   ├── devices.csv              # 设备列表（GBK，含中文设备名）
│   ├── devices.txt              # 同上的 | 分隔版本（备用）
│   ├── device_types.csv         # 设备类型定义（GBK）
│   ├── device_types.txt         # 同上的 | 分隔版本
│   └── commands/                # 巡检命令文件
│       ├── commands_cisco.txt   # 含 # @heavy 标注
│       ├── commands_huawei.txt  # 含 # @heavy 标注
│       ├── commands_h3c.txt
│       ├── commands_juniper.txt
│       ├── commands_linux.txt
│       └── commands_ruijie.txt
├── examples/                    # 参考示例（不直接使用）
│   └── commands_sdt_demo.txt    # SDT 类型命令示例（未注册到 device_types）
└── 巡检指南/                    # 厂商配置与使用文档
    ├── 配置使用指南.md
    ├── H3C设备巡检配置指南.md
    ├── 华为设备巡检配置指南.md
    ├── 思科设备巡检配置指南.md
    ├── Juniper设备巡检配置指南.md
    ├── 锐捷设备巡检配置指南.md
    ├── Linux主机巡检配置指南.md
    └── 日志系统更新说明.md
```

## 📝 运行示例

启动后界面分四个区域：

```
┌──────────────────────────────────────────────────────────┐
│ 🖥️ 网络设备自动巡检工具                        ⏸ 已停止 │
├──────────────────────────────────────────────────────────┤
│ 🚀 开始巡检  ⏹ 停止巡检          📊 导出  📈 统计  📁  │
├──────────────────────────────────────────────────────────┤
│ 📋 设备列表 (181 台)              📝 运行日志            │
│ ┌────────────────────────────┐ ┌──────────────────────┐ │
│ │ ☑ 浪潮-cisco-sw-01  1.1.1  │ │ [10:23:01] 加载配置 │ │
│ │ ☑ 浪潮-cisco-sw-02  1.1.2  │ │ [10:23:05] 开始巡检 │ │
│ │ ☑ 浪潮-huawei-sw-03 ...    │ │ [10:23:06] ✓ sw-01  │ │
│ │   ...                      │ │ ...                  │ │
│ └────────────────────────────┘ └──────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│ ⚙️ 并发:5  编码:自动检测  超时:30s  日志:INFO            │
│             ▓▓▓▓▓▓▓▓░░ 已完成 30/181                   │
└──────────────────────────────────────────────────────────┘
```

`devices.csv` 配置示例：

```csv
设备名,IP,类型ID,用户名,密码,enable密码,端口,协议,编码,selected
浪潮-cisco-sw-01,192.168.139.1,1,cisco,cisco,cisco,22,ssh,gbk,1
浪潮-huawei-sw-02,192.168.139.2,0,op,Nnteamu@20252,,22,ssh,utf-8,1
浪潮-linux-host-03,192.168.139.3,5,,,,23,telnet,gb2312,0
```

## 📋 v2.1 变更摘要

相比 v2.0，本版本修复若干关键 bug 并补齐功能：

### 🐛 修复

- **巡检结果回填**：`inspection_worker` 新增 `inspection_results` 参数，每台设备的 `success/error/timeout/duration` 真实回填到 UI，导出结果与统计报告不再为空
- **线程参数错位**：`start_inspection` 把 `max_workers` 挪到 `kwargs`，修复 `TypeError: inspection_worker() got multiple values for argument 'default_encoding'`（线程静默死亡的根因）
- **后台线程动 Tk 控件**：所有后台线程的 `widget.config` / `progress_bar.__setitem__` 全部走 `dialog.after(0, ...)` 派发到主线程
- **进度条传错对象**：`start_inspection` 改为传 `self.progress_bar`（DetailedProgressbar）而非 IntVar，详细文本"已完成 X/Y 台设备"正常显示
- **日志级别形同虚设**：`log_level_combobox` 绑定 `<<ComboboxSelected>>` 回写 `self.min_log_level`，过滤真正生效
- **统计报告解析字符串**：不再 `status_var.split("，")` hack 数字，改用真实 `inspection_results` 统计
- **编码未传给 Netmiko**：`device_info` 现在带 `encoding` 参数，UI 下拉框"自动检测"对中文设备默认走 GBK
- **CSV 校验卡死**：取消"必须含英文列名"的检查，支持跳注释、按位置校验、`.csv`/`.txt` 自适应

### ✨ 新增

- **`# @heavy` / `# @timeout N`** 命令标记：重型命令（如 `display current-configuration`）独立 180s 超时
- **`devices.csv` 第 10 列 `selected`**：可在文件里预勾选设备，无需启动后手动选
- **连通性测试独立按钮组**：▶ 开始 / ⏹ 停止（详情上方主操作）+ 📋 复制结果 / 关闭（底部工具）
- **连通性测试可配置超时**：Spinbox 1-60s，默认 5s，失败不重试
- **连通性测试并发执行**：`ThreadPoolExecutor`，20 台设备从 7 分钟 → 15 秒
- **辅助函数 `_check_encoding_match`**：命令输出含 Unicode 替换字符时主动 `[WARNING]`，并给出 devices.csv 修正指引
- **`sanitize_filename`**：日志路径自动清洗 Windows 非法字符
- **死代码清理**：`encrypt_password` / `validate_command` / `DeviceModel` 等 11 个未引用符号删除

### 🔧 重构

- `_resolve_effective_encoding` 三级优先级钩子
- `_run_inspection_worker` 拆分，添加顶层 try/except 兜底，线程不再静默死亡
- 高对比度模式真正生效：遍历 widget 树刷新 bg/fg，重建 ttk 样式
- 设备类型 `.csv` 与 `.txt` 数据一致；删除未引用 `devices-1.csv`
- `commands_*.txt` 中 `current-configuration` / `running-config` 标 `# @heavy`

## 🐛 故障排查

**Q: 启动后报 `ModuleNotFoundError: No module named 'netmiko'`？**
A: 装依赖：`pip install -r requirements.txt`。Linux 还要装 tkinter：`sudo apt install python3-tk`。

**Q: 设备输出有乱码 / `?` ？**
A: 是编码不匹配。看运行日志里有没有 `[WARNING] xxx 输出含 N 个替换字符`，按提示在 `devices.csv` 第 9 列填正确编码（中文老设备 GBK，现代设备 UTF-8，混合用 GB2312）。

**Q: 巡检报 `TypeError: got an unexpected keyword argument 'errors'`？**
A: 旧版本遗留。本版本已移除 `'errors'` 参数，请确认 `network_inspection.py` 是最新版本。

**Q: 点了"开始巡检"但什么都没发生？**
A: 旧版本 bug（线程参数错位导致 TypeError 静默崩）。本版本已修。同时建议：
- 看运行日志第一条是否有 `[INFO]` 提示
- 看状态栏是否从"开始巡检..."切到"正在处理 X/Y"

**Q: 测试连通性对话框卡在"等待开始"？**
A: 本版本加了显式 ▶ 开始测试 按钮（不会自动跑）。点这个按钮才执行。

**Q: Linux 下 `pip install` 成功但 `import tkinter` 报 `ModuleNotFoundError`？**
A: Debian/Ubuntu 装系统包：`sudo apt install python3-tk`；CentOS/RHEL：`sudo yum install python3-tkinter`；Arch：`sudo pacman -S tk`。

**Q: 怎么导出巡检结果？**
A: 巡检完成后，点右上角 📊 导出结果 → 选 `.xlsx` 保存。`InspectionLogs/<日期>/<设备>_<IP>_<时间>.txt` 是每台设备的原始日志。

**Q: 高对比度模式不生效？**
A: 按 Ctrl+H 切换后窗口颜色应立即变化。本版本已修，会遍历 widget 树刷新所有颜色。如果还不行，关掉重启程序。

**Q: 想批量停掉正在巡检的设备？**
A: 工具栏点 ⏹ 停止巡检，或 Ctrl+T。当前命令执行完毕后立即中断，未开始的设备不再执行。

## 📄 许可证

本项目以 [MIT License](LICENSE) 发布，仅供学习与交流使用，不得用于商业发布或未授权的运维操作。