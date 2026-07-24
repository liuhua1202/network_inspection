"""主题 / 配色 / 字体常量 ── NetworkInspector 设计系统（ui-ux-pro-max）。

基于 ui-ux-pro-max 检索：
- Pattern: Real-Time Operations Dashboard（运维工具）
- Style: Light Professional（浅色专业风，参考 Legal/Trust 调色板）
- WCAG AA：4.5:1 文字对比度，1px 边框 + 微阴影分层

设计语言：
- 权威深蓝（#1E3A8A）主色 ── 运维场景下的"专业/信任"信号
- 金色强调（#B45309）── KPI 卡片中突出关键数值
- Tailwind slate 灰阶 ── 现代 web 风（slate-50/100/200/500/900）
- 12px 圆角卡片 + 8px 按钮 + 微阴影 ── 现代卡片化布局
- 4/8/12/16/24/32px 间距系统 ── 8 倍数
- 状态色：成功 #16A34A / 警告 #D97706 / 错误 #DC2626

其它模块只通过 ``theme_manager`` 取色，不在常量里硬编码。
"""

# ==================== NetworkInspector 设计系统 ====================
# 主背景 = #F8FAFC（slate-50，略带蓝调的浅灰）── 应用最底层
# 卡片 = #FFFFFF + 1px 边框 #E2E8F0 + 微阴影 ── 浮在主背景上
# 灰阶 = slate-50/100/200/300/500/700/900 ── 现代 web 灰阶

# ---- 基础色 ----
COLOR_BG_PRIMARY = "#F8FAFC"        # 应用主背景（slate-50）
COLOR_BG_SECONDARY = "#FFFFFF"      # 卡片 / 工具栏（白）
COLOR_BG_CARD = "#FFFFFF"           # 卡片（白）
COLOR_BG_DARK = "#E2E8F0"           # progressbar trough / scrollbar trough（slate-200）
COLOR_BG_RAISED = "#FFFFFF"         # 凸起卡片（带阴影）

# ---- 文字（slate 灰阶） ----
COLOR_FG_PRIMARY = "#0F172A"        # slate-900 ── 标题与重要文字（11.8:1 对比度，AAA）
COLOR_FG_SECONDARY = "#334155"      # slate-700 ── 正文（9.4:1，AAA）
COLOR_FG_LIGHT = "#64748B"          # slate-500 ── 提示文字（4.8:1，AA）
COLOR_FG_MUTED = "#94A3B8"          # slate-400 ── 占位 / 禁用（3.0:1，仅大字体合规）

# ---- 主色（权威深蓝） ----
COLOR_ACCENT = "#1E3A8A"            # 主色（blue-900，权威深蓝）
COLOR_ACCENT_LIGHT = "#3B82F6"      # hover / 次级（blue-500）
COLOR_ACCENT_DARK = "#1E40AF"       # pressed / active（blue-800）
COLOR_ACCENT_GRADIENT_START = "#1E3A8A"  # 保留 token
COLOR_ACCENT_GRADIENT_END = "#1E3A8A"

# ---- 金色强调（KPI 数值突出） ----
COLOR_GOLD = "#B45309"              # amber-700 ── 强调色（KPI 数值、焦点）
COLOR_GOLD_LIGHT = "#D97706"        # amber-600 ── hover

# ---- 语义色 ----
COLOR_SUCCESS = "#16A34A"           # green-600 ── 成功
COLOR_SUCCESS_LIGHT = "#22C55E"     # green-500 ── hover
COLOR_SUCCESS_BG = "#DCFCE7"        # green-100 ── 成功底色
COLOR_WARNING = "#D97706"           # amber-600 ── 警告
COLOR_WARNING_BG = "#FEF3C7"        # amber-100 ── 警告底色
COLOR_ERROR = "#DC2626"             # red-600 ── 错误
COLOR_ERROR_BG = "#FEE2E2"          # red-100 ── 错误底色
COLOR_INFO = "#1E3A8A"              # 主色蓝 ── 信息

# ---- 边框（slate-200/300） ----
COLOR_BORDER = "#E2E8F0"            # slate-200 ── 卡片边框
COLOR_BORDER_DARK = "#CBD5E1"       # slate-300 ── 加重边框 / input 边框
COLOR_DIVIDER = "#E2E8F0"           # 分隔线

# ---- 阴影（Tailwind box-shadow 调色） ----
COLOR_SHADOW_SM = "#0F172A08"       # slate-900 @ 3% ── 微阴影（卡片）
COLOR_SHADOW_MD = "#0F172A10"       # slate-900 @ 6% ── 中阴影（hover/focus）
COLOR_SHADOW_LG = "#0F172A14"       # slate-900 @ 8% ── 大阴影（弹窗）

# ---- 按钮专用色 ----
COLOR_BUTTON_NEUTRAL = "#F1F5F9"     # slate-100 ── secondary 按钮底色（比卡片白明显深）
COLOR_BUTTON_NEUTRAL_HOVER = "#E2E8F0"  # slate-200 ── secondary 按钮 hover
COLOR_BUTTON_DISABLED = "#F1F5F9"   # slate-100 ── 禁用按钮底色
COLOR_BUTTON_DISABLED_FG = "#94A3B8" # slate-400 ── 禁用按钮文字
COLOR_FOCUS_RING = "#3B82F6"        # blue-500 ── 键盘焦点环

