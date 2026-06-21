# -*- coding: utf-8 -*-
"""
网络设备自动巡检工具 v2.0
Network Device Inspection Tool v2.0
作者：刘华
"""
import os
import sys
import csv
import threading
import queue
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import traceback
import tkinter as tk
from tkinter import (Tk, Frame, Label, Button, Listbox, Text, Scrollbar,
                     filedialog, messagebox, ttk, StringVar, END, Checkbutton, IntVar, Canvas)
from tkinter.ttk import Treeview, Progressbar, Separator
try:
    from netmiko import ConnectHandler, NetMikoAuthenticationException, NetMikoTimeoutException
    NETMIKO_AVAILABLE = True
except ImportError as e:
    ConnectHandler = None
    NetMikoAuthenticationException = Exception
    NetMikoTimeoutException = Exception
    NETMIKO_AVAILABLE = False
    missing_netmiko_message = str(e)

# 导入字体和样式库
try:
    from tkinter import font
except ImportError:
    import tkinter.font as font

# ==================== 现代浅色风格配色 ====================
# 主色调 - 清新明亮
COLOR_BG_PRIMARY = "#F5F7FA"        # 主背景 - 浅灰蓝
COLOR_BG_SECONDARY = "#FFFFFF"      # 次级背景 - 纯白
COLOR_BG_CARD = "#FFFFFF"           # 卡片背景 - 纯白
COLOR_BG_DARK = "#F0F2F5"           # 日志区背景 - 浅灰

# 文字颜色 - 改进对比度以符合无障碍标准
COLOR_FG_PRIMARY = "#0F172A"        # 主文字 - 更深的灰色，提高对比度
COLOR_FG_SECONDARY = "#475569"      # 次文字 - 更深的灰色，提高对比度
COLOR_FG_LIGHT = "#334155"          # 浅色文字 - 提高对比度
COLOR_FG_MUTED = "#64748B"          # 弱化文字 - 提高对比度

# 强调色 - 现代蓝
COLOR_ACCENT = "#2563EB"            # 主强调色 - 更深的蓝色，提高对比度
COLOR_ACCENT_LIGHT = "#3B82F6"      # 浅蓝 - 悬停
COLOR_ACCENT_DARK = "#1D4ED8"       # 深蓝 - 按下，更深的蓝色
COLOR_ACCENT_GRADIENT_START = "#2563EB"
COLOR_ACCENT_GRADIENT_END = "#3B82F6"

# 功能色 - 提高对比度
COLOR_SUCCESS = "#059669"           # 成功 - 更深的绿色
COLOR_WARNING = "#D97706"           # 警告 - 更深的琥珀色
COLOR_ERROR = "#DC2626"             # 错误 - 更深的红色
COLOR_INFO = "#0891B2"              # 信息 - 更深的青色

# 边框和分隔
COLOR_BORDER = "#CBD5E1"            # 边框 - 更深的灰色，提高对比度
COLOR_BORDER_DARK = "#94A3B8"       # 深色边框 - 提高对比度
COLOR_DIVIDER = "#E2E8F0"           # 分隔线 - 提高对比度

# 日志颜色 - 浅色背景适配，提高对比度
LOG_COLORS = {
    'DEBUG': '#475569',
    'INFO': '#2563EB',
    'WARNING': '#D97706',
    'ERROR': '#DC2626',
    'SUCCESS': '#059669',
    'CRITICAL': '#B91C1C'
}

# 高对比度模式备用颜色
HIGH_CONTRAST_BG_PRIMARY = "#FFFFFF"
HIGH_CONTRAST_BG_SECONDARY = "#FFFFFF"
HIGH_CONTRAST_BG_CARD = "#FFFFFF"
HIGH_CONTRAST_BG_DARK = "#F8FAFC"
HIGH_CONTRAST_FG_PRIMARY = "#000000"
HIGH_CONTRAST_FG_SECONDARY = "#333333"
HIGH_CONTRAST_FG_LIGHT = "#1A1A1A"
HIGH_CONTRAST_FG_MUTED = "#4D4D4D"
HIGH_CONTRAST_ACCENT = "#0000FF"
HIGH_CONTRAST_SUCCESS = "#006400"
HIGH_CONTRAST_WARNING = "#8B0000"
HIGH_CONTRAST_ERROR = "#8B0000"
HIGH_CONTRAST_INFO = "#000080"
HIGH_CONTRAST_BORDER = "#000000"


class ThemeManager:
    """主题管理器 - 统一管理应用主题"""
    
    def __init__(self):
        self.high_contrast_mode = False
    
    def get_color(self, color_name):
        """获取颜色值，根据当前主题返回对应颜色"""
        if self.high_contrast_mode:
            return getattr(self, f'HIGH_CONTRAST_{color_name}', globals()[f'COLOR_{color_name}'])
        return globals()[f'COLOR_{color_name}']
    
    def toggle_high_contrast(self):
        """切换高对比度模式"""
        self.high_contrast_mode = not self.high_contrast_mode
        return self.high_contrast_mode

# 创建全局主题管理器实例
theme_manager = ThemeManager()

# ==================== 字体设置 ====================
FONT_FAMILY_UI = "Microsoft YaHei UI"
FONT_FAMILY_CODE = "Consolas"
FONT_FAMILY_ICON = "Segoe MDL2 Assets"  # Windows 图标字体

# ==================== 尺寸设置 ====================
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700

# 边距和间距
PADDING_X = 16
PADDING_Y = 12
CARD_PADDING = 16
COMPONENT_GAP = 12

# 圆角半径
CORNER_RADIUS = 8

# 阴影（通过边框模拟）
SHADOW_COLOR = "rgba(0, 0, 0, 0.1)"

# ==================== 日志目录 ====================
LOG_DIR_NAME = "InspectionLogs"
LOG_SUBDIR_NAME = "logs"

# 配置目录
CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config')
COMMANDS_DIR = os.path.join(CONFIG_DIR, 'commands')
LOG_QUEUE = queue.Queue()

# 默认配置文件
DEFAULT_DEVICE_TYPES_FILE = ""
DEFAULT_DEVICES_FILE = ""

if os.path.exists(os.path.join(CONFIG_DIR, 'device_types.csv')):
    DEFAULT_DEVICE_TYPES_FILE = os.path.join(CONFIG_DIR, 'device_types.csv')
elif os.path.exists(os.path.join(CONFIG_DIR, 'device_types.txt')):
    DEFAULT_DEVICE_TYPES_FILE = os.path.join(CONFIG_DIR, 'device_types.txt')

if os.path.exists(os.path.join(CONFIG_DIR, 'devices.csv')):
    DEFAULT_DEVICES_FILE = os.path.join(CONFIG_DIR, 'devices.csv')
elif os.path.exists(os.path.join(CONFIG_DIR, 'devices.txt')):
    DEFAULT_DEVICES_FILE = os.path.join(CONFIG_DIR, 'devices.txt')

# 全局变量
stop_event = threading.Event()  # 线程安全的停止信号
_inspection_lock = threading.Lock()
_encoding_cache = {}  # 文件编码缓存，避免重复检测

# ==================== 工具函数 ====================
def setup_logging():
    """初始化日志系统"""
    logs_dir = os.path.join(os.getcwd(), "InspectionLogs", "logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                os.path.join(logs_dir, f"all_logs_{timestamp}.log"),
                encoding='utf-8'
            ),
            logging.FileHandler(
                os.path.join(logs_dir, f"debug_{timestamp}.log"),
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )

    debug_handler = logging.getLogger().handlers[1]
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)

    console_handler = logging.getLogger().handlers[2]
    console_handler.setLevel(logging.INFO)

    return logging.getLogger()

logger = None

def debug_log(message, level="DEBUG"):
    """记录日志信息"""
    global logger
    if logger is None:
        logger = setup_logging()

    if level.upper() == "DEBUG":
        logger.debug(message)
    elif level.upper() == "INFO":
        logger.info(message)
    elif level.upper() == "WARNING":
        logger.warning(message)
    elif level.upper() == "ERROR":
        logger.error(message)
    elif level.upper() == "CRITICAL":
        logger.critical(message)
    else:
        logger.debug(message)

def log_info(message):
    debug_log(message, "INFO")

def log_warning(message):
    debug_log(message, "WARNING")

def log_error(message):
    debug_log(message, "ERROR")


def detect_file_encoding(file_path, encodings):
    """检测文件编码并缓存，避免重复检测"""
    if file_path in _encoding_cache:
        debug_log(f"使用缓存的编码：{file_path} -> {_encoding_cache[file_path]}")
        return _encoding_cache[file_path]

    debug_log(f"开始检测文件编码：{file_path}")
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)  # 只读前1KB检测
            _encoding_cache[file_path] = encoding
            debug_log(f"检测到文件编码：{file_path} -> {encoding}")
            return encoding
        except UnicodeDecodeError:
            continue
        except Exception as e:
            debug_log(f"编码检测异常：{file_path} -> {encoding}: {e}")
            continue

    # 所有编码尝试失败，返回第一个编码作为默认值
    debug_log(f"所有编码尝试失败，使用默认编码：{encodings[0]}")
    _encoding_cache[file_path] = encodings[0]
    return encodings[0]


# ==================== 输入验证工具函数 ====================
import ipaddress
import re

def validate_ip(ip: str) -> bool:
    """验证IP地址格式"""
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False

def validate_port(port: int) -> bool:
    """验证端口号范围"""
    return 1 <= port <= 65535

def sanitize_filename(filename: str) -> str:
    """清理文件名，移除非法字符"""
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def validate_device_config(device: dict) -> list:
    """验证设备配置，返回错误列表"""
    errors = []
    
    if not device.get('device_name', '').strip():
        errors.append("设备名称不能为空")
    
    if not device.get('ip', '').strip():
        errors.append("IP地址不能为空")
    elif not validate_ip(device['ip']):
        errors.append(f"IP地址格式错误：{device['ip']}")
    
    port = device.get('port', 22)
    if not validate_port(port):
        errors.append(f"端口号无效：{port}")
    
    protocol = device.get('protocol', '')
    if protocol and protocol not in ['ssh', 'telnet']:
        errors.append(f"协议无效：{protocol}")
    
    return errors


def encrypt_password(password: str, key: bytes = None) -> str:
    """加密密码（简单Base64编码，生产环境建议使用cryptography库）"""
    import base64
    if not password:
        return ""
    # 使用Base64编码作为简单加密（可选：使用cryptography.fernet进行真正加密）
    encoded = base64.b64encode(password.encode('utf-8')).decode('utf-8')
    return f"ENC:{encoded}"

def decrypt_password(encrypted: str, key: bytes = None) -> str:
    """解密密码"""
    import base64
    if not encrypted or not encrypted.startswith("ENC:"):
        return encrypted  # 未加密的密码直接返回
    try:
        encoded = encrypted[4:]  # 移除"ENC:"前缀
        decoded = base64.b64decode(encoded.encode('utf-8')).decode('utf-8')
        return decoded
    except Exception as e:
        debug_log(f"密码解密失败：{e}")
        return encrypted

def is_password_encrypted(value: str) -> bool:
    """判断密码是否已加密"""
    return value.startswith("ENC:") if value else False


# ==================== 命令白名单验证 ====================
# 常见网络设备安全命令白名单
SAFE_COMMAND_PATTERNS = {
    'huawei': [
        r'^display\s+.*',           # display命令
        r'^show\s+.*',              # show命令
        r'^screen-length\s+0.*',    # 分页控制
    ],
    'cisco_ios': [
        r'^show\s+.*',
        r'^terminal\s+length\s+0.*',
    ],
    'hp_comware': [
        r'^display\s+.*',
        r'^screen-length\s+0.*',
    ],
    'juniper_junos': [
        r'^show\s+.*',
        r'^display\s+.*',
    ],
    'ruijie_os': [
        r'^show\s+.*',
        r'^display\s+.*',
    ],
    'linux': [
        r'^cat\s+/etc/.*',
        r'^uname\s+-.*',
        r'^ifconfig.*',
        r'^ip\s+.*',
        r'^df\s+-.*',
        r'^free\s+-.*',
    ],
}

