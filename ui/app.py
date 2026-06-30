"""主 UI 类 —— ModernNetworkInspectionUI。

变更要点（相对于 v2.1 单文件版）：
- ``stop_event`` 改为实例属性 ``self._stop_event``，不再用模块全局，避免与
  连通性测试对话框的局部 ``test_stop_event`` 互相串扰。
- 进度上报统一走 ``core.worker.make_progress_reporter``，消除
  ``hasattr(progress_var, 'set_progress')`` 鸭子类型。
- 业务逻辑（config / inspector / worker）下沉到 ``core``，UI 只负责装配。
"""
import os
import sys
import threading
import time
import queue
import tkinter as tk
from tkinter import Tk, Frame, Label, Text, Scrollbar, ttk, StringVar, IntVar, filedialog, messagebox
from tkinter.ttk import Treeview
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from utils.paths import CONFIG_DIR, COMMANDS_DIR, project_log_root
from utils.logging_setup import (
    LOG_QUEUE, setup_logging, log_info, log_error, debug_log,
)
from core.config import (
    load_devices, load_device_types_config, parse_commands_file,
    validate_device_types_config, validate_devices_config,
    validate_devices_config_with_details, validate_commands_config,
    validate_config_file, is_comment_line, _parse_selected,
)
from core.encoding import detect_file_encoding
from core.inspector import (
    connect_and_execute, connect_with_retry,
    NETMIKO_AVAILABLE, missing_netmiko_message,
)
from core.worker import (
    inspection_worker, make_progress_reporter,
    ProgressReporter, DetailedProgressbarAdapter, IntVarProgressReporter,
)
from ui.theme import (
    theme_manager, FONT_FAMILY_UI, FONT_FAMILY_CODE,
    WINDOW_WIDTH, WINDOW_HEIGHT, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    PADDING_X, PADDING_Y, CARD_PADDING, COMPONENT_GAP,
    CONNECTIVITY_TIMEOUT_SECONDS, LOG_COLORS,
)
from ui.widgets import ModernButton, ModernEntry, DetailedProgressbar, LogTag

# 可选的导出依赖
try:
    import pandas as _pd_check
    import openpyxl as _openpyxl_check
    PANDAS_AVAILABLE = True
    missing_pandas_message = ''
except ImportError as e:
    PANDAS_AVAILABLE = False
    missing_pandas_message = str(e)


def _default_device_types_file():
    if os.path.exists(os.path.join(CONFIG_DIR, 'device_types.csv')):
        return os.path.join(CONFIG_DIR, 'device_types.csv')
    if os.path.exists(os.path.join(CONFIG_DIR, 'device_types.txt')):
        return os.path.join(CONFIG_DIR, 'device_types.txt')
    return ''


def _default_devices_file():
    if os.path.exists(os.path.join(CONFIG_DIR, 'devices.csv')):
        return os.path.join(CONFIG_DIR, 'devices.csv')
    if os.path.exists(os.path.join(CONFIG_DIR, 'devices.txt')):
        return os.path.join(CONFIG_DIR, 'devices.txt')
    return ''