# ---- 日志行文字着色 ----
LOG_COLORS = {
    'DEBUG':    '#64748B',  # slate-500
    'INFO':     '#1E3A8A',  # 主色蓝
    'WARNING':  '#D97706',  # amber-600
    'ERROR':    '#DC2626',  # red-600
    'SUCCESS':  '#16A34A',  # green-600
    'CRITICAL': '#DC2626',  # red-600
}

# ---- 日志级别徽章（bg, fg）── 圆角 4px ----
LOG_TAG_COLORS = {
    'DEBUG':    ('#F1F5F9', '#64748B'),  # slate-100 / slate-500
    'INFO':     ('#1E3A8A', '#FFFFFF'),  # 主色蓝底白字
    'WARNING':  ('#D97706', '#FFFFFF'),  # amber-600 底白字
    'ERROR':    ('#DC2626', '#FFFFFF'),  # red-600 底白字
    'SUCCESS':  ('#16A34A', '#FFFFFF'),  # green-600 底白字
    'CRITICAL': ('#DC2626', '#FFFFFF'),  # 同 ERROR
}

# 高对比度模式（纯黑白 + 主色蓝）── 提升对比度用于视觉辅助
HIGH_CONTRAST_BG_PRIMARY = "#FFFFFF"
HIGH_CONTRAST_BG_SECONDARY = "#FFFFFF"
HIGH_CONTRAST_BG_CARD = "#FFFFFF"
HIGH_CONTRAST_BG_DARK = "#FFFFFF"
HIGH_CONTRAST_FG_PRIMARY = "#000000"
HIGH_CONTRAST_FG_SECONDARY = "#000000"
HIGH_CONTRAST_FG_LIGHT = "#000000"
HIGH_CONTRAST_FG_MUTED = "#000000"
HIGH_CONTRAST_ACCENT = "#1E3A8A"
HIGH_CONTRAST_SUCCESS = "#15803D"
HIGH_CONTRAST_WARNING = "#B45309"
HIGH_CONTRAST_ERROR = "#B91C1C"
HIGH_CONTRAST_INFO = "#1E3A8A"
HIGH_CONTRAST_BORDER = "#000000"
HIGH_CONTRAST_GOLD = "#92400E"

# 按钮专用色（高对比度版）
HIGH_CONTRAST_BUTTON_NEUTRAL = "#FFFFFF"
HIGH_CONTRAST_BUTTON_NEUTRAL_HOVER = "#F1F5F9"
HIGH_CONTRAST_BUTTON_DISABLED = "#F1F5F9"
HIGH_CONTRAST_BUTTON_DISABLED_FG = "#000000"
HIGH_CONTRAST_FOCUS_RING = "#1E3A8A"

# ==================== 字体 ====================
# UI 主字体：Microsoft YaHei（系统覆盖广；中文渲染友好）
FONT_FAMILY_UI = "Microsoft YaHei"
# 等宽字体（用于日志 / 代码）
FONT_FAMILY_CODE = "Consolas"
# 图标字体（Segoe MDL2 Assets / Segoe Fluent Icons）
FONT_FAMILY_ICON = "Segoe MDL2 Assets"

# ---- Typography 层级（基于 13px base） ----
# 标题层级：H1 24 / H2 18 / H3 14 / Body 13 / Caption 11
FONT_SIZE_H1 = 24
FONT_SIZE_H2 = 18
FONT_SIZE_H3 = 14
FONT_SIZE_BODY = 13
FONT_SIZE_CAPTION = 11
FONT_SIZE_KPI_VALUE = 34      # KPI 数值（大字号强调；卡片高度约为原始 1/2）
FONT_SIZE_KPI_LABEL = 11      # KPI 标签（小字号次要）
FONT_LINE_HEIGHT = 1.5

# ==================== 尺寸（基于 8 倍数系统） ====================
WINDOW_WIDTH = 1350
WINDOW_HEIGHT = 860
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 600

# 间距系统：4/8/12/16/24/32px ── 8 倍数（ui-ux-pro-max 推荐）
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 12
SPACING_LG = 16
SPACING_XL = 24
SPACING_2XL = 32

# 页面级 padding
PADDING_X = 24                # 页面水平 padding（更宽更舒展）
PADDING_Y = 20
CARD_PADDING = 20             # 卡片内 padding
COMPONENT_GAP = 16            # 组件间距

# ==================== 圆角与阴影 ====================
# 圆角：12px 卡片 / 8px 按钮 / 4px 输入框 / 999px 状态徽章
CORNER_RADIUS = 12            # 卡片圆角（现代风格，比 sdt 的 6px 更圆润）
BUTTON_CORNER_RADIUS = 8      # 按钮圆角
INPUT_CORNER_RADIUS = 6       # 输入框圆角
BADGE_CORNER_RADIUS = 999     # 状态徽章（完全圆角）

PROGRESSBAR_HEIGHT = 8        # 进度条高度（更明显一点）
TREEVIEW_ROW_HEIGHT = 36      # 设备列表行高（更舒展，与 8 倍数对齐）

# 阴影：Tailwind 风格（slate-900 alpha）
SHADOW_COLOR = COLOR_SHADOW_SM
SHADOW_SM = "0 1px 2px 0 " + COLOR_SHADOW_SM       # 微阴影（卡片默认）
SHADOW_MD = "0 4px 6px -1px " + COLOR_SHADOW_MD    # 中阴影（hover）
SHADOW_LG = "0 10px 15px -3px " + COLOR_SHADOW_LG  # 大阴影（弹窗）

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