def validate_command(device_type_id: str, command: str) -> bool:
    """验证命令是否在白名单中"""
    patterns = SAFE_COMMAND_PATTERNS.get(device_type_id, [])
    for pattern in patterns:
        if re.match(pattern, command, re.IGNORECASE):
            return True
    return False

def validate_commands_for_device(device_type_id: str, commands: list) -> list:
    """过滤不安全命令，返回有效命令列表"""
    valid_commands = []
    for cmd in commands:
        if validate_command(device_type_id, cmd):
            valid_commands.append(cmd)
        else:
            LOG_QUEUE.put(f"警告：命令 '{cmd}' 不在白名单中，已跳过")
            debug_log(f"命令白名单过滤：{cmd}")
    return valid_commands


# ==================== 数据模型 ====================
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class DeviceTypeModel:
    """设备类型数据模型"""
    type_id: str
    name: str
    ssh_driver: str
    telnet_driver: str
    enable_mode: bool
    disable_paging_cmd: str
    default_protocol: str
    commands_file: str = ""
    
    @property
    def netmiko_type(self) -> Dict[str, str]:
        """获取Netmiko驱动映射"""
        return {
            'ssh': self.ssh_driver,
            'telnet': self.telnet_driver
        }
    
    @classmethod
    def from_dict(cls, type_id: str, config: dict) -> 'DeviceTypeModel':
        """从字典创建实例"""
        return cls(
            type_id=type_id,
            name=config.get('name', ''),
            ssh_driver=config['netmiko_type']['ssh'],
            telnet_driver=config['netmiko_type']['telnet'],
            enable_mode=config.get('enable_mode', False),
            disable_paging_cmd=config.get('disable_paging_cmd', ''),
            default_protocol=config.get('default_protocol', 'ssh'),
            commands_file=config.get('commands_file', '')
        )

@dataclass
class DeviceModel:
    """设备数据模型"""
    device_name: str
    ip: str
    device_type: str
    username: str = ""
    password: str = ""
    secret: str = ""
    port: int = 22
    protocol: Optional[str] = None
    encoding: Optional[str] = None
    selected: bool = True
    
    def to_connection_dict(self, device_type: DeviceTypeModel) -> Dict:
        """转换为Netmiko连接参数字典"""
        protocol = self.protocol or device_type.default_protocol
        return {
            'device_type': device_type.netmiko_type[protocol],
            'ip': self.ip,
            'port': self.port,
            'username': self.username or None,
            'password': self.password or None,
            'secret': self.secret or None,
            'timeout': 60,
            'global_delay_factor': 2,
            'read_timeout_override': 120,
        }


# ==================== 现代风格组件 ====================
class ModernButton(tk.Button):
    """现代化按钮 - 使用标准Button控件实现，带有动画效果"""

    def __init__(self, parent, text, command=None, variant='primary', width=120, height=40, aria_label=None, **kwargs):
        # 初始化实例变量
        self.variant = variant
        self.is_disabled = False
        self.aria_label = aria_label or text
        self.original_command = command
        self.default_bg = None
        self.default_fg = None

        # 计算按钮的宽度和高度
        char_width = max(width // 10, 8)  # 每个字符约10像素宽
        row_height = max(height // 20, 1)  # 每行约20像素高

        # 初始化按钮 - 不设置command，因为我们要自己处理
        super().__init__(parent, text=text, width=char_width, height=row_height, **kwargs)

        # 设置初始样式
        self._apply_style()

        # 绑定事件
        self.bind('<Button-1>', self._on_button_click)
        self.bind('<space>', self._on_space_press)
        self.bind('<Return>', self._on_space_press)  # 也支持回车键
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.config(takefocus=True)  # 允许接收焦点，但不自动获取

    def _apply_style(self):
        """应用按钮样式"""
        # 获取主题颜色
        try:
            accent_color = theme_manager.get_color('ACCENT')
            accent_light = theme_manager.get_color('ACCENT_LIGHT')
            accent_dark = theme_manager.get_color('ACCENT_DARK')
            error_color = theme_manager.get_color('ERROR')
            fg_primary = theme_manager.get_color('FG_PRIMARY')
            bg_card = theme_manager.get_color('BG_CARD')
        except:
            # 安全回退颜色
            accent_color = "#3B82F6"
            accent_light = "#60A5FA"
            accent_dark = "#2563EB"
            error_color = "#EF4444"
            fg_primary = "#1F2937"
            bg_card = "#FFFFFF"

        # 根据变体设置样式
        if self.variant == 'primary':
            bg_color = accent_color
            fg_color = '#ffffff'
            active_bg = accent_dark
        elif self.variant == 'danger':
            bg_color = error_color
            fg_color = '#ffffff'
            active_bg = '#C41E3A'
        elif self.variant == 'secondary':
            bg_color = bg_card
            fg_color = accent_color
            active_bg = accent_light
        else:  # default
            bg_color = '#d0d0d0'
            fg_color = fg_primary
            active_bg = '#c0c0c0'

        # 记录默认颜色用于悬停效果
        self.default_bg = bg_color
        self.default_fg = fg_color

        # 应用样式
        self.config(
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground='#ffffff',
            relief='flat',  # 使用平面样式，配合自定义悬停效果
            bd=0,
            highlightthickness=0,
            padx=10,
            pady=6,
            font=(FONT_FAMILY_UI, 10, 'bold' if self.variant == 'primary' else 'normal'),
            cursor='hand2'
        )

    def _animate_hover_in(self):
        """悬停进入动画效果"""
        if not self.is_disabled:
            # 模拟悬停效果，稍微改变背景色
            try:
                accent_color = theme_manager.get_color('ACCENT')
                accent_light = theme_manager.get_color('ACCENT_LIGHT')
                if self.variant == 'secondary':
                    hover_bg = accent_light
                else:
                    # 使用稍微亮一点的颜色
                    hover_bg = accent_light if self.variant == 'primary' else '#e0e0e0'
                self.config(bg=hover_bg)
            except:
                # 安全回退
                if self.variant == 'secondary':
                    self.config(bg='#e6e6e6')
                else:
                    self.config(bg='#e0e0e0')

    def _animate_hover_out(self):
        """悬停退出动画效果"""
        if not self.is_disabled:
            # 恢复原始背景色
            self.config(bg=self.default_bg)

    def _on_button_click(self, event=None):
        """按钮点击事件"""
        if not self.is_disabled and self.original_command:
            try:
                self.original_command()
            except Exception as e:
                # 仅在log_error函数存在时才调用
                try:
                    log_error(f"按钮命令执行错误：{e}")
                except NameError:
                    # 如果log_error函数不可用，打印到控制台
                    print(f"按钮命令执行错误：{e}")

    def _on_space_press(self, event=None):
        """空格键或回车键事件"""
        if not self.is_disabled and self.original_command:
            try:
                self.original_command()
            except Exception as e:
                try:
                    log_error(f"按钮命令执行错误：{e}")
                except NameError:
                    print(f"按钮命令执行错误：{e}")

    def _on_enter(self, event=None):
        """鼠标进入"""
        if not self.is_disabled:
            self._animate_hover_in()

    def _on_leave(self, event=None):
        """鼠标离开"""
        if not self.is_disabled:
            self._animate_hover_out()

    def _on_focus_in(self, event=None):
        """焦点进入"""
        if not self.is_disabled:
            self.config(relief='solid', bd=1)

    def _on_focus_out(self, event=None):
        """焦点离开"""
        if not self.is_disabled:
            self.config(relief='flat', bd=0)

    def disable(self):
        """禁用按钮"""
        self.is_disabled = True
        self.config(state='disabled', bg='#D9D9D9', fg='#A6A6A6')

    def enable(self):
        """启用按钮"""
        self.is_disabled = False
        self.config(state='normal')
        self._apply_style()

    def set_variant(self, variant):
        """动态设置按钮变体"""
        self.variant = variant
        self._apply_style()


class ModernCard(Frame):
    """现代化卡片容器"""

    def __init__(self, parent, bg=theme_manager.get_color('BG_CARD'), relief='flat', borderwidth=1, **kwargs):
        super().__init__(parent, bg=bg, relief=relief, borderwidth=borderwidth, **kwargs)

        # 添加阴影效果（通过边框）
        self.shadow_top = Frame(self, height=1, bg='#ffffff')
        self.shadow_left = Frame(self, width=1, bg='#ffffff')
        self.shadow_bottom = Frame(self, height=1, bg='#e0e0e0')
        self.shadow_right = Frame(self, width=1, bg='#e0e0e0')


class ModernHeader(Label):
    """现代化标题"""

    def __init__(self, parent, text, font_size=14, weight='bold', color=theme_manager.get_color('FG_PRIMARY'), **kwargs):
        font = (FONT_FAMILY_UI, font_size, weight)
        super().__init__(parent, text=text, font=font, fg=color, bg=parent.cget('bg'), **kwargs)


class ModernEntry(tk.Entry):
    """现代化输入框 - 具有现代化外观和交互动画"""

    def __init__(self, parent, placeholder='', **kwargs):
        # 设置默认字体和颜色
        if 'font' not in kwargs:
            kwargs['font'] = (FONT_FAMILY_UI, 11)
        if 'fg' not in kwargs:
            kwargs['fg'] = theme_manager.get_color('FG_PRIMARY')
        if 'bg' not in kwargs:
            kwargs['bg'] = theme_manager.get_color('BG_CARD')
        if 'relief' not in kwargs:
            kwargs['relief'] = 'flat'
        if 'highlightthickness' not in kwargs:
            kwargs['highlightthickness'] = 2  # 增加高亮厚度
        if 'highlightbackground' not in kwargs:
            kwargs['highlightbackground'] = theme_manager.get_color('BORDER')
        if 'highlightcolor' not in kwargs:
            kwargs['highlightcolor'] = theme_manager.get_color('ACCENT')  # 焦点时的高亮颜色
        if 'insertbackground' not in kwargs:
            kwargs['insertbackground'] = theme_manager.get_color('FG_PRIMARY')  # 光标颜色
        if 'selectbackground' not in kwargs:
            kwargs['selectbackground'] = theme_manager.get_color('ACCENT')  # 选中文本背景
        if 'selectforeground' not in kwargs:
            kwargs['selectforeground'] = '#ffffff'  # 选中文本前景

        super().__init__(parent, **kwargs)
        self.placeholder = placeholder
        self.placeholder_color = theme_manager.get_color('FG_MUTED')
        self.default_fg_color = theme_manager.get_color('FG_PRIMARY')
        self.has_placeholder = False

        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)

        if placeholder:
            self._show_placeholder()

    def _on_focus_in(self, event):
        if self.has_placeholder:
            super().delete(0, 'end')
            self['fg'] = self.default_fg_color
            self.has_placeholder = False

    def _on_focus_out(self, event):
        if not self.get():
            self._show_placeholder()

    def _show_placeholder(self):
        self.delete(0, 'end')
        self.insert(0, self.placeholder)
        self['fg'] = self.placeholder_color
        self.has_placeholder = True

    def get(self):
        if self.has_placeholder:
            return ''
        return super().get()


class ModernProgressbar(Progressbar):
    """现代化进度条"""

    def __init__(self, parent, **kwargs):
        style = ttk.Style()
        style.configure('Modern.Horizontal.TProgressbar',
                       troughcolor=theme_manager.get_color('BG_DARK'),
                       background=theme_manager.get_color('ACCENT'),
                       borderwidth=0,
                       lightcolor=theme_manager.get_color('ACCENT_LIGHT'),
                       darkcolor=theme_manager.get_color('ACCENT_DARK'))

        super().__init__(parent, style='Modern.Horizontal.TProgressbar', **kwargs)


class DetailedProgressbar(Frame):
    """带详细信息的进度条组件"""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=parent.cget('bg') if parent.cget('bg') else theme_manager.get_color('BG_PRIMARY'))

        # 创建内部组件
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = ModernProgressbar(self, variable=self.progress_var, maximum=100)
        self.progress_label = Label(self, text="", font=(FONT_FAMILY_UI, 10),
                                   fg=theme_manager.get_color('FG_SECONDARY'), bg=self.cget('bg'))

        # 布局
        self.progress_bar.pack(fill='x', expand=True)
        self.progress_label.pack(fill='x', expand=True, pady=(4, 0))

    def set_progress(self, value, text=""):
        """设置进度值和文本"""
        self.progress_var.set(value)
        self.progress_label.config(text=text)

    def get_progress(self):
        """获取进度值"""
        return self.progress_var.get()