class ModernNetworkInspectionUI:
    """网络设备巡检工具"""

    def __init__(self, root):
        debug_log("初始化UI")
        self.root = root
        self.root.title("网络设备自动巡检工具 v2.1.1 | Network Device Inspector")

        # 窗口图标
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "favicon.ico")
            icon_path = os.path.abspath(icon_path)
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except Exception:
            pass

        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.root.configure(bg=theme_manager.get_color('BG_PRIMARY'))

        # ============== 实例级状态 ==============
        # 停止信号 —— 替代原来模块全局 ``stop_event``
        # 每次启动巡检前 ``.clear()``，停止时 ``.set()``
        self._stop_event = threading.Event()
        self._inspection_lock = threading.Lock()  # 预留给将来 inspection_results 的多线程保护

        self.device_types = {}
        self.devices = []
        self.original_devices = []
        self.command_files = {}
        self.device_types_file = ""
        self.devices_file = ""
        self.encodings_config = ['gbk', 'gb2312', 'gb18030', 'utf-8', 'cp936', 'iso-8859-1']
        self.encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'cp936', 'iso-8859-1']
        self.inspection_running = False
        self.device_check_vars = {}
        self.search_var = None
        self.search_entry = None
        self._search_timer = None

        # 主题切换需要：所有 ModernButton 实例列表
        self._modern_buttons = []

        # 统计信息
        self.completed_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.total_duration = 0
        self.avg_response_time = 0
        self.success_rate = 0
        self.inspection_results = []

        self.create_menu()
        self.create_ui()
        self.root.after(100, self.update_log)
        self.root.after(200, self.init_config_and_load_defaults)

    # ==================== 菜单 ====================

    def create_menu(self):
        self.menubar = tk.Menu(self.root, bg=theme_manager.get_color('BG_CARD'),
                               fg=theme_manager.get_color('FG_PRIMARY'))
        self.root.config(menu=self.menubar)

        file_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'),
                            fg=theme_manager.get_color('FG_PRIMARY'),
                            activebackground=theme_manager.get_color('ACCENT'),
                            activeforeground='#ffffff')
        self.menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="开始巡检 (Ctrl+S)", command=self.start_inspection)
        file_menu.add_command(label="停止巡检 (Ctrl+T)", command=self.stop_inspection)
        file_menu.add_separator()
        file_menu.add_command(label="退出 (Ctrl+Q)", command=self.root.quit)

        settings_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'),
                                fg=theme_manager.get_color('FG_PRIMARY'),
                                activebackground=theme_manager.get_color('ACCENT'),
                                activeforeground='#ffffff')
        self.menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="加载设备列表", command=self.load_devices)
        settings_menu.add_command(label="加载设备类型", command=self.load_device_types)
        settings_menu.add_command(label="配置设备命令", command=self.configure_commands)
        settings_menu.add_separator()
        settings_menu.add_command(label="测试设备连通性", command=self.test_device_connectivity)

        about_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'),
                             fg=theme_manager.get_color('FG_PRIMARY'),
                             activebackground=theme_manager.get_color('ACCENT'),
                             activeforeground='#ffffff')
        self.menubar.add_cascade(label="关于", menu=about_menu)
        about_menu.add_command(label="配置使用指南", command=self.show_config_guide)
        about_menu.add_command(label="关于软件", command=self.show_about)

        self.root.bind('<Control-s>', lambda e: self.start_inspection())
        self.root.bind('<Control-t>', lambda e: self.stop_inspection())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<F1>', lambda e: self.show_shortcuts_help())
        self.root.bind('<Control-h>', lambda e: self.toggle_high_contrast())
        self.root.bind('<Tab>', self._handle_tab_navigation)
        self.root.after(100, self._set_initial_focus)

    def _set_initial_focus(self):
        try:
            self.start_btn.focus_set()
        except Exception:
            pass

    def _handle_tab_navigation(self, event):
        """Tab 键在主要交互控件间循环。"""
        current_widget = self.root.focus_get()
        focus_order = [
            self.start_btn, self.stop_btn, self.log_dir_btn,
            self.select_all_btn, self.invert_btn, self.deselect_btn,
            self.search_entry, self.device_tree,
            self.copy_log_btn, self.export_log_btn, self.clear_log_btn,
            self.log_text,
            self.concurrency_spinbox, self.encoding_combobox,
            self.timeout_combobox, self.log_level_combobox,
        ]
        try:
            current_idx = -1
            for i, widget in enumerate(focus_order):
                if hasattr(widget, 'winfo_exists') and widget.winfo_exists() and current_widget == widget:
                    current_idx = i
                    break
            next_idx = (current_idx + 1) % len(focus_order)
            for i in range(len(focus_order)):
                idx = (next_idx + i) % len(focus_order)
                widget = focus_order[idx]
                if hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                    try:
                        widget.focus_set()
                        break
                    except Exception:
                        continue
        except Exception:
            try:
                self.start_btn.focus_set()
            except Exception:
                pass
        return "break"

    # ==================== 布局 ====================

    def create_ui(self):
        main_container = Frame(self.root, bg=theme_manager.get_color('BG_PRIMARY'))
        main_container.pack(fill='both', expand=True, padx=16, pady=12)

        self.create_header_section(main_container)
        self.create_toolbar(main_container)
        # 巡检配置移到工具栏下方、设备/日志分栏之前（用户要求）
        self.create_config_section(main_container)

        content_frame = Frame(main_container, bg=theme_manager.get_color('BG_PRIMARY'))
        content_frame.pack(fill='both', expand=True, pady=12)

        left_panel = Frame(content_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 6))
        self.create_device_panel(left_panel)

        right_panel = Frame(content_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        right_panel.pack(side='left', fill='both', expand=True, padx=(6, 0))
        self.create_log_panel(right_panel)

        # 进度条状态栏已挪到 create_log_panel 内（用户要求融入运行日志框体下方）

    def create_header_section(self, parent):
        header_frame = Frame(parent, bg=theme_manager.get_color('BG_SECONDARY'))
        header_frame.pack(fill='x', pady=(0, 8))
        inner_frame = Frame(header_frame, bg=theme_manager.get_color('BG_SECONDARY'))
        inner_frame.pack(fill='x', padx=20, pady=16)
        Label(inner_frame, text="网络设备自动巡检工具",
              font=(FONT_FAMILY_UI, 18, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=theme_manager.get_color('BG_SECONDARY')).pack(anchor='w')
        Label(inner_frame,
              text="Network Device Inspector v2.1.1",
              font=(FONT_FAMILY_UI, 10),
              fg=theme_manager.get_color('FG_SECONDARY'),
              bg=theme_manager.get_color('BG_SECONDARY')).pack(anchor='w', pady=(4, 0))

    def create_toolbar(self, parent):
        toolbar_frame = Frame(parent, bg=theme_manager.get_color('BG_PRIMARY'))
        toolbar_frame.pack(fill='x', pady=(0, 8))

        left_controls = Frame(toolbar_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        left_controls.pack(side='left')

        self.start_btn = ModernButton(left_controls, "🚀 开始巡检", self.start_inspection,
                                      variant='secondary', width=140, height=38,
                                      aria_label="开始巡检按钮，用于启动网络设备巡检流程")
        self.start_btn.pack(side='left', padx=(0, 8))
        self.stop_btn = ModernButton(left_controls, "⏹ 停止巡检", self.stop_inspection,
                                     variant='secondary', width=120, height=38, state='disabled',
                                     aria_label="停止巡检按钮，用于中断正在进行的网络设备巡检")
        self.stop_btn.pack(side='left', padx=(0, 8))

        right_controls = Frame(toolbar_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        right_controls.pack(side='right')
        self.export_results_btn = ModernButton(right_controls, "📊 导出结果", self.export_results,
                                               variant='secondary', width=110, height=36,
                                               aria_label="导出结果按钮，用于将巡检结果导出为Excel文件")
        self.export_results_btn.pack(side='left', padx=(8, 0))
        self.stats_report_btn = ModernButton(right_controls, "📈 统计报告", self.generate_statistics_report,
                                             variant='secondary', width=110, height=36,
                                             aria_label="统计报告按钮，用于生成巡检统计报告")
        self.stats_report_btn.pack(side='left', padx=(8, 0))
        self.log_dir_btn = ModernButton(right_controls, "📁 日志目录", self.open_log_directory,
                                        variant='secondary', width=110, height=36,
                                        aria_label="打开日志目录按钮，用于打开存储巡检日志的文件夹")
        self.log_dir_btn.pack(side='left', padx=(8, 0))

    def create_device_panel(self, parent):
        device_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        device_card.pack(fill='both', expand=True, side='top')

        header_frame = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        header_frame.pack(fill='x', padx=16, pady=(16, 8))

        Label(header_frame, text="📋 设备列表",
              font=(FONT_FAMILY_UI, 14, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left')

        btn_frame = Frame(header_frame, bg=theme_manager.get_color('BG_CARD'))
        btn_frame.pack(side='right')

        self.select_all_btn = ModernButton(btn_frame, "全选", self.select_all_devices,
                                           variant='secondary', width=60, height=30,
                                           aria_label="全选按钮")
        self.select_all_btn.pack(side='left', padx=4)
        self.invert_btn = ModernButton(btn_frame, "反选", self.invert_select_devices,
                                       variant='secondary', width=60, height=30,
                                       aria_label="反选按钮")
        self.invert_btn.pack(side='left', padx=4)
        self.deselect_btn = ModernButton(btn_frame, "清空", self.deselect_all_devices,
                                         variant='secondary', width=60, height=30,
                                         aria_label="清空按钮")
        self.deselect_btn.pack(side='left', padx=4)

        search_frame = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        search_frame.pack(fill='x', padx=16, pady=(0, 8))

        self.search_var = StringVar()
        self.search_var.trace_add('write', self._on_search_changed)
        self.search_entry = ModernEntry(search_frame,
                                        placeholder="🔍 搜索设备名称、IP地址、设备类型...",
                                        width=40, font=(FONT_FAMILY_UI, 11),
                                        textvariable=self.search_var)
        self.search_entry.pack(side='left', fill='x', expand=True)

        list_container = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        list_container.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        columns = ('select', 'device_name', 'ip', 'device_type', 'protocol')
        self.device_tree = Treeview(list_container, columns=columns, show='headings',
                                    style='DeviceTree.Treeview', selectmode='none')
        self.device_tree.heading('select', text='选择', anchor='center')
        self.device_tree.heading('device_name', text='设备名称', anchor='w')
        self.device_tree.heading('ip', text='IP 地址', anchor='w')
        self.device_tree.heading('device_type', text='设备类型', anchor='w')
        self.device_tree.heading('protocol', text='协议', anchor='center')
        self.device_tree.column('select', width=50, anchor='center')
        self.device_tree.column('device_name', width=140, anchor='w')
        self.device_tree.column('ip', width=130, anchor='w')
        self.device_tree.column('device_type', width=100, anchor='w')
        self.device_tree.column('protocol', width=70, anchor='center')

        scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)
        self.device_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('DeviceTree.Treeview',
                        background=theme_manager.get_color('BG_CARD'),
                        foreground=theme_manager.get_color('FG_PRIMARY'),
                        fieldbackground=theme_manager.get_color('BG_CARD'),
                        rowheight=36,
                        font=(FONT_FAMILY_UI, 10),
                        borderwidth=0,
                        relief='flat',
                        padding=(0, 4, 0, 4))
        style.configure('DeviceTree.Treeview.Heading',
                        background=theme_manager.get_color('BG_SECONDARY'),
                        foreground=theme_manager.get_color('FG_PRIMARY'),
                        font=(FONT_FAMILY_UI, 10, 'bold'),
                        relief='flat',
                        padding=(10, 8, 10, 8))
        style.map('DeviceTree.Treeview',
                  background=[('selected', theme_manager.get_color('ACCENT'))],
                  foreground=[('selected', '#ffffff')])
        style.configure('Treeview',
                        borderwidth=1,
                        focusthickness=1,
                        focuscolor=theme_manager.get_color('ACCENT'))

        self.device_tree.bind('<Button-1>', self.on_treeview_click)

    def create_log_panel(self, parent):
        log_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        log_card.pack(fill='both', expand=True, side='top')

        # 进度条状态栏：先 pack（side='bottom'，固定高度），再 pack 日志区（expand=True 占满剩余）
        self.create_status_bar(log_card)
        separator = Frame(log_card, bg=theme_manager.get_color('BORDER'), height=1)
        separator.pack(fill='x', side='bottom', padx=16)

        header_frame = Frame(log_card, bg=theme_manager.get_color('BG_CARD'))
        header_frame.pack(fill='x', padx=16, pady=(16, 8))

        Label(header_frame, text="📝 运行日志",
              font=(FONT_FAMILY_UI, 14, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left')

        btn_frame = Frame(header_frame, bg=theme_manager.get_color('BG_CARD'))
        btn_frame.pack(side='right')
        self.copy_log_btn = ModernButton(btn_frame, "📋 复制", self.copy_log,
                                         variant='secondary', width=70, height=30,
                                         aria_label="复制日志按钮")
        self.copy_log_btn.pack(side='left', padx=4)
        self.export_log_btn = ModernButton(btn_frame, "💾 导出", self.export_log,
                                           variant='secondary', width=70, height=30,
                                           aria_label="导出日志按钮")
        self.export_log_btn.pack(side='left', padx=4)
        self.clear_log_btn = ModernButton(btn_frame, "🗑 清空", self.clear_log,
                                          variant='secondary', width=70, height=30,
                                          aria_label="清空日志按钮")
        self.clear_log_btn.pack(side='left', padx=4)

        text_container = Frame(log_card, bg=theme_manager.get_color('BG_CARD'))
        # expand=True 占满 status_bar 之上所有剩余空间
        text_container.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        self.log_text = Text(text_container,
                             wrap='word', state='disabled',
                             bg=theme_manager.get_color('BG_CARD'),
                             fg=theme_manager.get_color('FG_PRIMARY'),
                             font=(FONT_FAMILY_CODE, 10),
                             relief='flat', bd=0,
                             padx=12, pady=12, spacing1=2, spacing3=2,
                             insertbackground=theme_manager.get_color('ACCENT'),
                             selectbackground=theme_manager.get_color('ACCENT'),
                             selectforeground='#ffffff', cursor='arrow')
        scrollbar = ttk.Scrollbar(text_container, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 日志级别 tag 颜色
        for level, color in LOG_COLORS.items():
            self.log_text.tag_config(level, foreground=color)
        self.log_text.tag_config('timestamp', foreground=theme_manager.get_color('FG_MUTED'))

        style = ttk.Style()
        style.configure('Vertical.TScrollbar',
                        gripcount=0,
                        troughcolor=theme_manager.get_color('BG_DARK'),
                        background=theme_manager.get_color('ACCENT_LIGHT'),
                        arrowcolor=theme_manager.get_color('FG_MUTED'),
                        bordercolor=theme_manager.get_color('BG_DARK'),
                        lightcolor=theme_manager.get_color('BG_DARK'),
                        darkcolor=theme_manager.get_color('BG_DARK'))

    def create_config_section(self, parent):
        config_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        config_card.pack(fill='x', pady=(0, 8))

        Label(config_card, text="⚙️ 巡检配置",
              font=(FONT_FAMILY_UI, 13, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(anchor='w', padx=16, pady=(12, 8))

        config_frame = Frame(config_card, bg=theme_manager.get_color('BG_CARD'))
        config_frame.pack(fill='x', padx=16, pady=(0, 12))

        # 并发线程数
        Label(config_frame, text="并发线程数:", font=(FONT_FAMILY_UI, 11),
              fg=theme_manager.get_color('FG_SECONDARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left', padx=(0, 8))
        self.concurrency_var = StringVar(value="5")
        self.concurrency_spinbox = ttk.Spinbox(config_frame, from_=1, to=50, width=5,
                                               textvariable=self.concurrency_var,
                                               font=(FONT_FAMILY_UI, 11))
        self.concurrency_spinbox.pack(side='left', padx=(0, 24))

        # 输出编码
        Label(config_frame, text="输出编码:", font=(FONT_FAMILY_UI, 11),
              fg=theme_manager.get_color('FG_SECONDARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left', padx=(0, 8))
        self.encoding_var = StringVar(value="自动检测")
        encoding_options = ["自动检测", "UTF-8", "GBK", "GB2312", "GB18030", "Big5"]
        self.encoding_combobox = ttk.Combobox(config_frame, textvariable=self.encoding_var,
                                              values=encoding_options, state="readonly", width=10,
                                              font=(FONT_FAMILY_UI, 11))
        self.encoding_combobox.pack(side='left', padx=(0, 24))

        # 连接超时
        Label(config_frame, text="连接超时:", font=(FONT_FAMILY_UI, 11),
              fg=theme_manager.get_color('FG_SECONDARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left', padx=(0, 8))
        self.timeout_var = StringVar(value="30s")
        timeout_options = ["15s", "30s", "45s", "60s", "90s"]
        self.timeout_combobox = ttk.Combobox(config_frame, textvariable=self.timeout_var,
                                            values=timeout_options, state="readonly", width=6,
                                            font=(FONT_FAMILY_UI, 11))
        self.timeout_combobox.pack(side='left', padx=(0, 24))

        # 日志级别
        Label(config_frame, text="日志级别:", font=(FONT_FAMILY_UI, 11),
              fg=theme_manager.get_color('FG_SECONDARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='left', padx=(0, 8))
        self.log_level_var = StringVar(value="INFO")
        log_level_options = ["DEBUG", "INFO", "WARNING", "ERROR"]
        self.log_level_combobox = ttk.Combobox(config_frame, textvariable=self.log_level_var,
                                               values=log_level_options, state="readonly", width=8,
                                               font=(FONT_FAMILY_UI, 11))
        self.log_level_combobox.pack(side='left')
        self.min_log_level = self.log_level_var.get()
        self.log_level_combobox.bind('<<ComboboxSelected>>', self._on_log_level_changed)

    def create_status_bar(self, parent):
        # side='bottom'：确保 status_card 始终贴底；外层有 expand 控件时 Tk 会自动挤压
        status_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        status_card.pack(fill='x', side='bottom')
        # inner_frame 用 pady=8（缩小上下间距），让文字基线和进度条视觉对齐
        inner_frame = Frame(status_card, bg=theme_manager.get_color('BG_CARD'))
        inner_frame.pack(fill='x', padx=16, pady=8)

        # 统一字号 = 11（与正文一致），指示点和版本号不再用 16 / 9 撑高/缩
        common_font = (FONT_FAMILY_UI, 11)

        self.status_var = StringVar(value="正在加载配置...")
        self.status_label = Label(inner_frame, textvariable=self.status_var,
                                  font=common_font,
                                  fg=theme_manager.get_color('FG_SECONDARY'),
                                  bg=theme_manager.get_color('BG_CARD'))
        self.status_label.pack(side='left')

        # show_label=False：状态栏已有 status_var 显示文字，进度条本体即可
        self.progress_bar = DetailedProgressbar(inner_frame, show_label=False)
        self.progress_bar.pack(side='left', padx=(16, 0), fill='x', expand=True)

        # 指示点字号收紧到 12（小一档），避免撑高整行
        self.status_indicator = Label(inner_frame, text="●",
                                      font=(FONT_FAMILY_UI, 12),
                                      fg=theme_manager.get_color('INFO'),
                                      bg=theme_manager.get_color('BG_CARD'))
        self.status_indicator.pack(side='right', padx=(8, 0))

        Label(inner_frame, text="v2.1.1",
              font=(FONT_FAMILY_UI, 10),
              fg=theme_manager.get_color('FG_MUTED'),
              bg=theme_manager.get_color('BG_CARD')).pack(side='right', padx=(8, 0))

    # ==================== 配置加载 ====================

    def init_config_and_load_defaults(self):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.makedirs(COMMANDS_DIR, exist_ok=True)
            debug_log(f"配置目录：{CONFIG_DIR}")
            debug_log(f"命令目录：{COMMANDS_DIR}")

            self.status_var.set("正在加载配置文件...")
            threading.Thread(target=self.load_defaults_in_background, daemon=True).start()
        except Exception as e:
            msg = f"初始化配置目录失败：{e}"
            LOG_QUEUE.put(msg)
            debug_log(msg)
            self.status_var.set(f"初始化失败：{e}")

    def load_defaults_in_background(self):
        try:
            self.auto_load_default_configs()
        except Exception as e:
            msg = f"加载配置失败：{e}"
            LOG_QUEUE.put(msg)
            debug_log(msg)
            try:
                self.root.after(0, lambda: self.status_var.set(f"加载配置失败：{e}"))
            except (RuntimeError, tk.TclError):
                # Python 3.14+ Tk 严格线程模型：worker 线程调 after() 可能抛 RuntimeError
                # 兜底：直接 set（不破坏数据，只是违反"主线程派发 UI"约定）
                try:
                    self.status_var.set(f"加载配置失败：{e}")
                except Exception:
                    pass

    def auto_load_default_configs(self):
        success = True
        device_types_file = _default_device_types_file()
        devices_file = _default_devices_file()

        if device_types_file and os.path.exists(device_types_file):
            self.device_types = load_device_types_config(device_types_file, self.encodings_config)
            self.device_types_file = device_types_file
        else:
            LOG_QUEUE.put("未找到默认设备类型配置文件")
            success = False

        if devices_file and os.path.exists(devices_file):
            self.devices = load_devices(devices_file, self.encodings_config)
            self.original_devices = list(self.devices)
            self.devices_file = devices_file
        else:
            LOG_QUEUE.put("未找到默认设备列表配置文件")
            success = False

        self.auto_associate_commands_from_device_types()
        try:
            self.root.after(0, self._apply_loaded_config_ui, success)
        except (RuntimeError, tk.TclError):
            # Python 3.14+ Tk 严格线程模型：worker 线程调 after() 偶发 RuntimeError
            # 同步直接调，保留等价行为（数据已 load 到 self.*，UI 刷新本来就是兜底）
            debug_log("auto_load_default_configs: after() 派发失败，同步 _apply_loaded_config_ui 兜底")
            self._apply_loaded_config_ui(success)

    def _apply_loaded_config_ui(self, success):
        try:
            self.update_config_file_display()
            self.update_device_listbox()
            self.update_start_button_state()
            valid_dt = validate_device_types_config(self.device_types)
            valid_dev = validate_devices_config(self.devices, self.device_types) if self.devices else False
            valid_cmd = validate_commands_config(self.device_types, self.command_files)
            if success and valid_dt and valid_dev and valid_cmd:
                self.status_var.set("所有配置加载完成，可以开始巡检")
                self.update_status_indicator('success')
            else:
                self.status_var.set("部分配置缺失，请检查日志")
                self.update_status_indicator('warning')
        except Exception as e:
            debug_log(f"应用加载配置到 UI 失败：{e}")
            log_error(f"应用加载配置到 UI 失败：{e}")

    def auto_associate_commands_from_device_types(self):
        if not self.device_types:
            LOG_QUEUE.put("未加载设备类型配置，无法关联命令文件")
            return
        self.command_files.clear()
        loaded_count = 0
        failed_count = 0
        for type_id, config in self.device_types.items():
            cmd_file_name = config.get('commands_file', '').strip()
            if cmd_file_name:
                if self._load_command_file_for_type(type_id, cmd_file_name):
                    loaded_count += 1
                else:
                    failed_count += 1
            else:
                LOG_QUEUE.put(f"设备类型 {type_id} 未配置命令文件")
                failed_count += 1
        # 总结行：失败=0 走 SUCCESS（绿色），失败>0 走 ERROR（红色）。
        # 同核心 worker.py 的逻辑：原文本里就含"失败"字样，依赖关键字启发
        # 会被误判成 ERROR，所以这里显式打 [LEVEL] 前缀。
        link_level = "ERROR" if failed_count > 0 else "SUCCESS"
        LOG_QUEUE.put(
            f"[{link_level}] 命令文件关联完成：成功{loaded_count}个，失败{failed_count}个"
        )

    def _load_command_file_for_type(self, type_id, cmd_file_name):
        possible_paths = [
            cmd_file_name,
            os.path.join(COMMANDS_DIR, cmd_file_name),
            os.path.join(os.path.dirname(self.device_types_file), cmd_file_name) if self.device_types_file else None,
            os.path.join(os.getcwd(), 'config', 'commands', cmd_file_name),
        ]
        possible_paths = [p for p in possible_paths if p is not None]
        for path in possible_paths:
            if os.path.exists(path):
                commands = parse_commands_file(path, self.encodings)
                if commands:
                    self.command_files[type_id] = (path, commands)
                    LOG_QUEUE.put(f"成功关联设备类型 {type_id} 的命令文件：{cmd_file_name}")
                    return True
                else:
                    LOG_QUEUE.put(f"命令文件 {path} 存在但未找到有效命令")
                    return False
        LOG_QUEUE.put(f"设备类型 {type_id} 的命令文件不存在：{cmd_file_name}")
        return False

    def update_config_file_display(self):
        if self.device_types_file:
            display_path = self.shorten_path(self.device_types_file)
            LOG_QUEUE.put(f"设备类型配置：{display_path}")
        if self.devices_file:
            display_path = self.shorten_path(self.devices_file)
            LOG_QUEUE.put(f"设备列表配置：{display_path}")

    @staticmethod
    def shorten_path(path, max_length=50):
        if not path:
            return ""
        if len(path) <= max_length:
            return path
        head_length = int(max_length * 0.4)
        tail_length = max_length - head_length - 3
        return f"{path[:head_length]}...{path[-tail_length:]}"

    # ==================== 设备列表 ====================

    def update_device_listbox(self):
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)
        self.device_check_vars = {}
        # iid 用 ASCII 哈希（避免 v2.1 既有 bug：含中文的 iid 在某些 Tk 构建下 encode 失真）
        self._iid_to_device = {}

        if not self.devices:
            if not hasattr(self, 'original_devices') or not self.original_devices:
                self.device_tree.insert('', 'end', values=('', '请先加载设备列表', '', '', ''), tags=('empty',))
            else:
                self.device_tree.insert('', 'end', values=('', '无匹配的设备', '', '', ''), tags=('empty',))
            return

        for device in self.devices:
            device_type_id = device.get('device_type', '')
            type_name = self.device_types.get(device_type_id, {}).get('name', device_type_id)
            protocol = (device.get('protocol', '') or 'SSH').upper()
            port = device.get('port', 22)
            iid = self._make_iid(device)
            self._iid_to_device[iid] = device
            var = IntVar(value=1 if device.get('selected', True) else 0)
            self.device_check_vars[iid] = var
            checkbox_display = '☑' if device.get('selected', True) else '☐'
            self.device_tree.insert('', 'end', iid=iid, values=(
                checkbox_display, device['device_name'],
                f"{device['ip']}:{port}", type_name, protocol,
            ), tags=('device',))

    def on_treeview_click(self, event):
        region = self.device_tree.identify_region(event.x, event.y)
        if region in ('cell', 'tree'):
            item_id = self.device_tree.identify_row(event.y)
            if not item_id:
                return
            target_device = self._iid_to_device.get(item_id)
            if target_device is None:
                return
            new_state = not target_device.get('selected', True)
            target_device['selected'] = new_state
            if item_id in self.device_check_vars:
                self.device_check_vars[item_id].set(1 if new_state else 0)
            checkbox_display = '☑' if new_state else '☐'
            current_values = self.device_tree.item(item_id, 'values')
            if current_values:
                self.device_tree.item(item_id, values=(checkbox_display,) + current_values[1:])

    @staticmethod
    def _make_iid(device):
        """稳定 ASCII iid：MD5(设备名+IP) 前 12 位。

        不用原始 ``{name}_{ip}`` 是因为 v2.1 既有 bug：ttk iid 含中文时部分
        Tk 构建会 encode 成 GBK 字节，再读回时部分字符变成 U+FFFD，
        导致按字符串再查找失败（``_iid_to_device`` 找不到）。
        """
        import hashlib
        raw = f"{device.get('device_name', '')}_{device.get('ip', '')}"
        return hashlib.md5(raw.encode('utf-8')).hexdigest()[:12]

    def update_commands_listbox(self):
        """v2.1：UI 侧命令列表已通过 configure_commands 对话框管理，主界面不再显示"""
        return

    def select_all_devices(self):
        for device in self.devices:
            device['selected'] = True
        for var in self.device_check_vars.values():
            var.set(1)
        for item_id in self.device_tree.get_children():
            current_values = self.device_tree.item(item_id, 'values')
            if current_values:
                self.device_tree.item(item_id, values=('☑',) + current_values[1:])
        LOG_QUEUE.put("已全选所有设备")

    def deselect_all_devices(self):
        for device in self.devices:
            device['selected'] = False
        for var in self.device_check_vars.values():
            var.set(0)
        for item_id in self.device_tree.get_children():
            current_values = self.device_tree.item(item_id, 'values')
            if current_values:
                self.device_tree.item(item_id, values=('☐',) + current_values[1:])
        LOG_QUEUE.put("已清空所有设备选择")

    def invert_select_devices(self):
        for device in self.devices:
            device['selected'] = not device.get('selected', True)
        for var in self.device_check_vars.values():
            var.set(0 if var.get() == 1 else 1)
        for iid, device in self._iid_to_device.items():
            current_values = self.device_tree.item(iid, 'values')
            if current_values:
                checkbox_display = '☑' if device['selected'] else '☐'
                self.device_tree.item(iid, values=(checkbox_display,) + current_values[1:])
        LOG_QUEUE.put("已反选设备")

    def update_start_button_state(self):
        valid_dt = validate_device_types_config(self.device_types)
        valid_dev = validate_devices_config(self.devices, self.device_types) if self.devices else False
        valid_cmd = validate_commands_config(self.device_types, self.command_files)
        state = 'normal' if (valid_dt and valid_dev and valid_cmd) else 'disabled'
        self.start_btn.config(state=state)

    def update_status_indicator(self, status):
        colors = {
            'ready': theme_manager.get_color('FG_MUTED'),
            'running': theme_manager.get_color('ACCENT'),
            'success': theme_manager.get_color('SUCCESS'),
            'warning': theme_manager.get_color('WARNING'),
            'error': theme_manager.get_color('ERROR'),
        }
        color = colors.get(status, theme_manager.get_color('FG_MUTED'))
        self.status_indicator.config(fg=color)

    # ==================== 搜索 ====================

    def _on_search_changed(self, *args):
        if getattr(self, '_search_timer', None):
            try:
                self.root.after_cancel(self._search_timer)
            except Exception:
                pass
        self._search_timer = self.root.after(150, self._do_real_time_search)

    def _do_real_time_search(self):
        search_text = self.search_var.get()
        if not search_text or search_text == "🔍 搜索设备名称、IP地址、设备类型...":
            self._restore_original_devices()
            return
        self._filter_devices(search_text.lower())

    def _restore_original_devices(self):
        self.devices = list(self.original_devices)
        self.update_device_listbox()

    def _filter_devices(self, search_term):
        filtered = []
        for device in self.original_devices:
            device_type_id = device.get('device_type', '')
            type_name = self.device_types.get(device_type_id, {}).get('name', device_type_id)
            protocol = (device.get('protocol', '') or 'ssh').upper()
            protocol_port = f"{protocol}:{device.get('port', 22)}"
            if (search_term in device['device_name'].lower() or
                search_term in device['ip'].lower() or
                search_term in device_type_id.lower() or
                search_term in type_name.lower() or
                search_term in protocol_port.lower()):
                filtered.append(device)
        self.devices = filtered
        self.update_device_listbox()
        if filtered:
            self.device_tree.yview_moveto(0.0)

    # ==================== 日志 ====================

    def update_log(self):
        batch_size = 0
        max_batch = 50
        should_scroll = False
        log_entries = []
        while batch_size < max_batch:
            try:
                msg = LOG_QUEUE.get_nowait()
            except queue.Empty:
                break
            timestamp = datetime.now().strftime('%H:%M:%S')
            level = self._detect_log_level(msg)
            if not self._should_show_log_level(level):
                batch_size += 1
                LOG_QUEUE.task_done()
                continue
            log_entries.append((f"[{timestamp}] {msg}\n", level))
            batch_size += 1
            should_scroll = True
            LOG_QUEUE.task_done()
        if log_entries:
            self.log_text.config(state='normal')
            for line, level in log_entries:
                self.log_text.insert('end', line, level)
        if should_scroll:
            self.log_text.see('end')
            self._limit_log_lines(5000)
        self.root.after(100, self.update_log)

    def _should_show_log_level(self, level):
        # 优先级表。SUCCESS 故意提到 ERROR 同级 —— 巡检全部成功的"绿色总结"
        # 是用户最关心的关键正面反馈，不应该在 WARNING/ERROR 过滤模式下整行
        # 消失；这是用户提的核心诉求。代价：操作性的 [SUCCESS]/success-启发行
        # （如"已全选所有设备"）也跟着被放出。这倒不算坏，因为用户调试时本来
        # 也希望看到自己的操作是否成功落地。
        priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2,
                    'ERROR': 3, 'SUCCESS': 3, 'CRITICAL': 4}
        min_level = getattr(self, 'min_log_level', 'DEBUG')
        return priority.get(level, 1) >= priority.get(min_level, 0)

    def _on_log_level_changed(self, event=None):
        self.min_log_level = self.log_level_var.get()
        LOG_QUEUE.put(f"日志显示级别已更新为：{self.min_log_level}")

    @staticmethod
    def _detect_log_level(msg):
        """从日志文本中识别级别。"""
        if not isinstance(msg, str):
            return 'INFO'
        import re as _re
        m = _re.match(r'^\[(DEBUG|INFO|WARNING|ERROR|SUCCESS|CRITICAL)\]', msg)
        if m:
            return m.group(1)
        lower = msg.lower()
        if '失败' in msg or '错误' in msg or '异常' in msg or 'error' in lower or 'failed' in lower or 'exception' in lower:
            return 'ERROR'
        if '警告' in msg or 'warn' in lower:
            return 'WARNING'
        if '成功' in msg or 'success' in lower:
            return 'SUCCESS'
        if '调试' in msg or 'debug' in lower:
            return 'DEBUG'
        return 'INFO'

    def _limit_log_lines(self, max_lines=5000):
        try:
            current_lines = int(self.log_text.index('end-1c').split('.')[0])
            if current_lines > max_lines:
                self.log_text.config(state='normal')
                self.log_text.delete('1.0', f'{current_lines - max_lines}.0')
                self.log_text.config(state='disabled')
        except Exception:
            pass

    def copy_log(self):
        content = self.log_text.get('1.0', 'end')
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        LOG_QUEUE.put("日志已复制到剪贴板")

    def export_log(self):
        file_path = filedialog.asksaveasfilename(
            title="导出日志", defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")])
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.log_text.get('1.0', 'end'))
                LOG_QUEUE.put(f"日志已导出：{file_path}")
            except Exception as e:
                log_error(f"导出日志失败：{e}")

    def clear_log(self):
        if messagebox.askyesno("确认", "确定要清空日志吗？"):
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', 'end')
            self.log_text.config(state='disabled')
            LOG_QUEUE.put("日志已清空")

    # ==================== 菜单功能 ====================

    def show_shortcuts_help(self):
        messagebox.showinfo("快捷键帮助", """快捷键帮助

通用快捷键：
• Ctrl+S : 开始巡检
• Ctrl+T : 停止巡检
• Ctrl+Q : 退出程序
• Ctrl+H : 切换高对比度模式
• F1 : 显示快捷键帮助
• Tab : 在界面元素间切换焦点

功能说明：
• 使用Tab键可在各按钮、输入框、列表间导航
• 空格键可激活当前焦点的按钮
• 设备列表中可通过上下箭头键选择设备""")

    def show_about(self):
        messagebox.showinfo("关于软件", """网络设备自动巡检工具 v2.1.1

主要功能：
• 支持多厂商设备（华为、思科、H3C、Juniper 等）
• 多线程并发巡检
• 智能编码输出处理
• 现代化用户界面

作者：刘华""")

    def toggle_high_contrast(self):
        is_high_contrast = theme_manager.toggle_high_contrast()
        status = "已开启" if is_high_contrast else "已关闭"
        LOG_QUEUE.put(f"高对比度模式{status}")
        self.status_var.set(f"高对比度模式{status}")
        self._reapply_ttk_styles()
        # 递归遍历整棵 widget 树，ModernButton 也会被识别并重绘
        self._reapply_theme_recursive(self.root)

    def _reapply_ttk_styles(self):
        try:
            style = ttk.Style()
            style.theme_use('clam')
            style.configure('DeviceTree.Treeview',
                            background=theme_manager.get_color('BG_CARD'),
                            foreground=theme_manager.get_color('FG_PRIMARY'),
                            fieldbackground=theme_manager.get_color('BG_CARD'),
                            rowheight=36,
                            font=(FONT_FAMILY_UI, 10),
                            borderwidth=0, relief='flat',
                            padding=(0, 4, 0, 4))
            style.configure('DeviceTree.Treeview.Heading',
                            background=theme_manager.get_color('BG_SECONDARY'),
                            foreground=theme_manager.get_color('FG_PRIMARY'),
                            font=(FONT_FAMILY_UI, 10, 'bold'),
                            relief='flat',
                            padding=(10, 8, 10, 8))
            style.map('DeviceTree.Treeview',
                      background=[('selected', theme_manager.get_color('ACCENT'))],
                      foreground=[('selected', '#ffffff')])
            style.configure('Treeview',
                            borderwidth=1,
                            focusthickness=1,
                            focuscolor=theme_manager.get_color('ACCENT'))
            style.configure('Modern.Horizontal.TProgressbar',
                            troughcolor=theme_manager.get_color('BG_DARK'),
                            background=theme_manager.get_color('ACCENT'),
                            borderwidth=0,
                            lightcolor=theme_manager.get_color('ACCENT_LIGHT'),
                            darkcolor=theme_manager.get_color('ACCENT_DARK'))
            style.configure('Vertical.TScrollbar',
                            gripcount=0,
                            troughcolor=theme_manager.get_color('BG_DARK'),
                            background=theme_manager.get_color('ACCENT_LIGHT'),
                            arrowcolor=theme_manager.get_color('FG_MUTED'),
                            bordercolor=theme_manager.get_color('BG_DARK'),
                            lightcolor=theme_manager.get_color('BG_DARK'),
                            darkcolor=theme_manager.get_color('BG_DARK'))
        except Exception as e:
            debug_log(f"刷新 ttk 样式失败：{e}")

    def _reapply_theme_recursive(self, widget):
        """递归给 Tk 控件应用当前主题色（修复 v2.1：Label 颜色按其父容器区分）"""
        if isinstance(widget, ModernButton):
            try:
                widget._apply_style()
            except Exception:
                pass
        else:
            cls_name = ''
            try:
                cls_name = widget.winfo_class()
            except Exception:
                cls_name = ''
            try:
                if cls_name in ('Frame', 'Toplevel'):
                    widget.configure(bg=theme_manager.get_color('BG_PRIMARY'))
                elif cls_name == 'Label':
                    # v2.1 修复：根据父容器背景决定 Label 自己的 bg，
                    # 之前一律 BG_PRIMARY 会让 BG_CARD 上的 Label 视觉错位
                    try:
                        parent_bg = widget.master.cget('bg')
                    except Exception:
                        parent_bg = ''
                    if parent_bg and parent_bg != theme_manager.get_color('BG_PRIMARY'):
                        widget.configure(bg=parent_bg)
                    else:
                        widget.configure(bg=theme_manager.get_color('BG_PRIMARY'))
                elif cls_name == 'Text':
                    widget.configure(
                        bg=theme_manager.get_color('BG_CARD'),
                        fg=theme_manager.get_color('FG_PRIMARY'),
                        insertbackground=theme_manager.get_color('ACCENT'),
                        selectbackground=theme_manager.get_color('ACCENT'),
                    )
            except Exception:
                pass
        for child in widget.winfo_children():
            self._reapply_theme_recursive(child)

    # ==================== 导出 / 统计 ====================

    def export_results(self):
        if not PANDAS_AVAILABLE:
            messagebox.showerror("错误",
                                 f"导出功能需要安装 pandas 与 openpyxl：\npip install pandas openpyxl\n\n原因：{missing_pandas_message}")
            return
        if not getattr(self, 'inspection_results', None):
            messagebox.showwarning("警告", "没有巡检结果可以导出")
            return
        file_path = filedialog.asksaveasfilename(
            title="导出巡检结果", defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")])
        if not file_path:
            return
        try:
            import pandas as pd
            df = pd.DataFrame([{
                '设备名称': r.get('device_name', ''),
                'IP地址': r.get('ip', ''),
                '设备类型': r.get('device_type', ''),
                '巡检状态': r.get('status', ''),
                '开始时间': r.get('start_time', ''),
                '结束时间': r.get('end_time', ''),
                '耗时(秒)': r.get('duration', 0),
                '错误信息': r.get('error', ''),
            } for r in self.inspection_results])
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='巡检结果', index=False)
                ws = writer.sheets['巡检结果']
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    ws.column_dimensions[column_letter].width = min(max_length + 2, 50)
            LOG_QUEUE.put(f"巡检结果已导出至：{file_path}")
            messagebox.showinfo("成功", f"巡检结果已导出至：{file_path}")
        except Exception as e:
            log_error(f"导出巡检结果失败：{e}")
            messagebox.showerror("错误", f"导出巡检结果失败：{e}")

    def generate_statistics_report(self):
        if not PANDAS_AVAILABLE:
            messagebox.showerror("错误",
                                 f"统计报告功能需要安装 pandas 与 openpyxl：\npip install pandas openpyxl\n\n原因：{missing_pandas_message}")
            return
        results = getattr(self, 'inspection_results', []) or []
        if not results:
            if not messagebox.askyesno("无巡检数据",
                                       "当前尚未执行过巡检，将生成一份空统计报告。是否继续？"):
                return
        try:
            import pandas as pd
            total_devices = len(self.devices) if hasattr(self, 'devices') else 0
            selected_devices = sum(1 for d in (self.devices or []) if d.get('selected', True))
            completed = len(results)
            success_count = sum(1 for r in results if r.get('status') == 'success')
            failed_count = sum(1 for r in results if r.get('status') == 'failed')
            interrupted_count = sum(1 for r in results if r.get('status') == 'interrupted')
            durations = [r.get('duration', 0) for r in results if r.get('duration', 0) > 0]
            avg_duration = (sum(durations) / len(durations)) if durations else 0
            total_duration = sum(durations)
            success_rate = (success_count / selected_devices * 100) if selected_devices > 0 else 0
            latest_time = max((r.get('end_time') for r in results if r.get('end_time')), default='')
            df = pd.DataFrame({
                '统计项目': [
                    '总设备数', '选中设备数', '巡检完成数', '成功数', '失败数', '中断数',
                    '巡检成功率', '平均响应时间(秒)', '总耗时(秒)', '最新巡检时间',
                ],
                '数值': [
                    total_devices, selected_devices, completed,
                    success_count, failed_count, interrupted_count,
                    f"{success_rate:.2f}%", f"{avg_duration:.2f}",
                    f"{total_duration:.2f}",
                    latest_time or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                ]
            })
            file_path = filedialog.asksaveasfilename(
                title="导出统计报告", defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")])
            if not file_path:
                return
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='统计报告', index=False)
                ws = writer.sheets['统计报告']
                for column in ws.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except Exception:
                            pass
                    ws.column_dimensions[column_letter].width = min(max_length + 2, 30)
            LOG_QUEUE.put(f"统计报告已导出至：{file_path}")
            messagebox.showinfo("成功", f"统计报告已导出至：{file_path}")
        except Exception as e:
            log_error(f"生成统计报告失败：{e}")
            messagebox.showerror("错误", f"生成统计报告失败：{e}")

    def show_config_guide(self):
        messagebox.showinfo("配置使用指南", """网络设备自动巡检工具配置指南

一、配置文件路径：
• 设备类型：config/device_types.csv
• 设备列表：config/devices.csv
• 命令文件：config/commands/*.txt

二、设备类型配置格式：
类型 ID|名称|SSH 驱动|Telnet 驱动|Enable|分页命令|协议|命令文件

三、设备列表配置格式：
设备名|IP|类型 ID|用户名|密码|Enable 密码 | 端口 | 协议

四、命令文件格式：
每行一条命令，#开头为注释

详细配置请查看 巡检指南/配置使用指南.md""")

    # ==================== 菜单触发的加载 ====================

    def load_device_types(self):
        initial_dir = CONFIG_DIR if os.path.exists(CONFIG_DIR) else os.getcwd()
        file_path = filedialog.askopenfilename(
            title="选择设备类型配置文件",
            filetypes=[("配置文件", "*.csv *.txt"), ("所有文件", "*.*")],
            initialdir=initial_dir)
        if not file_path:
            return
        self.status_var.set("正在加载设备类型配置...")
        self.device_types = load_device_types_config(file_path, self.encodings_config)
        self.device_types_file = file_path
        self.auto_associate_commands_from_device_types()
        self.update_config_file_display()
        self.update_commands_listbox()
        if validate_device_types_config(self.device_types):
            self.status_var.set(f"成功加载 {len(self.device_types)} 种设备类型配置")
            self.update_status_indicator('success')
        else:
            self.status_var.set("设备类型配置验证失败")
            self.update_status_indicator('error')
        self.update_start_button_state()

    def load_devices(self):
        initial_dir = CONFIG_DIR if os.path.exists(CONFIG_DIR) else os.getcwd()
        file_path = filedialog.askopenfilename(
            title="选择设备列表配置文件",
            filetypes=[("配置文件", "*.csv *.txt"), ("所有文件", "*.*")],
            initialdir=initial_dir)
        if not file_path:
            return
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在：{file_path}")
            return
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ('.csv', '.txt'):
            messagebox.showwarning("警告", f"不推荐的文件格式：{ext}，建议使用 .csv 或 .txt 文件")
        is_valid, validation_errors = validate_config_file(file_path, 3)
        if not is_valid:
            messagebox.showerror("错误", "配置文件格式错误：\n" + "\n".join(validation_errors))
            return
        self.status_var.set("正在加载设备列表...")
        self.devices = load_devices(file_path, self.encodings_config)
        self.original_devices = list(self.devices)
        self.devices_file = file_path
        self.update_device_listbox()
        self.update_config_file_display()
        validation_result = validate_devices_config_with_details(self.devices, self.device_types)
        self.update_start_button_state()
        if validation_result['valid']:
            msg = f"成功加载 {len(self.devices)} 台设备配置"
            self.status_var.set(msg)
            self.update_status_indicator('success')
            LOG_QUEUE.put(msg)
        else:
            self.status_var.set(f"设备列表配置验证失败：{validation_result['error_count']} 个错误")
            self.update_status_indicator('error')
            LOG_QUEUE.put("设备配置验证错误：\n" + "\n".join(validation_result['errors']))

    def configure_commands(self):
        if not self.device_types:
            messagebox.showwarning("警告", "请先加载设备类型配置")
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("配置设备类型命令文件")
        dialog.geometry("600x400")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=theme_manager.get_color('BG_PRIMARY'))
        frame = Frame(dialog, bg=theme_manager.get_color('BG_CARD'))
        frame.pack(fill='both', expand=True, padx=16, pady=16)
        Label(frame, text="设备类型列表", font=(FONT_FAMILY_UI, 12, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=theme_manager.get_color('BG_CARD')).pack(pady=(0, 8))
        listbox = tk.Listbox(frame, bg=theme_manager.get_color('BG_CARD'),
                             fg=theme_manager.get_color('FG_PRIMARY'),
                             font=(FONT_FAMILY_UI, 11))
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=listbox.yview)
        listbox.config(yscrollcommand=scrollbar.set)
        type_ids = list(self.device_types.keys())
        for i, type_id in enumerate(type_ids):
            type_name = self.device_types[type_id]['name']
            cmd_file = self.command_files.get(type_id, ("", []))[0] or "未配置"
            listbox.insert('end', f"{type_id}: {type_name} - 命令文件：{cmd_file}")
        listbox.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')
        btn_frame = Frame(dialog, bg=theme_manager.get_color('BG_PRIMARY'))
        btn_frame.pack(fill='x', padx=16, pady=12)

        def select_file():
            selection = listbox.curselection()
            if not selection:
                messagebox.showinfo("提示", "请先选择一种设备类型")
                return
            index = selection[0]
            type_id = type_ids[index]
            file_path = filedialog.askopenfilename(
                title="选择命令文件",
                filetypes=[("命令文件", "*.txt"), ("所有文件", "*.*")],
                initialdir=COMMANDS_DIR)
            if file_path:
                commands = parse_commands_file(file_path, self.encodings)
                self.command_files[type_id] = (file_path, commands)
                self.device_types[type_id]['commands_file'] = os.path.basename(file_path)
                listbox.delete(index)
                listbox.insert(index, f"{type_id}: {type_name} - 命令文件：{file_path}")
                listbox.selection_set(index)
                self.update_start_button_state()
                LOG_QUEUE.put(f"已配置设备类型 {type_id} 的命令文件")

        ModernButton(btn_frame, "选择文件", select_file, variant='primary', width=100,
                     aria_label="选择命令文件按钮").pack(side='left', padx=4)
        ModernButton(btn_frame, "完成", dialog.destroy, variant='secondary', width=80,
                     aria_label="完成配置按钮").pack(side='right')

    def open_log_directory(self):
        log_dir = os.path.join(os.getcwd(), "InspectionLogs")
        if os.path.exists(log_dir):
            try:
                if sys.platform == 'win32':
                    os.startfile(log_dir)
                elif sys.platform == 'darwin':
                    os.system(f'open "{log_dir}"')
                else:
                    os.system(f'xdg-open "{log_dir}"')
            except Exception as e:
                log_error(f"打开日志目录失败：{e}")
        else:
            messagebox.showinfo("提示", "日志目录不存在")

    # ==================== 巡检 ====================

    def start_inspection(self):
        if not NETMIKO_AVAILABLE:
            messagebox.showerror("错误", "缺少依赖库 netmiko，无法执行巡检。请运行：pip install netmiko")
            return
        if self.inspection_running:
            return
        selected_count = sum(1 for d in self.devices if d.get('selected', True))
        if selected_count == 0:
            messagebox.showwarning("警告", "请至少选择一台设备进行巡检")
            return
        try:
            max_workers = int(self.concurrency_var.get())
            if max_workers < 1 or max_workers > 50:
                raise ValueError("并发数必须在 1-50 之间")
        except ValueError as e:
            messagebox.showerror("错误", f"并发数设置错误：{e}")
            return

        selected_encoding = self.encoding_var.get()
        if selected_encoding == "自动检测":
            selected_encodings = self.encodings
            default_encoding = 'gbk'
            LOG_QUEUE.put("使用自动编码检测模式（默认 GBK；可在下拉框或 devices.csv 第 9 列覆盖）")
        else:
            encoding_map = {"UTF-8": "utf-8", "GBK": "gbk", "GB2312": "gb2312",
                            "GB18030": "gb18030", "Big5": "big5"}
            primary = encoding_map.get(selected_encoding, "gbk")
            selected_encodings = [primary] + [e for e in self.encodings if e != primary]
            default_encoding = primary
            LOG_QUEUE.put(f"使用编码：{selected_encoding}（可在 devices.csv 第 9 列覆盖）")

        self.inspection_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.update_status_indicator('running')
        self.status_var.set("开始巡检...")
        self.progress_bar.set_progress(0, "准备开始...")
        self.inspection_results = []
        debug_log("开始巡检")

        # 实例级 stop_event：先 clear 再传；connectivity test 用自己的 test_stop_event，互不串扰
        self._stop_event.clear()
        progress_reporter = make_progress_reporter(self.progress_bar)

        threading.Thread(
            target=inspection_worker,
            args=(self.devices, self.device_types, self.command_files,
                  selected_encodings, self.status_var, progress_reporter,
                  self.inspection_results, self._stop_event),
            kwargs={'default_encoding': default_encoding, 'max_workers': max_workers},
            daemon=True
        ).start()
        self.root.after(1000, self.check_inspection_complete)

    def stop_inspection(self):
        if not self.inspection_running:
            return
        if messagebox.askyesno("确认停止", "确定要停止当前巡检吗？未完成的设备将被中断。"):
            self._stop_event.set()  # 实例级停止信号，不影响连通性测试
            self.status_var.set("正在停止巡检...")
            self.stop_btn.config(state='disabled')

    def test_device_connectivity(self):
        """测试设备连通性（手动开始、可中途停止、结果实时显示）"""
        if not NETMIKO_AVAILABLE:
            messagebox.showerror("错误", "缺少依赖库 netmiko，无法执行连通性测试。请运行：pip install netmiko")
            return
        selected_items = [item for item, var in self.device_check_vars.items() if var.get() == 1]
        if not selected_items:
            messagebox.showwarning("警告", "请至少选择一台设备进行连通性测试")
            return
        selected_devices = [d for d in self.devices if d.get('selected', True)]
        if not selected_devices:
            messagebox.showwarning("警告", "所选设备列表为空，无法测试")
            return

        # 局部停止事件：与主巡检完全隔离（关键修复：v2.1 之前共用全局 stop_event）
        test_stop_event = threading.Event()
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("设备连通性测试")
        progress_dialog.geometry("720x520")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        def on_dialog_close():
            test_stop_event.set()
            try:
                progress_dialog.grab_release()
            except Exception:
                pass
            progress_dialog.destroy()
        progress_dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        header = Frame(progress_dialog, bg=progress_dialog.cget('bg'))
        header.pack(fill='x', padx=16, pady=(12, 4))
        Label(header,
              text=f"将测试 {len(selected_devices)} 台设备的连通性",
              font=(FONT_FAMILY_UI, 12, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=progress_dialog.cget('bg')).pack(side='left')

        progress_frame = Frame(progress_dialog, bg=progress_dialog.cget('bg'))
        progress_frame.pack(fill='x', padx=16, pady=(4, 4))
        progress_label = Label(progress_frame, text="等待开始...",
                               font=(FONT_FAMILY_UI, 11),
                               fg=theme_manager.get_color('FG_SECONDARY'),
                               bg=progress_dialog.cget('bg'))
        progress_label.pack(anchor='w')
        progress_bar = ttk.Progressbar(progress_frame, mode='determinate',
                                        maximum=len(selected_devices))
        progress_bar.pack(fill='x', pady=(4, 0))

        action_bar = Frame(progress_dialog, bg=progress_dialog.cget('bg'))
        action_bar.pack(fill='x', padx=16, pady=(8, 4))
        Label(action_bar, text="操作：",
              font=(FONT_FAMILY_UI, 10, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=progress_dialog.cget('bg')).pack(side='left', padx=(0, 8))

        def _btn(parent, text, width, variant):
            return ModernButton(parent, text, width=width, height=34, variant=variant)
        action_btn_frame = Frame(action_bar, bg=progress_dialog.cget('bg'))
        action_btn_frame.pack(side='left')
        start_btn = _btn(action_btn_frame, "▶ 开始测试", 130, 'primary')
        stop_btn = _btn(action_btn_frame, "⏹ 停止", 100, 'danger')
        start_btn.pack(side='left', padx=(0, 8))
        stop_btn.pack(side='left')
        stop_btn.disable()

        result_frame = Frame(progress_dialog, bg=progress_dialog.cget('bg'))
        result_frame.pack(fill='both', expand=True, padx=16, pady=(4, 4))
        Label(result_frame, text="执行详情（实时）：",
              font=(FONT_FAMILY_UI, 10, 'bold'),
              fg=theme_manager.get_color('FG_PRIMARY'),
              bg=progress_dialog.cget('bg')).pack(anchor='w')
        result_text = Text(result_frame, wrap='word', font=(FONT_FAMILY_CODE, 10),
                           bg=theme_manager.get_color('BG_PRIMARY'),
                           fg=theme_manager.get_color('FG_PRIMARY'),
                           relief='solid', bd=1, height=14)
        scrollbar = ttk.Scrollbar(result_frame, orient='vertical',
                                  command=result_text.yview)
        result_text.configure(yscrollcommand=scrollbar.set, state='disabled')
        result_text.pack(side='left', fill='both', expand=True, pady=(2, 0))
        scrollbar.pack(side='right', fill='y')

        bottom = Frame(progress_dialog, bg=progress_dialog.cget('bg'))
        bottom.pack(fill='x', padx=16, pady=(4, 12), side='bottom')
        timeout_frame = Frame(bottom, bg=progress_dialog.cget('bg'))
        timeout_frame.pack(side='left')
        Label(timeout_frame, text="单设备超时(秒):",
              font=(FONT_FAMILY_UI, 9),
              fg=theme_manager.get_color('FG_MUTED'),
              bg=progress_dialog.cget('bg')).pack(side='left')
        timeout_var = tk.IntVar(value=CONNECTIVITY_TIMEOUT_SECONDS)
        ttk.Spinbox(timeout_frame, from_=1, to=60, width=5,
                    textvariable=timeout_var,
                    font=(FONT_FAMILY_UI, 9)).pack(side='left', padx=(6, 12))
        Label(timeout_frame, text="(5s 无响应即超时；范围 1-60s)",
              font=(FONT_FAMILY_UI, 9),
              fg=theme_manager.get_color('FG_MUTED'),
              bg=progress_dialog.cget('bg')).pack(side='left')
        utility_btn_frame = Frame(bottom, bg=progress_dialog.cget('bg'))
        utility_btn_frame.pack(side='right')
        copy_btn = _btn(utility_btn_frame, "📋 复制结果", 110, 'secondary')
        close_btn = _btn(utility_btn_frame, "关闭", 80, 'secondary')
        copy_btn.pack(side='left', padx=(0, 8))
        close_btn.pack(side='left')
        copy_btn.disable()

        def ui_update(fn, *args, **kwargs):
            try:
                def _do():
                    try:
                        fn(*args, **kwargs)
                        progress_dialog.update_idletasks()
                    except Exception:
                        pass
                progress_dialog.after(0, _do)
            except Exception:
                pass

        def append_result(text):
            try:
                result_text.configure(state='normal')
                result_text.insert('end', text)
                result_text.see('end')
                result_text.configure(state='disabled')
            except Exception:
                pass

        def reset_result():
            try:
                result_text.configure(state='normal')
                result_text.delete('1.0', 'end')
                result_text.configure(state='disabled')
            except Exception:
                pass

        def set_progress_label(text):
            ui_update(progress_label.config, text=text)

        def set_progress_bar(value):
            ui_update(progress_bar.__setitem__, 'value', value)

        def copy_result_to_clipboard():
            try:
                content = result_text.get('1.0', 'end')
                progress_dialog.clipboard_clear()
                progress_dialog.clipboard_append(content)
                set_progress_label("结果已复制到剪贴板")
            except Exception as e:
                debug_log(f"复制结果失败：{e}")

        close_btn.config(command=on_dialog_close)
        copy_btn.config(command=copy_result_to_clipboard)

        def run_test():
            try:
                try:
                    cfg_timeout = int(timeout_var.get())
                    if cfg_timeout < 1 or cfg_timeout > 60:
                        cfg_timeout = CONNECTIVITY_TIMEOUT_SECONDS
                except (ValueError, tk.TclError):
                    cfg_timeout = CONNECTIVITY_TIMEOUT_SECONDS
                try:
                    cfg_workers = int(self.concurrency_var.get())
                except (ValueError, AttributeError):
                    cfg_workers = 5
                actual_workers = max(1, min(cfg_workers, 50, len(selected_devices)))

                state = {'success': 0, 'timeout': 0, 'error': 0,
                         'completed': 0, 'skipped': 0}
                lock = threading.Lock()

                def test_one_device(device):
                    if test_stop_event.is_set():
                        return ('skipped', '用户停止')
                    dev_name = device.get('device_name', '?')
                    dev_ip = device.get('ip', '?')
                    outcome = ('error', '未知错误')
                    try:
                        dtype = device['device_type']
                        if dtype not in self.device_types:
                            outcome = ('unknown_type', f"未知设备类型 {dtype}")
                        else:
                            dcfg = self.device_types[dtype]
                            protocol = device.get('protocol', 'ssh') or dcfg['default_protocol']
                            driver = dcfg['netmiko_type'][protocol]
                            enc_ui = self.encoding_var.get()
                            if enc_ui == "自动检测":
                                enc_ui = 'utf-8'
                            else:
                                enc_ui = {"UTF-8": "utf-8", "GBK": "gbk",
                                          "GB2312": "gb2312", "GB18030": "gb18030",
                                          "Big5": "big5"}.get(enc_ui, 'utf-8')
                            from core.encoding import resolve_effective_encoding
                            eff_enc = resolve_effective_encoding(device, dcfg, enc_ui)
                            dinfo = {
                                'device_type': driver,
                                'ip': device['ip'],
                                'port': device.get('port', 22),
                                'timeout': cfg_timeout,
                                'global_delay_factor': 1,
                                'read_timeout_override': cfg_timeout,
                                'encoding': eff_enc,
                            }
                            if device.get('username'):
                                dinfo['username'] = device['username']
                            if device.get('password'):
                                dinfo['password'] = device['password']
                            if device.get('secret'):
                                dinfo['secret'] = device['secret']
                            conn = connect_with_retry(dinfo, stop_event=test_stop_event,
                                                     max_retries=0, retry_delay=0)
                            if conn:
                                try:
                                    conn.disconnect()
                                except Exception:
                                    pass
                                outcome = ('success', None)
                            else:
                                outcome = ('timeout', f"{cfg_timeout}s 无响应")
                    except Exception as e:
                        ename = type(e).__name__
                        if 'Timeout' in ename:
                            outcome = ('timeout', str(e))
                        else:
                            outcome = ('error', f"{ename}: {e}")

                    with lock:
                        kind = outcome[0]
                        if kind == 'success':
                            state['success'] += 1
                        elif kind == 'timeout':
                            state['timeout'] += 1
                        elif kind == 'error':
                            state['error'] += 1
                        elif kind == 'skipped':
                            state['skipped'] += 1
                        state['completed'] += 1
                        lc, ls, lt, le, lk = (state['completed'], state['success'],
                                              state['timeout'], state['error'],
                                              state['skipped'])
                    set_progress_label(
                        f"已完成 {lc}/{len(selected_devices)} "
                        f"（通 {ls}, 超时 {lt}, 异常 {le}, 跳过 {lk}），最近：{dev_name}"
                    )
                    set_progress_bar(lc)
                    kind, msg = outcome
                    prefix = f"[{lc:>3d}/{len(selected_devices)}] "
                    if kind == 'success':
                        line = f"{prefix}✓ {dev_name}({dev_ip}) - 连接成功\n"
                    elif kind == 'timeout':
                        line = f"{prefix}⏱ {dev_name}({dev_ip}) - {msg}\n"
                    elif kind in ('unknown_type', 'error'):
                        line = f"{prefix}✗ {dev_name}({dev_ip}) - {msg}\n"
                    elif kind == 'skipped':
                        line = f"{prefix}⊘ {dev_name}({dev_ip}) - {msg}\n"
                    else:
                        line = f"{prefix}✗ {dev_name}({dev_ip}) - {msg}\n"
                    ui_update(append_result, line)
                    return outcome

                ui_update(reset_result)
                ui_update(append_result,
                          f"开始测试 {len(selected_devices)} 台设备 "
                          f"（{actual_workers} 并发，单设备超时 {cfg_timeout}s）...\n")
                set_progress_label(
                    f"正在进行 0/{len(selected_devices)}（通 0, 超时 0, 异常 0, 跳过 0）"
                )
                set_progress_bar(0)

                try:
                    with ThreadPoolExecutor(max_workers=actual_workers) as ex:
                        futs = [ex.submit(test_one_device, d) for d in selected_devices]
                        for f in futs:
                            try:
                                f.result()
                            except Exception as e:
                                log_error(f"连通性测试任务异常：{e}")
                except Exception as e:
                    from utils.logging_setup import format_traceback
                    tb_text = format_traceback()
                    log_error(f"连通性测试线程异常：{e}")
                    log_error(tb_text)
                    ui_update(append_result, f"\n[ERROR] 线程异常：{e}\n{tb_text}\n")
                    set_progress_label(f"线程异常：{e}")

                stopped = "（已停止）" if test_stop_event.is_set() else ""
                fs, ft, fe, fk = state['success'], state['timeout'], state['error'], state['skipped']
                total = len(selected_devices)
                failed = total - fs
                set_progress_label(
                    f"测试完成{stopped}: {fs}/{total} 通 "
                    f"(超时 {ft}, 失败 {failed}, 异常 {fe}, 跳过 {fk}；"
                    f"{actual_workers} 并发 × {cfg_timeout}s 超时)"
                )
                ui_update(append_result,
                          f"\n{'='*50}\n"
                          f"测试总结{stopped}：\n"
                          f"  总数：{total}\n"
                          f"  通：{fs}\n"
                          f"  超时：{ft}\n"
                          f"  失败：{failed}\n"
                          f"  异常：{fe}\n"
                          f"  跳过：{fk}\n"
                          f"  并发：{actual_workers}\n"
                          f"  单设备超时：{cfg_timeout}s\n"
                          f"{'='*50}\n")
            finally:
                def reset_buttons():
                    try:
                        start_btn.enable()
                        stop_btn.disable()
                        copy_btn.enable()
                    except Exception:
                        pass
                ui_update(reset_buttons)

        def on_start():
            test_stop_event.clear()
            try:
                start_btn.disable()
                stop_btn.enable()
                copy_btn.disable()
            except Exception:
                pass
            threading.Thread(target=run_test, daemon=True).start()

        def on_stop():
            test_stop_event.set()
            try:
                stop_btn.disable()
            except Exception:
                pass
            set_progress_label("正在停止...")

        start_btn.config(command=on_start)
        stop_btn.config(command=on_stop)

    def check_inspection_complete(self):
        if not self.inspection_running:
            return
        selected_devices = [d for d in self.devices if d.get('selected', True)]
        total_selected = len(selected_devices)
        results = getattr(self, 'inspection_results', []) or []
        completed = len(results)

        done = (completed >= total_selected) or (self._stop_event.is_set() and completed > 0)
        worker_text = self.status_var.get()
        worker_signaled = ("巡检完成" in worker_text) or ("巡检已停止" in worker_text)

        if done or worker_signaled:
            self.inspection_running = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')

            success_count = sum(1 for r in results if r.get('status') == 'success')
            failed_count = sum(1 for r in results if r.get('status') == 'failed')
            interrupted_count = sum(1 for r in results if r.get('status') == 'interrupted')
            durations = [r.get('duration', 0) for r in results if r.get('duration', 0) > 0]
            avg_duration = (sum(durations) / len(durations)) if durations else 0
            total_duration = sum(durations)

            self.completed_count = completed
            self.success_count = success_count
            self.failed_count = failed_count
            self.success_rate = (success_count / total_selected * 100) if total_selected > 0 else 0
            self.avg_response_time = avg_duration
            self.total_duration = total_duration

            if self._stop_event.is_set() or interrupted_count > 0:
                self.update_status_indicator('warning')
            elif failed_count == 0 and success_count > 0:
                self.update_status_indicator('success')
            elif success_count == 0:
                self.update_status_indicator('error')
            else:
                self.update_status_indicator('warning')

            # 与 worker.py 保持一致：worker 用 failed_total = total - success_count
            # （把 "中断" 也算作非成功）。这里把 interrupted 也纳入红绿分界，
            # 否则 "全部中断但失败数=0"（用户刚启动就按 Stop）会变绿，
            # 而 worker 的 "巡检已停止" 会变红，两条总结行颜色对打脸。
            # 规则：success_count > 0 AND failed == 0 AND interrupted == 0 → 绿
            is_clean_run = (success_count > 0
                            and failed_count == 0
                            and interrupted_count == 0)
            summary_level = "SUCCESS" if is_clean_run else "ERROR"
            LOG_QUEUE.put(
                f"[{summary_level}] 巡检收尾：共 {total_selected} 台，完成 {completed} 台，"
                f"成功 {success_count} 台，失败 {failed_count} 台，中断 {interrupted_count} 台"
            )
            return

        self.root.after(500, self.check_inspection_complete)
