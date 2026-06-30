"""主题 / 配色 / 字体常量 —— Metro (Microsoft Design Language) 风格。

设计原则：
- 纯平（flat）：无渐变、无阴影、零圆角
- 强对比：纯白底 + 纯黑字 + Microsoft Blue 强调
- 1px 描边：分割靠边线，不靠阴影

高对比度模式备选色与默认色一一对应。其它模块只通过 ``theme_manager`` 取色，
不在自己的常量里硬编码。
"""

# ==================== Metro 风格配色 ====================
# 分层策略（Metro "Light" 反转）：
#   主背景 = 浅灰 (#F4F4F4) ── 等同 Win8 Start screen 背景
#   卡片/瓦片 = 纯白 (#FFFFFF) ── 浮在浅灰上，无需阴影就有层次
#   灰阶表头 = 同背景 ── 用 1px 边框与卡片分割
COLOR_BG_PRIMARY = "#F4F4F4"        # 应用主背景（浅灰）
COLOR_BG_SECONDARY = "#F4F4F4"      # 表头 / 分隔条（与主背景同色，靠边框分层）
COLOR_BG_CARD = "#FFFFFF"           # 卡片 / 瓦片（纯白，浮在浅灰上）
COLOR_BG_DARK = "#E1E1E1"           # progressbar trough / scrollbar trough（深一档）

# 文字：纯黑为主，灰阶层级
COLOR_FG_PRIMARY = "#000000"
COLOR_FG_SECONDARY = "#5D5D5D"
COLOR_FG_LIGHT = "#3F3F3F"
COLOR_FG_MUTED = "#8A8A8A"

# Microsoft Blue —— Metro 经典强调色
COLOR_ACCENT = "#0078D4"
COLOR_ACCENT_LIGHT = "#106EBE"      # hover
COLOR_ACCENT_DARK = "#005A9E"       # pressed / 边框焦点
COLOR_ACCENT_GRADIENT_START = "#0078D4"  # 保留 token，Metro 不用渐变
COLOR_ACCENT_GRADIENT_END = "#0078D4"

# 语义色（Metro 调色板）
COLOR_SUCCESS = "#107C10"
COLOR_WARNING = "#FF8C00"
COLOR_ERROR = "#E81123"
COLOR_INFO = "#0078D4"

# 边框：1px 极浅灰
COLOR_BORDER = "#E1E1E1"
COLOR_BORDER_DARK = "#B3B3B3"
COLOR_DIVIDER = "#E1E1E1"

# 日志行文字着色
LOG_COLORS = {
    'DEBUG': '#5D5D5D',
    'INFO': '#0078D4',
    'WARNING': '#FF8C00',
    'ERROR': '#E81123',
    'SUCCESS': '#107C10',
    'CRITICAL': '#E81123',
}

# 日志级别徽章（bg, fg）—— Metro 块状色片
LOG_TAG_COLORS = {
    'DEBUG':    ('#F4F4F4', '#5D5D5D'),  # 灰底
    'INFO':     ('#0078D4', '#FFFFFF'),  # 蓝底白字
    'WARNING':  ('#FF8C00', '#FFFFFF'),  # 橙底白字
    'ERROR':    ('#E81123', '#FFFFFF'),  # 红底白字
    'SUCCESS':  ('#107C10', '#FFFFFF'),  # 绿底白字
    'CRITICAL': ('#E81123', '#FFFFFF'),  # 同 ERROR
}

# 高对比度模式（Metro HC 风格 —— 纯黑白 + 微软蓝）
HIGH_CONTRAST_BG_PRIMARY = "#FFFFFF"
HIGH_CONTRAST_BG_SECONDARY = "#FFFFFF"
HIGH_CONTRAST_BG_CARD = "#FFFFFF"
HIGH_CONTRAST_BG_DARK = "#FFFFFF"
HIGH_CONTRAST_FG_PRIMARY = "#000000"
HIGH_CONTRAST_FG_SECONDARY = "#000000"
HIGH_CONTRAST_FG_LIGHT = "#000000"
HIGH_CONTRAST_FG_MUTED = "#000000"
HIGH_CONTRAST_ACCENT = "#0078D4"
HIGH_CONTRAST_SUCCESS = "#107C10"
HIGH_CONTRAST_WARNING = "#FF8C00"
HIGH_CONTRAST_ERROR = "#E81123"
HIGH_CONTRAST_INFO = "#0078D4"
HIGH_CONTRAST_BORDER = "#000000"

# ==================== 字体 ====================
FONT_FAMILY_UI = "Microsoft YaHei UI"
FONT_FAMILY_CODE = "Consolas"
FONT_FAMILY_ICON = "Segoe MDL2 Assets"

# ==================== 尺寸 ====================
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
WINDOW_MIN_WIDTH = 1100
WINDOW_MIN_HEIGHT = 700

PADDING_X = 16
PADDING_Y = 12
CARD_PADDING = 16
COMPONENT_GAP = 12

# Metro 标志：零圆角（与 #0078D4 配套的"扁平"美学）
CORNER_RADIUS = 0
# Metro 标志：无阴影
SHADOW_COLOR = None

# 连通性测试单设备默认超时（秒）
CONNECTIVITY_TIMEOUT_SECONDS = 5


class ThemeManager:
    """主题管理器：统一管理应用主题。"""

    def __init__(self):
        self.high_contrast_mode = False

    def get_color(self, color_name):
        """根据当前主题返回对应颜色"""
        if self.high_contrast_mode:
            return globals().get(f'HIGH_CONTRAST_{color_name}', globals().get(f'COLOR_{color_name}'))
        return globals()[f'COLOR_{color_name}']

    def toggle_high_contrast(self):
        self.high_contrast_mode = not self.high_contrast_mode
        return self.high_contrast_mode


# 全局主题管理器实例
theme_manager = ThemeManager()