# ==================== 日志级别标签
class LogTag(Frame):
    """日志级别标签"""

    def __init__(self, parent, level='INFO', **kwargs):
        super().__init__(parent, **kwargs)

        colors = {
            'DEBUG': ('#3A3A3A', '#4A4A4A'),
            'INFO': ('#FFFFFF', '#58A6FF'),
            'WARNING': ('#FFFFFF', '#D29922'),
            'ERROR': ('#FFFFFF', '#F85149'),
            'SUCCESS': ('#FFFFFF', '#3FB950')
        }

        bg, fg = colors.get(level, colors['INFO'])

        self.label = Label(self, text=level, font=(FONT_FAMILY_UI, 9, 'bold'),
                          fg=fg, bg=bg, padx=6, pady=2)
        self.label.pack()


# ==================== 主 UI 类 ====================
class ModernNetworkInspectionUI:
    """网络设备巡检工具 - 现代科技风格 UI"""

    def __init__(self, root):
        debug_log("初始化现代科技风格 UI")
        self.root = root
        self.root.title("网络设备自动巡检工具 v2.0 | Network Device Inspector")

        # 设置窗口图标
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.ico")
            if os.path.exists(icon_path):
                self.root.iconbitmap(icon_path)
        except:
            pass

        # 窗口设置
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.minsize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # 设置窗口背景色
        self.root.configure(bg=theme_manager.get_color('BG_PRIMARY'))

        # 数据初始化
        self.device_types = {}
        self.devices = []
        self.original_devices = []
        self.command_files = {}
        self.device_types_file = ""
        self.devices_file = ""
        # 中文配置文件优先使用 GBK 编码，其他文件使用 UTF-8 优先
        self.encodings_config = ['gbk', 'gb2312', 'gb18030', 'utf-8', 'cp936', 'iso-8859-1']
        self.encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'cp936', 'iso-8859-1']
        self.inspection_running = False
        self.device_check_vars = {}
        self.search_var = None
        self.search_entry = None
        self._search_timer = None
        
        # 统计信息
        self.completed_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.total_duration = 0
        self.avg_response_time = 0
        self.success_rate = 0
        self.inspection_results = []

        # 创建 UI
        self.create_menu()
        self.create_ui()

        # 启动日志更新
        self.root.after(100, self.update_log)

        # 加载默认配置
        self.root.after(200, self.init_config_and_load_defaults)

    def create_menu(self):
        """创建菜单栏"""
        self.menubar = tk.Menu(self.root, bg=theme_manager.get_color('BG_CARD'), fg=theme_manager.get_color('FG_PRIMARY'))
        self.root.config(menu=self.menubar)

        # 文件菜单
        file_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'), fg=theme_manager.get_color('FG_PRIMARY'),
                           activebackground=theme_manager.get_color('ACCENT'), activeforeground='#ffffff')
        self.menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="开始巡检 (Ctrl+S)", command=self.start_inspection)
        file_menu.add_command(label="停止巡检 (Ctrl+T)", command=self.stop_inspection)
        file_menu.add_separator()
        file_menu.add_command(label="退出 (Ctrl+Q)", command=self.root.quit)

        # 设置菜单
        settings_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'), fg=theme_manager.get_color('FG_PRIMARY'),
                               activebackground=theme_manager.get_color('ACCENT'), activeforeground='#ffffff')
        self.menubar.add_cascade(label="设置", menu=settings_menu)
        settings_menu.add_command(label="加载设备列表", command=self.load_devices)
        settings_menu.add_command(label="加载设备类型", command=self.load_device_types)
        settings_menu.add_command(label="配置设备命令", command=self.configure_commands)
        settings_menu.add_separator()
        settings_menu.add_command(label="测试设备连通性", command=self.test_device_connectivity)

        # 关于菜单
        about_menu = tk.Menu(self.menubar, tearoff=0, bg=theme_manager.get_color('BG_CARD'), fg=theme_manager.get_color('FG_PRIMARY'),
                            activebackground=theme_manager.get_color('ACCENT'), activeforeground='#ffffff')
        self.menubar.add_cascade(label="关于", menu=about_menu)
        about_menu.add_command(label="配置使用指南", command=self.show_config_guide)
        about_menu.add_command(label="关于软件", command=self.show_about)

        # 绑定快捷键
        self.root.bind('<Control-s>', lambda e: self.start_inspection())
        self.root.bind('<Control-t>', lambda e: self.stop_inspection())
        self.root.bind('<Control-q>', lambda e: self.root.quit())
        self.root.bind('<F1>', lambda e: self.show_shortcuts_help())  # 快捷键帮助
        self.root.bind('<Control-h>', lambda e: self.toggle_high_contrast())  # 高对比度模式
        
        # 添加 Tab 键导航
        self.root.bind('<Tab>', self._handle_tab_navigation)
        
        # 设置焦点到第一个可聚焦元素
        self.root.after(100, self._set_initial_focus)

    def _set_initial_focus(self):
        """设置初始焦点"""
        # 尝试设置焦点到开始按钮
        try:
            self.start_btn.focus_set()
        except:
            pass

    def _handle_tab_navigation(self, event):
        """处理 Tab 键导航"""
        # 获取当前焦点部件
        current_widget = self.root.focus_get()
        
        # 定义焦点顺序
        focus_order = [
            self.start_btn,
            self.stop_btn,
            self.log_dir_btn,
            self.select_all_btn,
            self.invert_btn,
            self.deselect_btn,
            self.search_entry,
            self.device_tree,
            self.copy_log_btn,
            self.export_log_btn,
            self.clear_log_btn,
            self.log_text,
            self.concurrency_spinbox,
            self.encoding_combobox,
            self.timeout_combobox,
            self.log_level_combobox
        ]
        
        try:
            # 找到当前焦点部件在顺序中的位置
            current_idx = -1
            for i, widget in enumerate(focus_order):
                if hasattr(widget, 'winfo_exists') and widget.winfo_exists() and current_widget == widget:
                    current_idx = i
                    break
            
            # 找到下一个可聚焦的部件
            next_idx = (current_idx + 1) % len(focus_order)
            for i in range(len(focus_order)):
                idx = (next_idx + i) % len(focus_order)
                widget = focus_order[idx]
                if hasattr(widget, 'winfo_exists') and widget.winfo_exists():
                    try:
                        widget.focus_set()
                        break
                    except:
                        continue
        except:
            # 如果出现错误，尝试设置焦点到开始按钮
            try:
                self.start_btn.focus_set()
            except:
                pass
                
        return "break"  # 阻止默认的tab行为

    def create_ui(self):
        """创建主 UI"""
        # 主容器
        main_container = Frame(self.root, bg=theme_manager.get_color('BG_PRIMARY'))
        main_container.pack(fill='both', expand=True, padx=16, pady=12)

        # === 顶部标题栏 ===
        self.create_header_section(main_container)

        # === 工具栏 ===
        self.create_toolbar(main_container)

        # === 内容区域 ===
        content_frame = Frame(main_container, bg=theme_manager.get_color('BG_PRIMARY'))
        content_frame.pack(fill='both', expand=True, pady=12)

        # 左侧面板（设备列表 + 命令配置）
        left_panel = Frame(content_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        left_panel.pack(side='left', fill='both', expand=True, padx=(0, 6))

        # 设备列表
        self.create_device_panel(left_panel)

        # 右侧面板（日志区）
        right_panel = Frame(content_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        right_panel.pack(side='left', fill='both', expand=True, padx=(6, 0))

        # 日志区域
        self.create_log_panel(right_panel)

        # === 配置区域 ===
        self.create_config_section(main_container)

        # === 状态栏 ===
        self.create_status_bar(main_container)

    def create_header_section(self, parent):
        """创建顶部标题栏"""
        header_frame = Frame(parent, bg=theme_manager.get_color('BG_SECONDARY'))
        header_frame.pack(fill='x', pady=(0, 8))

        # 容器内边距
        inner_frame = Frame(header_frame, bg=theme_manager.get_color('BG_SECONDARY'))
        inner_frame.pack(fill='x', padx=20, pady=16)

        # 标题和副标题
        title_label = Label(inner_frame,
                           text="🖥️ 网络设备自动巡检工具",
                           font=(FONT_FAMILY_UI, 18, 'bold'),
                           fg=theme_manager.get_color('FG_PRIMARY'), 
                           bg=theme_manager.get_color('BG_SECONDARY'))
        title_label.pack(anchor='w')

        subtitle_label = Label(inner_frame,
                              text="Network Device Inspector v2.0 - Modern Light UI  |  by 刘华",
                              font=(FONT_FAMILY_UI, 10),
                              fg=theme_manager.get_color('FG_SECONDARY'), 
                              bg=theme_manager.get_color('BG_SECONDARY'))
        subtitle_label.pack(anchor='w', pady=(4, 0))

    def create_toolbar(self, parent):
        """创建工具栏"""
        toolbar_frame = Frame(parent, bg=theme_manager.get_color('BG_PRIMARY'))
        toolbar_frame.pack(fill='x', pady=(0, 8))

        # 左侧控制按钮
        left_controls = Frame(toolbar_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        left_controls.pack(side='left')

        # 开始/停止按钮
        self.start_btn = ModernButton(left_controls, "🚀 开始巡检", self.start_inspection,
                                      variant='secondary', width=140, height=38,
                                      aria_label="开始巡检按钮，用于启动网络设备巡检流程")
        self.start_btn.pack(side='left', padx=(0, 8))

        self.stop_btn = ModernButton(left_controls, "⏹ 停止巡检", self.stop_inspection,
                                     variant='secondary', width=120, height=38, state='disabled',
                                     aria_label="停止巡检按钮，用于中断正在进行的网络设备巡检")
        self.stop_btn.pack(side='left', padx=(0, 8))

        # 右侧按钮
        right_controls = Frame(toolbar_frame, bg=theme_manager.get_color('BG_PRIMARY'))
        right_controls.pack(side='right')

        # 导出结果按钮
        self.export_results_btn = ModernButton(right_controls, "📊 导出结果", self.export_results,
                                              variant='secondary', width=110, height=36,
                                              aria_label="导出结果按钮，用于将巡检结果导出为Excel文件")
        self.export_results_btn.pack(side='left', padx=(8, 0))

        # 统计报告按钮
        self.stats_report_btn = ModernButton(right_controls, "📈 统计报告", self.generate_statistics_report,
                                            variant='secondary', width=110, height=36,
                                            aria_label="统计报告按钮，用于生成巡检统计报告")
        self.stats_report_btn.pack(side='left', padx=(8, 0))

        # 日志目录按钮
        self.log_dir_btn = ModernButton(right_controls, "📁 日志目录", self.open_log_directory,
                                        variant='secondary', width=110, height=36,
                                        aria_label="打开日志目录按钮，用于打开存储巡检日志的文件夹")
        self.log_dir_btn.pack(side='left', padx=(8, 0))

    def create_device_panel(self, parent):
        """创建设备列表面板"""
        # 卡片容器
        device_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        device_card.pack(fill='both', expand=True, side='top')

        # 标题栏
        header_frame = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        header_frame.pack(fill='x', padx=16, pady=(16, 8))

        title_label = Label(header_frame,
                           text="📋 设备列表",
                           font=(FONT_FAMILY_UI, 14, 'bold'),
                           fg=theme_manager.get_color('FG_PRIMARY'), 
                           bg=theme_manager.get_color('BG_CARD'))
        title_label.pack(side='left')

        # 操作按钮
        btn_frame = Frame(header_frame, bg=theme_manager.get_color('BG_CARD'))
        btn_frame.pack(side='right')

        self.select_all_btn = ModernButton(btn_frame, "全选", self.select_all_devices,
                                           variant='secondary', width=60, height=30,
                                           aria_label="全选按钮，用于选中设备列表中的所有设备")
        self.select_all_btn.pack(side='left', padx=4)

        self.invert_btn = ModernButton(btn_frame, "反选", self.invert_select_devices,
                                       variant='secondary', width=60, height=30,
                                       aria_label="反选按钮，用于反转设备列表中当前的选择状态")
        self.invert_btn.pack(side='left', padx=4)

        self.deselect_btn = ModernButton(btn_frame, "清空", self.deselect_all_devices,
                                         variant='secondary', width=60, height=30,
                                         aria_label="清空按钮，用于取消选中设备列表中的所有设备")
        self.deselect_btn.pack(side='left', padx=4)

        # 搜索框 - 位于标题栏下方、设备列表上方
        search_frame = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        search_frame.pack(fill='x', padx=16, pady=(0, 8))

        self.search_var = StringVar()
        self.search_var.trace_add('write', self._on_search_changed)

        self.search_entry = ModernEntry(search_frame, placeholder="🔍 搜索设备名称、IP地址、设备类型...",
                                        width=40, font=(FONT_FAMILY_UI, 11),
                                        textvariable=self.search_var)
        self.search_entry.pack(side='left', fill='x', expand=True)

        # 设备列表容器
        list_container = Frame(device_card, bg=theme_manager.get_color('BG_CARD'))
        list_container.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        # Treeview 表格
        columns = ('select', 'device_name', 'ip', 'device_type', 'protocol')
        self.device_tree = Treeview(list_container, columns=columns, show='headings',
                                   style='DeviceTree.Treeview', selectmode='none')

        # 列设置
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

        # 滚动条
        scrollbar = ttk.Scrollbar(list_container, orient='vertical', command=self.device_tree.yview)
        self.device_tree.configure(yscrollcommand=scrollbar.set)

        self.device_tree.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 样式配置 - 现代化设计
        style = ttk.Style()
        style.theme_use('clam')  # 使用更现代的样式主题
        
        # 配置 Treeview 行样式
        style.configure('DeviceTree.Treeview',
                       background=theme_manager.get_color('BG_CARD'),
                       foreground=theme_manager.get_color('FG_PRIMARY'),
                       fieldbackground=theme_manager.get_color('BG_CARD'),
                       rowheight=36,  # 稍微增加行高，更现代化
                       font=(FONT_FAMILY_UI, 10),
                       borderwidth=0,
                       relief='flat',
                       padding=(0, 4, 0, 4))
        
        # 配置 Treeview 头部样式
        style.configure('DeviceTree.Treeview.Heading',
                       background=theme_manager.get_color('BG_SECONDARY'),
                       foreground=theme_manager.get_color('FG_PRIMARY'),
                       font=(FONT_FAMILY_UI, 10, 'bold'),
                       relief='flat',
                       padding=(10, 8, 10, 8))  # 增加头部内边距
        
        # 配置选中项样式
        style.map('DeviceTree.Treeview',
                 background=[('selected', theme_manager.get_color('ACCENT'))],
                 foreground=[('selected', '#ffffff')])
        
        # 配置 Treeview 边框
        style.configure('Treeview',
                       borderwidth=1,
                       focusthickness=1,
                       focuscolor=theme_manager.get_color('ACCENT'))

        # 点击事件
        self.device_tree.bind('<Button-1>', self.on_treeview_click)

    def create_log_panel(self, parent):
        """创建日志面板"""
        # 卡片容器 - 修改为与设备列表一致的颜色
        log_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        log_card.pack(fill='both', expand=True, side='top')

        # 标题栏
        header_frame = Frame(log_card, bg=theme_manager.get_color('BG_CARD'))
        header_frame.pack(fill='x', padx=16, pady=(16, 8))

        title_label = Label(header_frame,
                           text="📝 运行日志",
                           font=(FONT_FAMILY_UI, 14, 'bold'),
                           fg=theme_manager.get_color('FG_PRIMARY'), 
                           bg=theme_manager.get_color('BG_CARD'))
        title_label.pack(side='left')

        # 操作按钮
        btn_frame = Frame(header_frame, bg=theme_manager.get_color('BG_CARD'))
        btn_frame.pack(side='right')

        self.copy_log_btn = ModernButton(btn_frame, "📋 复制", self.copy_log,
                                         variant='secondary', width=70, height=30,
                                         aria_label="复制日志按钮，用于将当前日志内容复制到剪贴板")
        self.copy_log_btn.pack(side='left', padx=4)

        self.export_log_btn = ModernButton(btn_frame, "💾 导出", self.export_log,
                                           variant='secondary', width=70, height=30,
                                           aria_label="导出日志按钮，用于将当前日志保存为文件")
        self.export_log_btn.pack(side='left', padx=4)

        self.clear_log_btn = ModernButton(btn_frame, "🗑 清空", self.clear_log,
                                          variant='secondary', width=70, height=30,
                                          aria_label="清空日志按钮，用于清除当前显示的日志内容")
        self.clear_log_btn.pack(side='left', padx=4)

        # 日志文本区
        text_container = Frame(log_card, bg=theme_manager.get_color('BG_CARD'))
        text_container.pack(fill='both', expand=True, padx=16, pady=(0, 16))

        self.log_text = Text(text_container,
                            wrap='word',
                            state='disabled',
                            bg=theme_manager.get_color('BG_CARD'),  # 修改为与设备列表一致
                            fg=theme_manager.get_color('FG_PRIMARY'),
                            font=(FONT_FAMILY_CODE, 10),
                            relief='flat',
                            bd=0,
                            padx=12,  # 增加内边距，更现代化
                            pady=12,
                            spacing1=2,  # 行间距
                            spacing3=2,
                            insertbackground=theme_manager.get_color('ACCENT'),
                            selectbackground=theme_manager.get_color('ACCENT'),
                            selectforeground='#ffffff',
                            cursor='arrow')

        # 滚动条 - 现代化样式
        scrollbar = ttk.Scrollbar(text_container, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        self.log_text.pack(side='left', fill='both', expand=True)
        scrollbar.pack(side='right', fill='y')

        # 配置日志标签颜色 - 使用主题管理器
        self.log_text.tag_config('DEBUG', foreground=theme_manager.get_color('FG_MUTED'))
        self.log_text.tag_config('INFO', foreground=theme_manager.get_color('ACCENT'))
        self.log_text.tag_config('WARNING', foreground=theme_manager.get_color('WARNING'))
        self.log_text.tag_config('ERROR', foreground=theme_manager.get_color('ERROR'))
        self.log_text.tag_config('SUCCESS', foreground=theme_manager.get_color('SUCCESS'))
        self.log_text.tag_config('timestamp', foreground=theme_manager.get_color('FG_MUTED'))
        
        # 配置滚动条样式
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
        """创建配置区域"""
        config_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        config_card.pack(fill='x', pady=(0, 8))

        # 标题
        title_label = Label(config_card,
                           text="⚙️ 巡检配置",
                           font=(FONT_FAMILY_UI, 13, 'bold'),
                           fg=theme_manager.get_color('FG_PRIMARY'), 
                           bg=theme_manager.get_color('BG_CARD'))
        title_label.pack(anchor='w', padx=16, pady=(12, 8))

        # 配置项容器
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

    def create_status_bar(self, parent):
        """创建状态栏"""
        status_card = Frame(parent, bg=theme_manager.get_color('BG_CARD'))
        status_card.pack(fill='x')

        # 状态栏容器
        inner_frame = Frame(status_card, bg=theme_manager.get_color('BG_CARD'))
        inner_frame.pack(fill='x', padx=16, pady=12)

        # 状态文字
        self.status_var = StringVar(value="正在加载配置...")
        self.status_label = Label(inner_frame, textvariable=self.status_var,
                                  font=(FONT_FAMILY_UI, 11),
                                  fg=theme_manager.get_color('FG_SECONDARY'), 
                                  bg=theme_manager.get_color('BG_CARD'))
        self.status_label.pack(side='left')

        # 详细进度条
        self.progress_var = tk.IntVar(value=0)
        self.progress_bar = DetailedProgressbar(inner_frame)
        self.progress_bar.pack(side='left', padx=(24, 0), fill='x', expand=True)
        self.progress_bar.progress_bar.config(length=300)

        # 状态指示器
        self.status_indicator = Label(inner_frame, text="●",
                                      font=(FONT_FAMILY_UI, 16),
                                      fg=theme_manager.get_color('INFO'), 
                                      bg=theme_manager.get_color('BG_CARD'))
        self.status_indicator.pack(side='right', padx=(8, 0))

        # 版本信息
        version_label = Label(inner_frame, text="v2.0",
                              font=(FONT_FAMILY_UI, 9),
                              fg=theme_manager.get_color('FG_MUTED'), 
                              bg=theme_manager.get_color('BG_CARD'))
        version_label.pack(side='right')

    # ==================== 功能方法 ====================

    def init_config_and_load_defaults(self):
        """初始化配置并加载默认值"""
        debug_log("初始化配置目录并加载默认配置")

        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            os.makedirs(COMMANDS_DIR, exist_ok=True)
            debug_log(f"配置目录：{CONFIG_DIR}")
            debug_log(f"命令目录：{COMMANDS_DIR}")

            # 在后台线程加载配置，避免阻塞 UI
            self.status_var.set("正在加载配置文件...")
            threading.Thread(target=self.load_defaults_in_background, daemon=True).start()

        except Exception as e:
            msg = f"初始化配置目录失败：{str(e)}"
            LOG_QUEUE.put(msg)
            debug_log(msg)
            self.status_var.set(f"初始化失败：{str(e)}")

    def load_defaults_in_background(self):
        """在后台线程加载默认配置"""
        try:
            self.auto_load_default_configs()
        except Exception as e:
            msg = f"加载配置失败：{str(e)}"
            LOG_QUEUE.put(msg)
            debug_log(msg)
            self.root.after(0, lambda: self.status_var.set(f"加载配置失败：{str(e)}"))

    def auto_load_default_configs(self):
        """自动加载默认配置"""
        success = True

        # 加载设备类型 - 使用 GBK 优先编码
        if DEFAULT_DEVICE_TYPES_FILE and os.path.exists(DEFAULT_DEVICE_TYPES_FILE):
            self.device_types = load_device_types_config(DEFAULT_DEVICE_TYPES_FILE, self.encodings_config)
            self.device_types_file = DEFAULT_DEVICE_TYPES_FILE
        else:
            LOG_QUEUE.put("未找到默认设备类型配置文件")
            success = False

        # 加载设备列表 - 使用 GBK 优先编码
        if DEFAULT_DEVICES_FILE and os.path.exists(DEFAULT_DEVICES_FILE):
            self.devices = load_devices(DEFAULT_DEVICES_FILE, self.encodings_config)
            self.original_devices = self.devices.copy()
            self.devices_file = DEFAULT_DEVICES_FILE
        else:
            LOG_QUEUE.put("未找到默认设备列表配置文件")
            success = False

        # 关联命令文件
        self.auto_associate_commands_from_device_types()

        # 更新显示
        self.update_config_file_display()
        self.update_device_listbox()
        self.update_commands_listbox()

        # 验证配置
        valid_device_types = validate_device_types_config(self.device_types)
        valid_devices = validate_devices_config(self.devices, self.device_types) if self.devices else False
        valid_commands = validate_commands_config(self.device_types, self.command_files)

        self.update_start_button_state()

        if success and valid_device_types and valid_devices and valid_commands:
            self.status_var.set("所有配置加载完成，可以开始巡检")
            self.update_status_indicator('success')
        else:
            self.status_var.set("部分配置缺失，请检查日志")
            self.update_status_indicator('warning')

    def auto_associate_commands_from_device_types(self):
        """从设备类型配置中自动关联命令文件"""
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

        LOG_QUEUE.put(f"命令文件关联完成：成功{loaded_count}个，失败{failed_count}个")

    def _load_command_file_for_type(self, type_id, cmd_file_name):
        """为指定设备类型加载命令文件"""
        possible_paths = [
            cmd_file_name,
            os.path.join(COMMANDS_DIR, cmd_file_name),
            os.path.join(os.path.dirname(self.device_types_file), cmd_file_name) if self.device_types_file else None,
            os.path.join(os.getcwd(), 'config', 'commands', cmd_file_name)
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
        """更新配置文件路径显示"""
        if self.device_types_file:
            display_path = self.shorten_path(self.device_types_file)
            LOG_QUEUE.put(f"设备类型配置：{display_path}")
        if self.devices_file:
            display_path = self.shorten_path(self.devices_file)
            LOG_QUEUE.put(f"设备列表配置：{display_path}")

    def shorten_path(self, path, max_length=50):
        """缩短路径显示"""
        if not path:
            return ""
        if len(path) <= max_length:
            return path
        head_length = int(max_length * 0.4)
        tail_length = max_length - head_length - 3
        return f"{path[:head_length]}...{path[-tail_length:]}"

    def update_device_listbox(self):
        """更新设备列表显示"""
        for item in self.device_tree.get_children():
            self.device_tree.delete(item)

        self.device_check_vars = {}

        if not self.devices:
            if not hasattr(self, 'original_devices') or not self.original_devices:
                self.device_tree.insert('', 'end', values=('', '请先加载设备列表', '', '', ''), tags=('empty',))
            else:
                self.device_tree.insert('', 'end', values=('', '无匹配的设备', '', '', ''), tags=('empty',))
            return

        for idx, device in enumerate(self.devices):
            device_type_id = device.get('device_type', '')
            type_name = self.device_types.get(device_type_id, {}).get('name', device_type_id)
            protocol = device.get('protocol', '').upper() or 'SSH'
            port = device.get('port', 22)

            unique_key = f"{device['device_name']}_{device['ip']}"
            var = IntVar(value=1 if device.get('selected', True) else 0)
            self.device_check_vars[unique_key] = var

            checkbox_display = '☑' if device.get('selected', True) else '☐'
            ip_port = f"{device['ip']}:{port}"

            self.device_tree.insert('', 'end', iid=unique_key, values=(
                checkbox_display,
                device['device_name'],
                ip_port,
                type_name,
                protocol
            ), tags=('device',))

    def on_treeview_click(self, event):
        """处理 Treeview 点击事件"""
        region = self.device_tree.identify_region(event.x, event.y)

        if region in ('cell', 'tree'):
            item_id = self.device_tree.identify_row(event.y)
            if item_id:
                target_device = None
                target_index = None
                for idx, device in enumerate(self.devices):
                    unique_key = f"{device['device_name']}_{device['ip']}"
                    if unique_key == item_id:
                        target_device = device
                        target_index = idx
                        break

                if target_device is None:
                    return

                current_state = target_device.get('selected', True)
                new_state = not current_state
                target_device['selected'] = new_state

                if item_id in self.device_check_vars:
                    self.device_check_vars[item_id].set(1 if new_state else 0)

                checkbox_display = '☑' if new_state else '☐'
                current_values = self.device_tree.item(item_id, 'values')
                if current_values:
                    new_values = (checkbox_display,) + current_values[1:]
                    self.device_tree.item(item_id, values=new_values)

    def update_commands_listbox(self):
        """更新命令配置列表"""
        pass  # 简化版本，可以在需要时添加

    def select_all_devices(self):
        """全选设备"""
        for device in self.devices:
            device['selected'] = True
        for var in self.device_check_vars.values():
            var.set(1)
        for item_id in self.device_tree.get_children():
            current_values = self.device_tree.item(item_id, 'values')
            if current_values:
                new_values = ('☑',) + current_values[1:]
                self.device_tree.item(item_id, values=new_values)
        LOG_QUEUE.put("已全选所有设备")

    def deselect_all_devices(self):
        """取消全选"""
        for device in self.devices:
            device['selected'] = False
        for var in self.device_check_vars.values():
            var.set(0)
        for item_id in self.device_tree.get_children():
            current_values = self.device_tree.item(item_id, 'values')
            if current_values:
                new_values = ('☐',) + current_values[1:]
                self.device_tree.item(item_id, values=new_values)
        LOG_QUEUE.put("已清空所有设备选择")

    def invert_select_devices(self):
        """反选设备"""
        device_key_to_idx = {}
        for idx, device in enumerate(self.devices):
            unique_key = f"{device['device_name']}_{device['ip']}"
            device_key_to_idx[unique_key] = idx

        for device in self.devices:
            device['selected'] = not device.get('selected', True)

        for var in self.device_check_vars.values():
            current = var.get()
            var.set(0 if current == 1 else 1)

        for item_id in self.device_tree.get_children():
            if item_id in device_key_to_idx:
                idx = device_key_to_idx[item_id]
                current_values = self.device_tree.item(item_id, 'values')
                if current_values:
                    checkbox_display = '☑' if self.devices[idx]['selected'] else '☐'
                    new_values = (checkbox_display,) + current_values[1:]
                    self.device_tree.item(item_id, values=new_values)
        LOG_QUEUE.put("已反选设备")

    def update_start_button_state(self):
        """更新开始按钮状态"""
        valid_device_types = validate_device_types_config(self.device_types)
        valid_devices = validate_devices_config(self.devices, self.device_types) if self.devices else False
        valid_commands = validate_commands_config(self.device_types, self.command_files)

        state = 'normal' if (valid_device_types and valid_devices and valid_commands) else 'disabled'
        self.start_btn.config(state=state)

    def update_status_indicator(self, status):
        """更新状态指示器颜色"""
        colors = {
            'ready': theme_manager.get_color('FG_MUTED'),
            'running': theme_manager.get_color('ACCENT'),
            'success': theme_manager.get_color('SUCCESS'),
            'warning': theme_manager.get_color('WARNING'),
            'error': theme_manager.get_color('ERROR')
        }
        color = colors.get(status, theme_manager.get_color('FG_MUTED'))
        self.status_indicator.config(fg=color)

    # ==================== 搜索功能 ====================

    def _on_search_changed(self, *args):
        """搜索框内容变化"""
        if hasattr(self, '_search_timer') and self._search_timer:
            self.root.after_cancel(self._search_timer)
        self._search_timer = self.root.after(150, self._do_real_time_search)

    def _do_real_time_search(self):
        """执行实时搜索"""
        # 获取搜索文本，处理占位符情况
        search_text = self.search_var.get()
        
        # 如果为空或仍是占位符，恢复所有设备
        if not search_text or search_text == "🔍 搜索设备名称、IP地址、设备类型...":
            self._restore_original_devices()
            return

        search_term = search_text.lower()
        self._filter_devices(search_term)

    def _restore_original_devices(self):
        """恢复显示所有设备"""
        self.devices = self.original_devices.copy()
        self.update_device_listbox()

    def _filter_devices(self, search_term):
        """过滤设备"""
        filtered_devices = []
        for device in self.original_devices:
            device_type_id = device.get('device_type', '')
            type_name = self.device_types.get(device_type_id, {}).get('name', device_type_id)
            protocol = device.get('protocol', '').upper() or 'SSH'
            port = device.get('port', 22)
            protocol_port = f"{protocol}:{port}"

            if (search_term in device['device_name'].lower() or
                search_term in device['ip'].lower() or
                search_term in device['device_type'].lower() or
                search_term in type_name.lower() or
                search_term in protocol_port.lower()):
                filtered_devices.append(device)

        self.devices = filtered_devices
        self.update_device_listbox()

        if filtered_devices:
            self.device_tree.yview_moveto(0.0)

    # ==================== 日志操作 ====================

    def update_log(self):
        """更新日志显示 - 批量处理优化"""
        batch_size = 0
        max_batch = 50  # 每批最多处理50条
        should_scroll = False
        log_entries = []  # 批量收集日志条目

        while batch_size < max_batch:
            try:
                msg = LOG_QUEUE.get_nowait()  # 非阻塞获取
                timestamp = datetime.now().strftime('%H:%M:%S')

                # 解析日志级别
                level = 'INFO'
                for lvl in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'SUCCESS', 'CRITICAL']:
                    if f'[{lvl}]' in msg or lvl in msg:
                        level = lvl
                        break

                # 应用日志级别过滤
                if not self._should_show_log_level(level):
                    batch_size += 1
                    LOG_QUEUE.task_done()
                    continue

                # 收集日志条目，稍后一次性插入
                log_line = f"[{timestamp}] {msg}\n"
                log_entries.append((log_line, level))

                batch_size += 1
                should_scroll = True
                LOG_QUEUE.task_done()

            except queue.Empty:
                break

        # 批量插入日志，减少UI更新次数
        if log_entries:
            self.log_text.config(state='normal')
            for log_line, level in log_entries:
                self.log_text.insert(END, log_line, level)

        # 批量滚动一次
        if should_scroll:
            self.log_text.see(END)
            # 限制日志行数，防止内存泄漏
            self._limit_log_lines(5000)

        self.root.after(100, self.update_log)  # 提高响应性到100ms

    def _should_show_log_level(self, level):
        """判断是否应显示指定日志级别"""
        # 默认显示所有级别，可根据需要实现过滤逻辑
        # 例如，只显示INFO及以上级别的日志
        log_level_priority = {'DEBUG': 0, 'INFO': 1, 'WARNING': 2, 'ERROR': 3, 'CRITICAL': 4, 'SUCCESS': 1}
        min_level = getattr(self, 'min_log_level', 'DEBUG')  # 可通过配置设置最低显示级别
        return log_level_priority.get(level, 1) >= log_level_priority.get(min_level, 0)

    def _limit_log_lines(self, max_lines=5000):
        """限制日志行数，防止内存泄漏"""
        try:
            current_lines = int(self.log_text.index('end-1c').split('.')[0])
            if current_lines > max_lines:
                self.log_text.config(state='normal')
                self.log_text.delete('1.0', f'{current_lines - max_lines}.0')
                self.log_text.config(state='disabled')
        except:
            pass

    def copy_log(self):
        """复制日志"""
        log_content = self.log_text.get('1.0', END)
        self.root.clipboard_clear()
        self.root.clipboard_append(log_content)
        LOG_QUEUE.put("日志已复制到剪贴板")

    def export_log(self):
        """导出日志"""
        file_path = filedialog.asksaveasfilename(
            title="导出日志",
            defaultextension=".txt",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if file_path:
            try:
                log_content = self.log_text.get('1.0', END)
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(log_content)
                LOG_QUEUE.put(f"日志已导出：{file_path}")
            except Exception as e:
                log_error(f"导出日志失败：{e}")

    def clear_log(self):
        """清空日志"""
        if messagebox.askyesno("确认", "确定要清空日志吗？"):
            self.log_text.config(state='normal')
            self.log_text.delete('1.0', END)
            self.log_text.config(state='disabled')
            LOG_QUEUE.put("日志已清空")

    # ==================== 菜单功能 ====================

    def show_shortcuts_help(self):
        """显示快捷键帮助"""
        shortcuts_text = """快捷键帮助

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
• 设备列表中可通过上下箭头键选择设备"""
        messagebox.showinfo("快捷键帮助", shortcuts_text)

    def show_about(self):
        """显示关于"""
        about_text = """网络设备自动巡检工具 v2.0


主要功能：
• 支持多厂商设备（华为、思科、H3C、Juniper 等）
• 多线程并发巡检
• 智能编码输出处理
• 现代化用户界面

作者：刘华"""
        messagebox.showinfo("关于软件", about_text)

    def toggle_high_contrast(self):
        """切换高对比度模式"""
        is_high_contrast = theme_manager.toggle_high_contrast()
        status = "已开启" if is_high_contrast else "已关闭"
        LOG_QUEUE.put(f"高对比度模式{status}")
        self.status_var.set(f"高对比度模式{status}")
        
        # 可以在这里添加重新绘制UI的逻辑，如果需要的话
        # 目前依赖于动态颜色获取，无需手动重绘

    def export_results(self):
        """导出巡检结果"""
        # 检查是否有结果可以导出
        if not hasattr(self, 'inspection_results') or not self.inspection_results:
            messagebox.showwarning("警告", "没有巡检结果可以导出")
            return

        # 选择保存路径
        file_path = filedialog.asksaveasfilename(
            title="导出巡检结果",
            defaultextension=".xlsx",
            filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
        )

        if not file_path:
            return

        try:
            import pandas as pd
            from datetime import datetime

            # 创建DataFrame
            df_data = []
            for result in self.inspection_results:
                df_data.append({
                    '设备名称': result.get('device_name', ''),
                    'IP地址': result.get('ip', ''),
                    '设备类型': result.get('device_type', ''),
                    '巡检状态': result.get('status', ''),
                    '开始时间': result.get('start_time', ''),
                    '结束时间': result.get('end_time', ''),
                    '耗时(秒)': result.get('duration', 0),
                    '错误信息': result.get('error', '')
                })

            df = pd.DataFrame(df_data)

            # 保存为Excel文件
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='巡检结果', index=False)

                # 获取工作表并设置列宽
                worksheet = writer.sheets['巡检结果']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            LOG_QUEUE.put(f"巡检结果已导出至：{file_path}")
            messagebox.showinfo("成功", f"巡检结果已导出至：{file_path}")
        except ImportError:
            messagebox.showerror("错误", "导出功能需要安装pandas库：pip install pandas openpyxl")
        except Exception as e:
            log_error(f"导出巡检结果失败：{e}")
            messagebox.showerror("错误", f"导出巡检结果失败：{str(e)}")

    def generate_statistics_report(self):
        """生成统计报告"""
        try:
            import pandas as pd
            from datetime import datetime

            # 计算统计信息
            total_devices = len(self.devices) if hasattr(self, 'devices') else 0
            selected_devices = len([d for d in self.devices if d.get('selected', True)]) if hasattr(self, 'devices') else 0
            
            # 生成报告
            stats_data = {
                '统计项目': [
                    '总设备数',
                    '选中设备数',
                    '巡检完成数',
                    '巡检成功率',
                    '平均响应时间(秒)',
                    '最新巡检时间'
                ],
                '数值': [
                    total_devices,
                    selected_devices,
                    getattr(self, 'completed_count', 0),
                    f"{getattr(self, 'success_rate', 0):.2f}%",
                    f"{getattr(self, 'avg_response_time', 0):.2f}",
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                ]
            }

            df_stats = pd.DataFrame(stats_data)

            # 选择保存路径
            file_path = filedialog.asksaveasfilename(
                title="导出统计报告",
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("所有文件", "*.*")]
            )

            if not file_path:
                return

            # 保存为Excel文件
            with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
                df_stats.to_excel(writer, sheet_name='统计报告', index=False)

                # 获取工作表并设置列宽
                worksheet = writer.sheets['统计报告']
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 30)
                    worksheet.column_dimensions[column_letter].width = adjusted_width

            LOG_QUEUE.put(f"统计报告已导出至：{file_path}")
            messagebox.showinfo("成功", f"统计报告已导出至：{file_path}")
        except ImportError:
            messagebox.showerror("错误", "统计报告功能需要安装pandas库：pip install pandas openpyxl")
        except Exception as e:
            log_error(f"生成统计报告失败：{e}")
            messagebox.showerror("错误", f"生成统计报告失败：{str(e)}")

    def show_config_guide(self):
        """显示配置指南"""
        guide_text = """网络设备自动巡检工具配置指南

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

详细配置请查看 巡检指南/配置使用指南.md"""
        messagebox.showinfo("配置使用指南", guide_text)

    def load_device_types(self):
        """加载设备类型"""
        initial_dir = CONFIG_DIR if os.path.exists(CONFIG_DIR) else os.getcwd()

        file_path = filedialog.askopenfilename(
            title="选择设备类型配置文件",
            filetypes=[("配置文件", "*.csv *.txt"), ("所有文件", "*.*")],
            initialdir=initial_dir
        )

        if not file_path:
            return

        self.status_var.set("正在加载设备类型配置...")
        # 使用 GBK 优先编码加载配置文件
        self.device_types = load_device_types_config(file_path, self.encodings_config)
        self.device_types_file = file_path

        self.auto_associate_commands_from_device_types()
        self.update_config_file_display()
        self.update_commands_listbox()

        valid = validate_device_types_config(self.device_types)
        self.update_start_button_state()

        if valid:
            msg = f"成功加载 {len(self.device_types)} 种设备类型配置"
            self.status_var.set(msg)
            self.update_status_indicator('success')
        else:
            self.status_var.set("设备类型配置验证失败")
            self.update_status_indicator('error')

    def load_devices(self):
        """加载设备列表"""
        initial_dir = CONFIG_DIR if os.path.exists(CONFIG_DIR) else os.getcwd()

        file_path = filedialog.askopenfilename(
            title="选择设备列表配置文件",
            filetypes=[("配置文件", "*.csv *.txt"), ("所有文件", "*.*")],
            initialdir=initial_dir
        )

        if not file_path:
            return

        # 验证文件是否存在
        if not os.path.exists(file_path):
            messagebox.showerror("错误", f"文件不存在：{file_path}")
            return

        # 验证文件扩展名
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in ['.csv', '.txt']:
            messagebox.showwarning("警告", f"不推荐的文件格式：{ext}，建议使用 .csv 或 .txt 文件")

        # 验证配置文件格式
        required_columns = ['device_name', 'ip', 'device_type']
        is_valid, validation_errors = validate_config_file(file_path, required_columns)
        if not is_valid:
            error_msg = "配置文件格式错误：\n" + "\n".join(validation_errors)
            messagebox.showerror("错误", error_msg)
            return

        self.status_var.set("正在加载设备列表...")
        # 使用 GBK 优先编码加载配置文件
        self.devices = load_devices(file_path, self.encodings_config)
        self.original_devices = self.devices.copy()
        self.devices_file = file_path

        self.update_device_listbox()
        self.update_config_file_display()

        # 验证设备配置
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
            # 显示详细错误信息
            error_details = "\n".join(validation_result['errors'])
            LOG_QUEUE.put(f"设备配置验证错误：\n{error_details}")

    def configure_commands(self):
        """配置设备命令"""
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
              fg=theme_manager.get_color('FG_PRIMARY'), bg=theme_manager.get_color('BG_CARD')).pack(pady=(0, 8))

        listbox = tk.Listbox(frame, bg=theme_manager.get_color('BG_CARD'), fg=theme_manager.get_color('FG_PRIMARY'),
                            font=(FONT_FAMILY_UI, 11))
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=listbox.yview)
        listbox.config(yscrollcommand=scrollbar.set)

        type_ids = list(self.device_types.keys())
        for i, type_id in enumerate(type_ids):
            type_name = self.device_types[type_id]['name']
            cmd_file = self.command_files.get(type_id, ("", []))[0] or "未配置"
            listbox.insert(END, f"{type_id}: {type_name} - 命令文件：{cmd_file}")

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
                title=f"选择命令文件",
                filetypes=[("命令文件", "*.txt"), ("所有文件", "*.*")],
                initialdir=COMMANDS_DIR
            )

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
                     aria_label="选择命令文件按钮，用于为所选设备类型选择命令配置文件").pack(side='left', padx=4)
        ModernButton(btn_frame, "完成", dialog.destroy, variant='secondary', width=80,
                     aria_label="完成配置按钮，用于关闭设备命令配置对话框").pack(side='right')

    def open_log_directory(self):
        """打开日志目录"""
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

    # ==================== 巡检功能 ====================

    def start_inspection(self):
        """开始巡检"""
        if not NETMIKO_AVAILABLE:
            messagebox.showerror("错误", "缺少依赖库 netmiko，无法执行巡检。请运行：pip install netmiko")
            return

        if self.inspection_running:
            return

        # 检查选中的设备
        selected_count = sum(1 for d in self.devices if d.get('selected', True))
        if selected_count == 0:
            messagebox.showwarning("警告", "请至少选择一台设备进行巡检")
            return

        # 获取并发数
        try:
            max_workers = int(self.concurrency_var.get())
            if max_workers < 1 or max_workers > 50:
                raise ValueError("并发数必须在 1-50 之间")
        except ValueError as e:
            messagebox.showerror("错误", f"并发数设置错误：{str(e)}")
            return

        # 获取编码配置
        selected_encoding = self.encoding_var.get()
        if selected_encoding == "自动检测":
            selected_encodings = self.encodings
            LOG_QUEUE.put("使用自动编码检测模式")
        else:
            encoding_map = {"UTF-8": "utf-8", "GBK": "gbk", "GB2312": "gb2312",
                          "GB18030": "gb18030", "Big5": "big5"}
            primary = encoding_map.get(selected_encoding, "utf-8")
            selected_encodings = [primary] + [e for e in self.encodings if e != primary]
            LOG_QUEUE.put(f"优先使用编码：{selected_encoding}")

        self.inspection_running = True
        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.update_status_indicator('running')

        self.status_var.set("开始巡检...")
        self.progress_var.set(0)
        debug_log("开始巡检")

        # 启动工作线程
        threading.Thread(
            target=inspection_worker,
            args=(self.devices, self.device_types, self.command_files,
                  selected_encodings, self.status_var, self.progress_var, max_workers),
            daemon=True
        ).start()

        self.root.after(1000, self.check_inspection_complete)

    def stop_inspection(self):
        """停止巡检"""
        global stop_event
        if not self.inspection_running:
            return

        if messagebox.askyesno("确认停止", "确定要停止当前巡检吗？未完成的设备将被中断。"):
            stop_event.set()  # 线程安全地设置停止信号
            self.status_var.set("正在停止巡检...")
            self.stop_btn.config(state='disabled')

    def test_device_connectivity(self):
        """测试设备连通性"""
        if not NETMIKO_AVAILABLE:
            messagebox.showerror("错误", "缺少依赖库 netmiko，无法执行连通性测试。请运行：pip install netmiko")
            return

        selected_items = [item for item, var in self.device_check_vars.items() if var.get() == 1]
        if not selected_items:
            messagebox.showwarning("警告", "请至少选择一台设备进行连通性测试")
            return

        # 获取选中的设备
        selected_devices = [d for d in self.devices if d.get('selected', True)]

        # 创建进度对话框
        progress_dialog = tk.Toplevel(self.root)
        progress_dialog.title("设备连通性测试")
        progress_dialog.geometry("500x300")
        progress_dialog.transient(self.root)
        progress_dialog.grab_set()

        # 进度标签
        progress_label = Label(progress_dialog, text="开始测试设备连通性...", font=(FONT_FAMILY_UI, 11))
        progress_label.pack(pady=20)

        # 进度条
        progress_bar = ttk.Progressbar(progress_dialog, mode='determinate')
        progress_bar.pack(fill='x', padx=20, pady=10)
        progress_bar['maximum'] = len(selected_devices)

        # 结果显示区域
        result_text = Text(progress_dialog, wrap='word', state='normal',
                          font=(FONT_FAMILY_CODE, 10), height=10)
        scrollbar = ttk.Scrollbar(result_text)
        result_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=result_text.yview)

        result_text.pack(fill='both', expand=True, padx=20, pady=10)
        scrollbar.pack(side='right', fill='y')

        # 关闭按钮
        close_btn = ModernButton(progress_dialog, "关闭", progress_dialog.destroy,
                                variant='secondary', width=80, height=30)
        close_btn.pack(pady=10)

        # 开始测试
        def run_test():
            success_count = 0
            total_count = len(selected_devices)
            for i, device in enumerate(selected_devices):
                if stop_event.is_set():
                    break
                
                progress_label.config(text=f"正在测试 {device['device_name']} ({i+1}/{total_count})...")
                progress_bar['value'] = i + 1
                self.root.update_idletasks()

                # 尝试连接设备
                try:
                    device_type_id = device['device_type']
                    if device_type_id not in self.device_types:
                        result_text.insert(END, f"✗ {device['device_name']}({device['ip']}) - 未知设备类型\n")
                        result_text.see(END)
                        continue

                    device_config = self.device_types[device_type_id]
                    
                    protocol = device.get('protocol', 'ssh') or device_config['default_protocol']
                    device_driver = device_config['netmiko_type'][protocol]

                    device_info = {
                        'device_type': device_driver,
                        'ip': device['ip'],
                        'port': device.get('port', 22),
                        'timeout': 10,  # 较短的超时时间
                        'global_delay_factor': 2,
                        'read_timeout_override': 30,
                    }

                    if device.get('username'):
                        device_info['username'] = device['username']
                    if device.get('password'):
                        device_info['password'] = device['password']
                    if device.get('secret'):
                        device_info['secret'] = device['secret']

                    # 尝试连接
                    connection = connect_with_retry(device_info, max_retries=1, retry_delay=1)
                    if connection:
                        connection.disconnect()
                        result_text.insert(END, f"✓ {device['device_name']}({device['ip']}) - 连接成功\n")
                        result_text.see(END)
                        success_count += 1
                    else:
                        result_text.insert(END, f"✗ {device['device_name']}({device['ip']}) - 连接失败\n")
                        result_text.see(END)
                except Exception as e:
                    result_text.insert(END, f"✗ {device['device_name']}({device['ip']}) - 错误: {str(e)}\n")
                    result_text.see(END)

            progress_label.config(text=f"测试完成: {success_count}/{total_count} 台设备连通")
            result_text.insert(END, f"\n测试总结: {success_count}/{total_count} 台设备连通\n")
            result_text.see(END)

        # 在后台线程中运行测试
        threading.Thread(target=run_test, daemon=True).start()

    def check_inspection_complete(self):
        """检查巡检是否完成"""
        if not self.inspection_running:
            return

        if self.progress_var.get() == 100 or stop_event.is_set():
            self.inspection_running = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            self.update_status_indicator('success' if self.progress_var.get() == 100 else 'warning')
            
            # 更新统计信息
            selected_devices = [d for d in self.devices if d.get('selected', True)]
            total_selected = len(selected_devices)
            self.completed_count = total_selected
            # 这里需要从巡检结果中获取成功数量
            # 临时使用状态更新中的成功数量
            status_text = self.status_var.get()
            if "成功" in status_text:
                try:
                    # 提取成功数量，例如："巡检完成：共5台，成功4台"
                    parts = status_text.split("，")
                    for part in parts:
                        if "成功" in part:
                            self.success_count = int(part.replace("成功", "").replace("台", ""))
                            break
                    self.failed_count = total_selected - self.success_count
                    self.success_rate = (self.success_count / total_selected) * 100 if total_selected > 0 else 0
                except:
                    self.success_count = 0
                    self.failed_count = total_selected
                    self.success_rate = 0
            return

        self.root.after(1000, self.check_inspection_complete)


