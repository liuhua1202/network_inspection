# 网络设备巡检工具 · Network Device Inspector

[[[Version](https://img.shields.io/badge/version-v2.2.1-0078d4?style=flat-square)](#-变更摘要)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-0078d4?style=flat-square)](#-特性)
[![Python](https://img.shields.io/badge/python-3.8%2B-3776AB?style=flat-square)](https://www.python.org/)
[![Netmiko](https://img.shields.io/badge/netmiko-4.x-FF6F00?style=flat-square)](https://github.com/ktbyers/netmiko)
[![Tkinter](https://img.shields.io/badge/tkinter-builtin-2C5E8E?style=flat-square)](#-技术栈)

基于 Python + Tkinter 的网络设备批量巡检工具，支持 SSH / Telnet 协议、并发执行、结果导出 Excel、GBK / UTF-8 中文输出识别。

<img width="1402" height="932" alt="a271109efdce0bda8d6b5611055a81dd" src="https://github.com/user-attachments/assets/89e9f7ec-017e-427b-90f0-a5883ae63049" />



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
- 🛑 **优雅停止**（v2.1.2 改进）：随时停止巡检，**~500ms 内响应**，未完成的设备立即中断，不留后台残留
- 🪟 **任务栏图标**（v2.1.3 修复）：打包后 Windows 任务栏 / 标题栏 / 系统菜单正确显示 `favicon.ico`（地球+放大镜 logo），不再回退到 Tk 默认调色板

## 📦 下载

前往 [Releases 页面](https://github.com/liuhua1202/network_inspection/releases) 下载最新版（产物文件名带版本号）：

| 平台 | 文件 | 大小 | 说明 |
|---|---|---|---|
| Windows | [`NetworkInspector-v2.2.1.exe`](https://github.com/liuhua1202/network_inspection/releases/download/v2.2.1/NetworkInspector-v2.2.1.exe) | ~58 MB | 单文件便携版，零安装，双击即用 |
| 源码 | `Source code (zip)` / `Source code (tar.gz)` | — | GitHub 自动生成 |

**v2.2.1 SHA256**：
```
dd0e4f1b2730fa884db28b186bcf50e5e1ccf7fd5c8bce416e752318f6a3a389  NetworkInspector-v2.2.1.exe
```

> Windows：双击即用，无需安装。首次启动可能被 SmartScreen 拦截，点"更多信息 → 仍要运行"即可。  
> 校验：`Get-FileHash .\NetworkInspector-v2.2.1.exe -Algorithm SHA256`（PowerShell）或 `certutil -hashfile NetworkInspector-v2.2.1.exe SHA256`。

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
- 启动入口 `network_inspection.py`，业务拆为 `core/` + `ui/` + `utils/` 三层（v2.1.1 起模块化），无第三方 GUI 框架

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
├── network_inspection.py        # 启动入口 + 顶层 API 兼容层（v2.1.1 起拆模块）
├── favicon.ico                  # 窗口图标
├── requirements.txt             # 依赖清单
├── LICENSE                      # MIT
├── README.md                    # 本文件
├── .gitignore
├── core/                        # 业务逻辑
│   ├── config.py                # 设备 / 设备类型 / 命令文件解析
│   ├── encoding.py              # 编码检测 / 替换字符告警
│   ├── inspector.py             # 单台设备连接 + 命令执行
│   └── worker.py                # 巡检 worker + _safe_set_status + ProgressReporter
├── ui/                          # Tk GUI 层
│   ├── app.py                   # ModernNetworkInspectionUI（状态栏 / 日志 / 巡检收尾逻辑）
│   ├── theme.py                 # 主题 + LOG_COLORS 颜色表
│   └── widgets.py               # ModernButton / ModernEntry / DetailedProgressbar
├── utils/                       # 通用工具
│   ├── logging_setup.py         # LOG_QUEUE + 敏感字段脱敏
│   ├── paths.py                 # 项目目录常量
│   └── validation.py            # IP / 端口 / 文件名 sanitization
├── tests/                       # 单元测试
│   ├── test_pure_functions.py   # 纯函数单测（不依赖 Tk）
│   ├── test_refactor.py         # 模块拆分回归
│   └── test_full_verification.py# UI + 集成测试
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

## 📋 v2.2.1 变更摘要

相比 v2.2.0，v2.2.1 聚焦**图标稳定性与界面细节打磨**（均为 v2.2.0 发布后收集的反馈）。建议升级以获得更稳的图标渲染与更紧凑的布局。

### 🐛 修复

- **🛠 按钮图标偶发不显示**。根因是 `Canvas` 上的图标 `PhotoImage` 是局部变量，函数返回后被 Python 垃圾回收，导致按钮只剩文字。已在 `ModernButton` 中增加 `self._btn_icon_photo` 持久引用，图标稳定显示。
- **🛠 巡检配置齿轮图标看不见**。原线描笔画过细且 PIL 绘制未用 `p()` 缩放，只画出 6×6 的小点。重绘为**实心 8 齿剪影**，标题与配置项前清晰可见。

### ✨ UI 改进

- **🔧 配置项图标高度对齐文字**。`make_icon_label` 新增 `match_text_height`，CPU / 命令 / 时钟 / 日志等级等配置项图标高度与同行文字一致，不再错位。
- **🗑 清空按钮图标去背景**。设备列表「清空」与日志面板「清空」的图标由浅蓝圆角底改为**透明背景单色（ACCENT 蓝）**，与同排「全选 / 反选」Linear 图标视觉统一。
- **⏯ 开始 / 停止巡检按钮等宽**（均 140px），视觉更平衡。
- **📊 KPI 三张卡片重排**：改为**横向排版**，数值与文字说明并排；卡片高度由 ~156px 缩至 ~75px（≈ 原 1/2），充分利用顶部空间、减少纵向占用。
- **🪟 窗口默认尺寸 1350×860、最小 1000×600**，更适配主流笔记本屏。

### 🔧 交互

- **并发线程数越界保护**。并发数 Spinbox 失焦时若超出允许范围（1–50）或非法，自动重置为默认值 `5` 并弹窗提示，避免误填导致巡检异常。

### 🧪 验证

- 全部 Python 文件 `py_compile` 通过，`import ui.app` 通过
- 图标渲染目检：清空按钮透明图标、齿轮剪影、配置项等高图标均正常
- KPI 横向并排布局 + 半高卡片经窗口截图确认

---

## 📋 v2.2.0 变更摘要

相比 v2.1.3，v2.2.0 是一次**视觉与体验重构**：去除 emoji、改用 PIL 矢量图标、加入 KPI 统计卡片、修复 Py 3.14 下的线程崩溃。**强烈建议升级**（界面与稳定性均有显著提升）。

### ✨ 视觉与体验

- **🔤 去 emoji，改 PIL 矢量图标**（ui-ux-pro-max 推荐）。所有 emoji（🚀 📊 📁 🔍 ⏹ 等）替换为 PIL 绘制的 24 个矢量图标（`ui/widgets.py:IconLibrary`）。图标跟随主题色，无字体依赖、跨平台一致。PIL 不可用时优雅降级到 Unicode 字符。
- **🟦 按钮圆角像素级平滑**（`ModernButton._render_button_bg`）。8× 超采样 + 1px padding + LANCZOS 高质量重采样，Canvas 端整数像素 + .5 偏移定位，彻底消除边缘锯齿。
- **📊 顶部 3 张 KPI 统计卡片**（`StatCard`）。设备总数 / 已选设备 / 当前巡检中设备实时统计，accent 渐变色条 + 大字号数值（28px bold）+ 趋势说明。
- **✅ 设备列表勾选框矢量改造**。从 Unicode 字符（☑/☐）改为 PIL 矢量圆角勾选框（蓝底白勾 / 白底灰描边），不依赖系统字体。
- **🏷 头部图标**：设备列表（list）/ 运行日志（doc，terminal 风格）/ 各配置项（cpu / code / clock / level），所有图标 + 文字在 `make_icon_label` 辅助下统一布局。
- **🔧 工具栏配置项 inline**。把"巡检配置"独立卡片合并到工具栏：开始巡检 / 停止巡检 | 并发数 / 输出编码 / 连接超时 / 日志等级 | 导出结果 / 统计报告 / 日志目录，节省垂直空间。
- **🎨 主题切换**。高对比度模式（Ctrl+H）下，所有颜色（含按钮、勾选框、图标）都自动重新生成。

### 🐛 修复

- **🛠 Py 3.14 + Tk 8.6 严格线程模型下 worker 线程调用 widget 崩溃**。原 `auto_load_default_configs` 用 `root.after(0, ...)` 派发 UI 更新，Py 3.14 抛 `RuntimeError: main thread is not in main loop`，fallback 同步调用又导致"主线程派发 UI 约束"崩溃，状态栏永远卡在"正在加载配置文件..."。改用 **thread-safe `Event` + main-thread 轮询** 模式（`_schedule_config_load_check` 每 100ms 检查一次），UI 更新始终在 main 线程。
- **🛠 设备列表 checkbox 点击区域**。从"任意列切换"改为"仅点击 #0 列切换"（避免误操作 + 更符合 Treeview 交互习惯）。
- **🛠 日志区背景透明**。`Text` 控件 `bg` 改为与卡片的浅冷灰色（`#fbfcfe`）形成层次。

### 🔧 重构

- **`ui/widgets.py`**：完整重写 `ModernButton`（Canvas-based + PIL 圆角 + icon 参数 + 完整状态机），新增 `IconLibrary`（17 个原始图标 + 7 个新增配置图标 = 24 个）、`make_icon_label`（icon + text 横向布局辅助）、`StatCard`（KPI 卡片）、`StatusIndicator`（运行状态灯）。
- **`ui/app.py`**：重写 `create_ui`（main 布局）、`create_toolbar`（inline 配置项）、`create_stats_row`、`_make_card`（Canvas 圆角卡片）、`_create_selection_images` / `_checkbox_glyph` / `_refresh_device_checkbox_images`（PIL 勾选框）。

### 🧪 验证

- 90 测试全过：50 pure + 28 refactor + 12 full verification（含 `test_select_all` / `test_deselect_all` / `test_invert` / `test_search_by_ip_substring` / `test_theme_toggle_twice_idempotent` / `test_theme_toggle_keeps_widgets_responsive`）
- 配置加载流程 smoke test：100 台设备全部加载，状态栏最终显示"所有配置加载完成"
- 图标渲染 smoke test：24 个 IconLibrary 图标全部成功渲染
- 按钮 AA smoke test：8× 超采样后圆角边缘像素级平滑，无可见锯齿

### 📦 升级说明

- 配置文件（`config/*.csv` / `config/*.txt`）兼容，无需迁移
- 设备列表 CSV 列顺序不变
- 命令文件 `# @heavy` / `# @timeout N` 标记继续支持
- **旧 exe 卸载即可**，新 exe 直接覆盖运行（不依赖注册表 / 用户配置目录）

---

## 📋 v2.1.3 变更摘要

相比 v2.1.2，本版本专修"Windows 任务栏图标不对"这一项。

### 🐛 修复

- **打包后任务栏 / 标题栏 / 系统菜单显示 Tk 默认调色板图标**（而不是项目的 `favicon.ico`）
  - **根因 1：仅用 `iconbitmap()` 不够**。`Tk.iconbitmap` 内部只设 `WM_SETICON`（per-window icon），不会改 `WNDCLASSEX.HICON`（class icon）。Win10/11 任务栏非合并模式 + 系统菜单走的都是 class icon。
  - **根因 2：HWND 拿错**。文档里说"用 `wm frame` 拿 top-level HWND（class `TkTopLevel`）"，那是老版本 Tk 的行为。在 Py 3.14 + Tk 8.6 + Win11 上，`winfo_id()` / `wm frame` 在 `update()` 之前返回的是同一个窗口（class `TkChild`），`update()` 之后才分离出 `TkTopLevel` 真正的 Windows top-level wrapper。
  - **根因 3：Tk 会在 `Toplevel.__init__` / paint 事件里用 `SetClassLongPtr` 把 class icon 改回默认**。设一次不够，要 60 秒 `after()` 链持续重设。

### ✨ 新增

- **`ui/icon_helper.py`**（~190 行）
  - `apply_icon(window)`：跨平台入口（macOS/Linux 走 `iconphoto`；Windows 再走 `iconbitmap` + Win32 强设 + 60 秒 retry 链）
  - `_apply_icon_win32(window, ico_path)`：直接调 `user32.dll` 强设 `WM_SETICON` + `SetClassLongPtrW`（HICON / HICONSM）
  - HWND 拿法兼容老 / 新 Tk：先 `wm frame`，fallback `winfo_id()`；用 `GetParent==0 AND GetAncestor(GA_PARENT).class=="#32769"` 判定是 top-level
- **多分辨率 `favicon.ico`**：原本只有 1 帧 64x64 → 现在 6 帧 16/32/48/64/128/256（手写 ICO header，PNG-in-ICO 编码），覆盖任务栏 16/32、系统菜单 16、资源管理器 48、高分屏 256
- **PyInstaller `--icon` 嵌入 exe 资源**：之前 `icon=...` 是注释掉的，现在启用，`[System.Drawing.Icon]::ExtractAssociatedIcon` 抽出来是网络设备 logo（地球+放大镜）

### ✨ UI 改进

- 3 个顶层窗口全部设图标：主窗口 + "配置设备类型命令文件"对话框 + "设备连通性测试"进度对话框
- `apply_icon(self.root)` 放在 `create_ui()` 之后（widget 全部就位 + Tk 已创建 `wm frame` 真正的 top-level），retry 链在 50ms / 150ms / 300ms / 600ms / 1.2s / 2.5s / 5s / 10s / 20s / 35s / 50s / 60s 各重设一次

### 🔧 重构

- `icon_helper` 用 ctypes 强类型签名（`argtypes` / `restype`），64-bit Python 不配会 crash 在 stdcall 栈错位的问题彻底解决
- `utils/paths.PROJECT_ROOT` 已自动处理 `_MEIPASS`（PyInstaller `--onefile` 模式），`icon_helper` 直接用它定位 `favicon.ico`，源码 / 打包行为一致

### 🧪 验证

- 进程内 `apply_icon` 调用前后 `GCLP_HICON`：从 `0x286419b9`（Tk 默认）→ `0x69d811f7`（我们的 favicon HICON）
- `ExtractAssociatedIcon("NetworkInspector-v2.1.3.exe")` 抽出 32x32 像素，正是网络设备 logo
- 130 测试全过（50 pure + 28 refactor + 52 full verification）

### ⚠️ Windows 图标缓存

代码改对了任务栏还显示旧图标？Windows 按 exe 路径缓存图标：
- 任务栏右键"取消固定 → 重新固定"
- 或 PowerShell 管理员：`Stop-Process -Name explorer -Force; Start-Process explorer`
- 或换个文件名 / 路径运行

不影响功能，只影响显示。

---

## 📋 v2.1.2 变更摘要

相比 v2.1.1，本版本聚焦"停止响应速度 + 状态条交互"两块体验：

### 🐛 修复

- **停止按钮要等 10-60s 才反应**：Netmiko 的 `send_command` / `enable` / `ConnectHandler` 都是阻塞 socket IO，stop_event 检查只在两条命令之间，进入后最多要等满 `read_timeout`（普通命令 60s、heavy 180s、显式覆盖 120s）。这版把 `time.sleep(2)` / `enable()` / `ConnectHandler` 全部用 daemon 线程包一层，stop 一 set 立刻 disconnect 关 socket 让阻塞 IO 失败，主线程最多等 100-300ms 返回。
- **死连接上 `disconnect()` 自身可能挂 OS TCP 超时**：单独抽出 `_disconnect_fast(timeout=0.3)` 封顶，外层 `finally` 也走这个。
- **`runner.join(timeout=1.0)` 兜底太长**：收到 stop 信号后 disconnect 完只多等 0.2s 让 runner 收尾，超时直接返回。

实测 stop 响应链路：用户点停止 → 100-300ms 内所有 worker 退出 → UI 按钮翻转。总感知延迟约 **300-500ms**（其中 500ms 来自 `check_inspection_complete` 轮询上限）。

### ✨ 新增

- **`TestInterruptibleSleep` / `TestEnableInterruptible` / `TestConnectHandlerInterruptible` / `TestDisconnectFast`**：4 个新测试类共 10 用例，覆盖所有补好的阻塞点的可中断契约（模拟 5-30s 长耗时，stop 后必须 < 1s 返回）
- **`_interruptible_sleep(seconds, stop_event)`**：100ms 分段 poll 的 `time.sleep` 替代品
- **`_enable_interruptible` / `_connect_handler_interruptible` / `_disconnect_fast`**：所有阻塞 IO 包装的统一 helper

### ✨ UI 改进

- **状态栏进度条前进动画**：`DetailedProgressbar` 内部 `progress_var` 从 `IntVar` 换成 `DoubleVar`（IntVar 截断小数让 60fps 步进变成 5% 一格的整数跳）。`set_progress` 收到前进值（target > current）启动 320ms 60fps 缓动；后退 / 重置（target ≤ current）直接 snap 不回弹。巡检进度从"跳跃感"变成"平滑过渡"。
- **`destroy()` 拦截**：进度条销毁前清掉 in-flight 的 `after` 帧，避免 widget 销毁后 Tk 报 `invalid command name` 噪音

### 🔧 重构

- `_send_command_interruptible` 重构成 `_run_on_conn_interruptible` 通用包装，`send_command` / `enable` 都委托给它，一处维护
- `connect_with_retry` 改用 `_connect_handler_interruptible`，异常用 `isinstance(exc, NetMikoTimeoutException)` 分发，不再靠字符串匹配

---

## 📋 v2.1.1 变更摘要

相比 v2.1，本版本聚焦"日志着色 + 跨线程稳定性"两块：

### 🐛 修复

- **运行日志总结行颜色跟随失败数**：巡检完成 / 巡检已停止 / 巡检收尾 / 命令文件关联完成等行，原来的文本都含 "失败" 关键字，被 `_detect_log_level` 一律判成 ERROR 红。现在 worker 显式打 `[SUCCESS]` / `[ERROR]` 前缀 —— `failed_total == 0` 走绿，`failed_total > 0` 走红。结果：用户最关心的"全成功"反馈一眼可见。
- **"全中断" 场景下两条总结行颜色对打脸**：之前 worker "巡检已停止" 红而 app "巡检收尾" 绿（因为后者没把 interrupted 算进失败）。现在两边一致：中断 ≥ 1 → 红。
- **worker 跨线程崩 `status_var.set` 静默挂死**：5 处裸奔的 `status_var.set()` 在新版 Tk（Py3.12+ / Tcl 8.6.13+）抛 `RuntimeError: main thread is not in main loop`。新增 `_safe_set_status` helper 集中 swallow，worker 不再因为状态栏写不进去而 crash。
- **SUCCESS 优先级太低，WARNING/ERROR 过滤模式吞掉绿总结行**：把 SUCCESS 升到 ERROR 同级（priority 3），保证"全成功"在最高过滤级别下也可见。
- **敏感字段脱敏覆盖到 LOG_QUEUE**：之前 `log_error(traceback_str)` 这一路只会经过 `_redact_sensitive`，而 LOG_QUEUE 上的日志还有没脱敏的尾巴。`debug_log` 入口统一脱敏。

### ✨ 新增

- `TestSummaryLineLevelTag`（5 用例）：覆盖 `all success / all fail / mixed / all interrupted / _detect_log_level` 前缀契约
- `TestStatusVarThreadSafety`（4 用例）：`_safe_set_status` 单元 + 端到端（status_var 每个 set 都炸时 worker 仍能跑完）
- `TestSuccessLogLevelPriority`（4 用例）：各级别过滤器的 SUCCESS 可见性契约
- 模块拆分：单文件 `network_inspection.py` 拆成 `core/` `ui/` `utils/`，顶层文件仅做向后兼容

### 🔧 重构

- `_run_inspection_worker` 抽出 `summary_level = "ERROR" if failed_total > 0 else "SUCCESS"`，与 `[LEVEL]` 前缀约定联动
- 检查器线程、连通性测试、主巡检各自用本地 `threading.Event()`，全局停止事件共享的历史坑彻底清除（沿用 v2.1 的修复）

---

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

**Q: 任务栏 / 标题栏图标不对（显示 Tk 默认彩色方块而不是网络设备 logo）？**
A: **v2.1.3 已修**。多分辨率 favicon.ico（16/32/48/64/128/256）+ `ui/icon_helper.py` 跨层强设 WM_SETICON + SetClassLongPtrW + 60 秒 retry 链。如果升级后还看到旧图标：Windows 按 exe 路径缓存图标 → 任务栏右键"取消固定→重新固定"或 PowerShell 跑 `Stop-Process -Name explorer -Force; Start-Process explorer` 清缓存，或换个文件夹名跑新 exe。

**Q: 想批量停掉正在巡检的设备？**
A: 工具栏点 ⏹ 停止巡检，或 Ctrl+T。**v2.1.2 起停止响应从原本的 10-60s 降到 ~500ms** —— Netmiko 的阻塞 IO（send_command / enable / ConnectHandler）全部用 daemon 线程包了可中断包装，stop 一 set 立刻 disconnect 关 socket，让阻塞 IO 立即返回。未开始的设备不再执行。

## 📄 许可证

本项目以 [MIT License](LICENSE) 发布，仅供学习与交流使用，不得用于商业发布或未授权的运维操作。