# ==================== 巡检工作线程 ====================

def inspection_worker(devices, device_types, command_files, encodings, status_var, progress_var, max_workers=5):
    """巡检工作线程 - 使用线程池优化"""
    global stop_event
    stop_event.clear()  # 清除之前的停止信号

    try:
        selected_devices = [d for d in devices if d.get('selected', True)]
        total_devices = len(selected_devices)

        if total_devices == 0:
            status_var.set("没有选中任何设备")
            LOG_QUEUE.put("没有选中任何设备进行巡检")
            return

        success_count = 0
        interrupted = False
        lock = threading.Lock()

        # 动态调整线程数：如果设备数量少于最大线程数，则使用设备数量
        actual_max_workers = min(max_workers, len(selected_devices))
        
        def process_device(device, index):
            """处理单个设备"""
            nonlocal success_count
            if stop_event.is_set():
                return False

            success, log_file = connect_and_execute(device, device_types, command_files, encodings)
            with lock:
                if success:
                    success_count += 1
                processed = index + 1
                status_var.set(f"正在处理 {device['device_name']} ({processed}/{total_devices})")

                # 如果是自定义的DetailedProgressbar，则使用set_progress方法
                if hasattr(progress_var, 'set_progress'):
                    progress_var.set_progress(
                        int((processed / total_devices) * 100),
                        f"已完成 {processed}/{total_devices} 台设备"
                    )
                else:
                    progress_var.set(int((processed / total_devices) * 100))
            return success

        # 使用线程池替代全量创建线程
        with ThreadPoolExecutor(max_workers=actual_max_workers) as executor:
            futures = []
            for i, device in enumerate(selected_devices):
                if stop_event.is_set():
                    interrupted = True
                    break
                future = executor.submit(process_device, device, i)
                futures.append(future)

            # 等待所有任务完成
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    log_error(f"任务执行异常：{str(e)}")

        if interrupted or stop_event.is_set():
            status_var.set(f"巡检已停止：{success_count}/{total_devices}台设备")
            LOG_QUEUE.put(f"巡检已停止：成功{success_count}台，失败{total_devices-success_count}台")
        else:
            status_var.set(f"巡检完成：共{total_devices}台，成功{success_count}台")
            LOG_QUEUE.put(f"巡检完成：成功{success_count}台，失败{total_devices-success_count}台")

        if hasattr(progress_var, 'set_progress'):
            progress_var.set_progress(100 if not interrupted else progress_var.get(),
                                    f"巡检完成：{success_count}/{total_devices}台设备")
        else:
            progress_var.set(100 if not interrupted else progress_var.get())

    except Exception as e:
        error_msg = f"巡检线程错误：{str(e)}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        status_var.set(f"巡检出错：{str(e)}")


def connect_and_execute(device, device_types, command_files, encodings):
    """连接设备并执行命令"""
    global stop_event

    if stop_event.is_set():
        return False, None

    try:
        device_type_id = device['device_type']
        if device_type_id not in device_types:
            error_msg = f"设备 {device['device_name']} 的类型 {device_type_id} 未定义"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False, None

        device_config = device_types[device_type_id]

        if device_type_id not in command_files or not command_files[device_type_id][1]:
            error_msg = f"设备 {device['device_name']} 没有配置巡检命令"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False, None

        commands = command_files[device_type_id][1]

        protocol = device['protocol'] or device_config['default_protocol']
        if protocol not in ['ssh', 'telnet']:
            protocol = device_config['default_protocol']

        device_driver = device_config['netmiko_type'][protocol]

        device_info = {
            'device_type': device_driver,
            'ip': device['ip'],
            'port': device['port'],
            'timeout': 60,
            'global_delay_factor': 2,
            'read_timeout_override': 120,
        }

        if device['username'].strip():
            device_info['username'] = device['username']
        if device['password'].strip():
            device_info['password'] = device['password']
        if device['secret'].strip():
            device_info['secret'] = device['secret']

        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        LOG_DIR = os.path.join(os.getcwd(), "InspectionLogs", datetime.now().strftime("%Y_%m_%d"))
        os.makedirs(LOG_DIR, exist_ok=True)
        log_file = os.path.join(LOG_DIR, f"{device['device_name']}_{device['ip']}_{timestamp}.txt")

        msg = f"开始处理 {device_config['name']}: {device['device_name']} ({device['ip']})"
        LOG_QUEUE.put(msg)
        log_info(msg)

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"设备名称：{device['device_name']}\n")
            f.write(f"IP 地址：{device['ip']}\n")
            f.write(f"设备类型：{device_config['name']}\n")
            f.write(f"连接协议：{protocol.upper()}\n")
            f.write(f"处理时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"执行命令数：{len(commands)}\n")
            f.write("=" * 50 + "\n\n")

        # 使用带重试机制的连接函数
        net_connect = connect_with_retry(device_info, max_retries=2, retry_delay=2)
        if net_connect is None:
            error_msg = f"无法连接到设备 {device['device_name']} ({device['ip']})"
            LOG_QUEUE.put(error_msg)
            return False, None

        try:
            time.sleep(2)

            if device_config['enable_mode']:
                try:
                    net_connect.enable()
                except Exception as enable_error:
                    debug_log(f"进入特权模式失败：{enable_error}")

            disable_paging_cmd = device_config['disable_paging_cmd']
            if disable_paging_cmd and disable_paging_cmd.strip():
                try:
                    net_connect.send_command(disable_paging_cmd, read_timeout=30)
                except Exception as paging_error:
                    debug_log(f"禁用分页失败：{paging_error}")

            with open(log_file, 'a', encoding='utf-8') as f:
                for command in commands:
                    if stop_event.is_set():
                        f.write("巡检被用户终止\n")
                        return False, log_file

                    f.write(f"执行命令：{command}\n")
                    f.write("-" * 50 + "\n")

                    try:
                        output = net_connect.send_command(command, read_timeout=60)

                        # 编码处理
                        if isinstance(output, bytes):
                            for encoding in encodings:
                                try:
                                    output = output.decode(encoding)
                                    break
                                except:
                                    continue

                        f.write(output + "\n\n")
                    except Exception as cmd_error:
                        f.write(f"命令执行失败：{cmd_error}\n\n")

        finally:
            # 确保连接被关闭
            try:
                net_connect.disconnect()
            except:
                pass  # 忽略断开连接时的错误

        msg = f"{device_config['name']} {device['device_name']} 处理完成"
        LOG_QUEUE.put(msg)
        log_info(msg)
        return True, log_file

    except (NetMikoAuthenticationException, NetMikoTimeoutException) as e:
        error_msg = f"设备 {device['device_name']} 连接异常：{str(e)}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        return False, None
    except Exception as e:
        error_msg = f"设备 {device['device_name']} 处理失败：{str(e)}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        return False, None


def connect_with_retry(device_info, max_retries=3, retry_delay=1):
    """
    带重试机制的设备连接函数
    :param device_info: 设备连接信息
    :param max_retries: 最大重试次数
    :param retry_delay: 重试间隔（秒）
    :return: 连接对象或None
    """
    if not NETMIKO_AVAILABLE:
        LOG_QUEUE.put("netmiko 库未安装，无法建立设备连接")
        return None

    for attempt in range(max_retries + 1):
        try:
            connection = ConnectHandler(**device_info)
            return connection
        except NetMikoTimeoutException:
            if attempt < max_retries:
                LOG_QUEUE.put(f"连接超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                time.sleep(retry_delay)
            else:
                LOG_QUEUE.put(f"连接设备失败，已达最大重试次数")
        except NetMikoAuthenticationException:
            LOG_QUEUE.put(f"认证失败，请检查用户名和密码")
            break  # 认证失败通常不需要重试
        except Exception as e:
            if attempt < max_retries:
                LOG_QUEUE.put(f"连接异常，{retry_delay}秒后重试: {str(e)}")
                time.sleep(retry_delay)
            else:
                LOG_QUEUE.put(f"连接设备失败: {str(e)}")
    return None

def validate_config_file(file_path, required_columns):
    """
    验证配置文件格式
    :param file_path: 配置文件路径
    :param required_columns: 必需的列名列表
    :return: (是否有效, 错误信息列表)
    """
    errors = []
    try:
        encoding = detect_file_encoding(file_path, ['utf-8', 'gbk', 'gb2312'])
        with open(file_path, 'r', encoding=encoding) as f:
            first_line = f.readline().strip()
            columns = [col.strip() for col in first_line.split(',')]

        for col in required_columns:
            if col not in columns:
                errors.append(f"缺少必需列: {col}")

        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"文件读取错误: {str(e)}"]

# ==================== 配置加载辅助函数 ====================

def is_comment_line(line_parts):
    """判断是否为注释行"""
    if not line_parts:
        return False
    for part in line_parts:
        stripped = part.strip()
        if stripped:
            return stripped.startswith('#')
    return False


def load_device_types_config(file_path, encodings):
    """加载设备类型配置"""
    log_info(f"开始加载设备类型配置：{file_path}")
    if not file_path or not os.path.exists(file_path):
        error_msg = f"设备类型配置文件不存在：{file_path}"
        LOG_QUEUE.put(error_msg)
        debug_log(error_msg)
        return {}

    device_types = {}
    file_ext = os.path.splitext(file_path)[1].lower()
    debug_log(f"加载设备类型配置文件：{file_path}, 扩展名：{file_ext}")

    # 使用编码缓存
    encoding = detect_file_encoding(file_path, encodings)
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            if file_ext == '.csv':
                reader = csv.reader(f)
                for row_num, parts in enumerate(reader, 1):
                    if not parts or is_comment_line(parts):
                        continue
                    if len(parts) >= 7:
                        device_id, name, ssh_driver, telnet_driver, enable_mode, paging_cmd, default_proto = [p.strip() for p in parts[:7]]
                        cmd_file = parts[7].strip() if len(parts) > 7 and parts[7].strip() else ""

                        device_types[device_id] = {
                            'name': name,
                            'netmiko_type': {'ssh': ssh_driver, 'telnet': telnet_driver},
                            'enable_mode': bool(int(enable_mode)),
                            'disable_paging_cmd': paging_cmd,
                            'default_protocol': default_proto,
                            'commands_file': cmd_file
                        }
                    else:
                        msg = f"设备类型配置第{row_num}行格式错误"
                        LOG_QUEUE.put(msg)
                        debug_log(msg)
            else:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        continue
                    parts = [p.strip() for p in stripped_line.split('|')]
                    if len(parts) >= 7:
                        device_id, name, ssh_driver, telnet_driver, enable_mode, paging_cmd, default_proto = parts[:7]
                        cmd_file = parts[7] if len(parts) > 7 and parts[7] else ""

                        device_types[device_id] = {
                            'name': name,
                            'netmiko_type': {'ssh': ssh_driver, 'telnet': telnet_driver},
                            'enable_mode': bool(int(enable_mode)),
                            'disable_paging_cmd': paging_cmd,
                            'default_protocol': default_proto,
                            'commands_file': cmd_file
                        }
                    else:
                        msg = f"设备类型配置第{line_num}行格式错误"
                        LOG_QUEUE.put(msg)
                        debug_log(msg)

            msg = f"成功加载设备类型配置：{file_path}，共{len(device_types)}种设备类型"
            LOG_QUEUE.put(msg)
            debug_log(msg)
            return device_types

    except Exception as e:
        msg = f"加载设备类型配置失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return {}


def load_devices(file_path, encodings):
    """加载设备列表"""
    log_info(f"开始加载设备列表：{file_path}")
    if not file_path or not os.path.exists(file_path):
        error_msg = f"设备列表文件不存在：{file_path}"
        LOG_QUEUE.put(error_msg)
        debug_log(error_msg)
        return []

    devices = []
    file_ext = os.path.splitext(file_path)[1].lower()

    # 使用编码缓存
    encoding = detect_file_encoding(file_path, encodings)
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            if file_ext == '.csv':
                reader = csv.reader(f)
                for row_num, parts in enumerate(reader, 1):
                    if not parts or is_comment_line(parts):
                        continue
                    if len(parts) >= 3 and all(parts[i].strip() for i in range(3)):
                        device = {
                            'device_name': parts[0].strip(),
                            'ip': parts[1].strip(),
                            'device_type': parts[2].strip(),
                            'username': parts[3].strip() if len(parts) > 3 else '',
                            'password': parts[4].strip() if len(parts) > 4 else '',
                            'secret': parts[5].strip() if len(parts) > 5 else '',
                            'port': int(parts[6].strip()) if len(parts) > 6 and parts[6].strip() else 22,
                            'protocol': parts[7].strip().lower() if len(parts) > 7 and parts[7].strip() else None,
                            'encoding': parts[8].strip() if len(parts) > 8 and parts[8].strip() else None,
                            'selected': True
                        }
                        devices.append(device)
            else:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        continue
                    parts = [p.strip() for p in stripped_line.split('|')]
                    if len(parts) >= 3 and all(parts[i].strip() for i in range(3)):
                        device = {
                            'device_name': parts[0],
                            'ip': parts[1],
                            'device_type': parts[2],
                            'username': parts[3] if len(parts) > 3 else '',
                            'password': parts[4] if len(parts) > 4 else '',
                            'secret': parts[5] if len(parts) > 5 else '',
                            'port': int(parts[6]) if len(parts) > 6 and parts[6] else 22,
                            'protocol': parts[7].lower() if len(parts) > 7 and parts[7] else None,
                            'encoding': parts[8].strip() if len(parts) > 8 and parts[8].strip() else None,
                            'selected': True
                        }
                        devices.append(device)

        msg = f"成功加载设备列表：{file_path}，共{len(devices)}台设备"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return devices

    except Exception as e:
        msg = f"加载设备列表失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return []


def parse_commands_file(file_path, encodings):
    """解析命令文件"""
    commands = []
    if not file_path or not os.path.exists(file_path):
        msg = f"命令文件不存在：{file_path}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands

    # 使用编码缓存
    encoding = detect_file_encoding(file_path, encodings)
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            for line in f:
                stripped_line = line.strip()
                if stripped_line and not stripped_line.startswith('#'):
                    commands.append(stripped_line)
        msg = f"成功加载命令文件：{file_path}，共{len(commands)}条命令"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands
    except Exception as e:
        msg = f"解析命令文件失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands


def validate_device_types_config(device_types):
    """验证设备类型配置"""
    if not device_types:
        LOG_QUEUE.put("设备类型配置错误：未加载任何设备类型配置")
        debug_log("设备类型配置错误：未加载任何设备类型配置")
        return False

    for device_id, config in device_types.items():
        required_fields = ['name', 'netmiko_type', 'enable_mode', 'disable_paging_cmd', 'default_protocol']
        for field in required_fields:
            if field not in config:
                error_msg = f"设备类型配置错误：设备类型 {device_id} 缺少必要字段：{field}"
                LOG_QUEUE.put(error_msg)
                debug_log(error_msg)
                return False

        if 'default_protocol' in config and config['default_protocol'] not in ['ssh', 'telnet']:
            error_msg = f"设备类型配置错误：设备类型 {device_id} 的默认协议无效：{config['default_protocol']}"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False

    return True


def validate_devices_config(devices, device_types):
    """验证设备列表配置（向后兼容）"""
    result = validate_devices_config_with_details(devices, device_types)
    return result['valid']

def validate_devices_config_with_details(devices, device_types):
    """验证设备列表配置并返回详细结果"""
    errors = []
    if not devices:
        errors.append("未加载任何设备列表")
        return {
            'valid': False,
            'error_count': len(errors),
            'errors': errors
        }

    if not device_types:
        errors.append("未加载设备类型配置，无法验证设备列表")
        return {
            'valid': False,
            'error_count': len(errors),
            'errors': errors
        }

    for device in devices:
        # 验证设备名称
        if not device.get('device_name', '').strip():
            errors.append(f"设备缺少名称")
            continue

        # 验证IP地址格式
        ip = device.get('ip', '').strip()
        if not ip:
            errors.append(f"设备 {device['device_name']} 的IP地址为空")
        elif not validate_ip(ip):
            errors.append(f"设备 {device['device_name']} 的IP地址格式错误：{ip}")

        # 验证设备类型
        device_type = device.get('device_type', '').strip()
        if not device_type:
            errors.append(f"设备 {device['device_name']} 的类型为空")
        elif device_type not in device_types:
            errors.append(f"设备 {device['device_name']} 的类型 {device_type} 不存在")

        # 验证协议
        protocol = device.get('protocol', '').strip()
        if protocol and protocol not in ['ssh', 'telnet']:
            errors.append(f"设备 {device['device_name']} 的协议 {protocol} 无效")

        # 验证端口
        try:
            port = int(device.get('port', 22))
            if not (1 <= port <= 65535):
                errors.append(f"设备 {device['device_name']} 的端口 {port} 超出有效范围 (1-65535)")
        except ValueError:
            errors.append(f"设备 {device['device_name']} 的端口 {device.get('port', 22)} 不是有效数字")

    return {
        'valid': len(errors) == 0,
        'error_count': len(errors),
        'errors': errors
    }


def validate_commands_config(device_types, command_files):
    """验证命令配置"""
    errors = []
    if not device_types:
        return True

    for device_id, config in device_types.items():
        if device_id not in command_files or not command_files[device_id][1]:
            errors.append(f"设备类型 {device_id} ({config['name']}) 未配置有效巡检命令")

    if errors:
        for error in errors:
            LOG_QUEUE.put(f"命令配置错误：{error}")
            debug_log(f"命令配置错误：{error}")
        return False
    return True


# ==================== 主程序入口 ====================

def main():
    """主程序入口"""
    global logger
    logger = setup_logging()

    log_info("程序开始启动")
    log_info(f"Python 版本：{sys.version}")
    log_info(f"运行路径：{os.getcwd()}")
    debug_log("日志系统初始化完成")

    try:
        # 启动主程序
        root = Tk()
        app = ModernNetworkInspectionUI(root)
        root.mainloop()

    except Exception as e:
        error_log_path = os.path.join(os.getcwd(), "InspectionLogs", "logs", "inspection_error.log")
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"程序启动失败：{str(e)}\n")
            f.write(traceback.format_exc())

        try:
            error_root = tk.Tk()
            error_root.withdraw()
            messagebox.showerror("启动失败", f"程序启动失败，错误信息已写入 {error_log_path}")
            error_root.destroy()
        except:
            pass

        log_error(f"程序启动失败：{str(e)}")
        debug_log(traceback.format_exc(), "ERROR")


if __name__ == "__main__":
    main()
