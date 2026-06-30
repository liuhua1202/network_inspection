"""自定义 Tk / ttk 控件。

- ``ModernButton``：自绘按钮（hover / focus / 变体）
- ``ModernEntry``：带 placeholder 的输入框
- ``ModernProgressbar``：ttk 风格化的进度条
- ``DetailedProgressbar``：带详细文本的进度条（实现 ``set_progress(value, text)`` 协议）
- ``LogTag``：日志级别小标签
"""
import tkinter as tk
from tkinter import Label, Frame, StringVar, IntVar
from tkinter import ttk

from ui.theme import (
    theme_manager,
    FONT_FAMILY_UI,
    FONT_FAMILY_CODE,
    LOG_COLORS,
    LOG_TAG_COLORS,
)


class ModernButton(tk.Button):
    """现代化按钮 —— 自绘（hover / focus / 变体）"""

    def __init__(self, parent, text, command=None, variant='primary',
                 width=120, height=40, aria_label=None, **kwargs):
        self.variant = variant
        self.is_disabled = False
        self.aria_label = aria_label or text
        self.original_command = command
        self.default_bg = None
        self.default_fg = None

        char_width = max(width // 10, 8)
        row_height = max(height // 20, 1)

        super().__init__(parent, text=text, width=char_width, height=row_height, **kwargs)
        self._apply_style()

        # 注：v2.1 之前的"自注册到 root._modern_buttons"在部分 tkinter 版本
        # 下会拿到底层 _tkinter.tkapp 而非 Python Tk 实例，导致注册静默失败、
        # 主题切换时按钮永远不刷新。现已改由 _reapply_theme_recursive 递归遍历
        # 整棵 widget 树处理 ModernButton，__init__ 里不再做无效注册。

        self.bind('<Button-1>', self._on_button_click)
        self.bind('<space>', self._on_space_press)
        self.bind('<Return>', self._on_space_press)
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.config(takefocus=True)

    def _apply_style(self):
        try:
            accent_color = theme_manager.get_color('ACCENT')
            accent_light = theme_manager.get_color('ACCENT_LIGHT')
            accent_dark = theme_manager.get_color('ACCENT_DARK')
            error_color = theme_manager.get_color('ERROR')
            fg_primary = theme_manager.get_color('FG_PRIMARY')
            bg_card = theme_manager.get_color('BG_CARD')
            bg_secondary = theme_manager.get_color('BG_SECONDARY')
            border_color = theme_manager.get_color('BORDER')
        except Exception:
            # Metro 风格 fallback：微软蓝 + 纯黑
            accent_color = "#0078D4"
            accent_light = "#106EBE"
            accent_dark = "#005A9E"
            error_color = "#E81123"
            fg_primary = "#000000"
            bg_card = "#FFFFFF"
            bg_secondary = "#F4F4F4"
            border_color = "#E1E1E1"

        if self.variant == 'primary':
            # 实底色按钮（Metro 主操作）
            bg_color = accent_color
            fg_color = '#ffffff'
            active_bg = accent_dark
            border_thickness = 0
            hl_thickness = 0
        elif self.variant == 'danger':
            bg_color = error_color
            fg_color = '#ffffff'
            active_bg = '#A50E1E'
            border_thickness = 0
            hl_thickness = 0
        elif self.variant == 'secondary':
            # Metro secondary：白底 + 1px 边框（与浅灰背景区分开）
            bg_color = bg_card
            fg_color = accent_color
            active_bg = bg_secondary
            border_thickness = 1
            hl_thickness = 1
        else:
            # 默认 / default 变体：灰底
            bg_color = '#E1E1E1'
            fg_color = fg_primary
            active_bg = '#D0D0D0'
            border_thickness = 0
            hl_thickness = 0

        self.default_bg = bg_color
        self.default_fg = fg_color

        self.config(
            bg=bg_color,
            fg=fg_color,
            activebackground=active_bg,
            activeforeground=fg_color if self.variant == 'secondary' else '#ffffff',
            relief='solid' if border_thickness else 'flat',
            bd=border_thickness,
            highlightthickness=hl_thickness,
            highlightbackground=border_color,
            highlightcolor=accent_color,
            padx=10,
            pady=6,
            font=(FONT_FAMILY_UI, 10, 'bold' if self.variant in ('primary', 'danger') else 'normal'),
            cursor='hand2'
        )

    def _animate_hover_in(self):
        if not self.is_disabled:
            try:
                accent_light = theme_manager.get_color('ACCENT_LIGHT')
                bg_secondary = theme_manager.get_color('BG_SECONDARY')
                if self.variant == 'secondary':
                    # Metro：secondary 按钮 hover 用浅灰底
                    hover_bg = bg_secondary
                else:
                    hover_bg = accent_light  # primary/danger hover = 加深一档
                self.config(bg=hover_bg)
            except Exception:
                if self.variant == 'secondary':
                    self.config(bg='#F4F4F4')
                else:
                    self.config(bg='#106EBE')

    def _animate_hover_out(self):
        if not self.is_disabled:
            self.config(bg=self.default_bg)

    def _on_button_click(self, event=None):
        if not self.is_disabled and self.original_command:
            try:
                self.original_command()
            except Exception as e:
                try:
                    from utils.logging_setup import log_error
                    log_error(f"按钮命令执行错误：{e}")
                except Exception:
                    print(f"按钮命令执行错误：{e}")

    def _on_space_press(self, event=None):
        if not self.is_disabled and self.original_command:
            try:
                self.original_command()
            except Exception as e:
                try:
                    from utils.logging_setup import log_error
                    log_error(f"按钮命令执行错误：{e}")
                except Exception:
                    print(f"按钮命令执行错误：{e}")

    def _on_enter(self, event=None):
        if not self.is_disabled:
            self._animate_hover_in()

    def _on_leave(self, event=None):
        if not self.is_disabled:
            self._animate_hover_out()

    def _on_focus_in(self, event=None):
        if not self.is_disabled:
            # Metro 焦点环：2px accent 色 highlight（外圈）
            self.config(highlightthickness=2)

    def _on_focus_out(self, event=None):
        if not self.is_disabled:
            # 还原：secondary 保持 1px 边框，其它 0
            hl = 1 if self.variant == 'secondary' else 0
            self.config(highlightthickness=hl)

    def disable(self):
        self.is_disabled = True
        # Metro disabled：浅灰底 + 灰字，保留边框避免与背景同化
        hl = 1 if self.variant == 'secondary' else 0
        self.config(
            state='disabled',
            bg='#F4F4F4',
            fg='#A6A6A6',
            highlightthickness=hl,
            highlightbackground='#E1E1E1',
        )

    def enable(self):
        self.is_disabled = False
        self.config(state='normal')
        self._apply_style()

    def set_variant(self, variant):
        self.variant = variant
        self._apply_style()


class ModernEntry(tk.Entry):
    """现代化输入框 —— 带 placeholder 文字"""

    def __init__(self, parent, placeholder='', **kwargs):
        if 'font' not in kwargs:
            kwargs['font'] = (FONT_FAMILY_UI, 11)
        if 'fg' not in kwargs:
            kwargs['fg'] = theme_manager.get_color('FG_PRIMARY')
        if 'bg' not in kwargs:
            kwargs['bg'] = theme_manager.get_color('BG_CARD')
        if 'relief' not in kwargs:
            kwargs['relief'] = 'flat'
        if 'highlightthickness' not in kwargs:
            kwargs['highlightthickness'] = 2
        if 'highlightbackground' not in kwargs:
            kwargs['highlightbackground'] = theme_manager.get_color('BORDER')
        if 'highlightcolor' not in kwargs:
            kwargs['highlightcolor'] = theme_manager.get_color('ACCENT')
        if 'insertbackground' not in kwargs:
            kwargs['insertbackground'] = theme_manager.get_color('FG_PRIMARY')
        if 'selectbackground' not in kwargs:
            kwargs['selectbackground'] = theme_manager.get_color('ACCENT')
        if 'selectforeground' not in kwargs:
            kwargs['selectforeground'] = '#ffffff'

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


class ModernProgressbar(tk.Canvas):
    """Metro 风格扁平进度条 —— Canvas 自绘，固定高度（默认 8px）。

    继承 tk.Canvas 但对外暴露和 ttk.Progressbar 一样的接口：
    - configure(variable=IntVar) 通过 IntVar 跟踪进度
    - ``cget('value')`` / ``itemconfigure(value=...)`` 用于读 / 写
    简化实现：监听 ``variable``（IntVar 0-100）变化时重绘。
    """

    def __init__(self, parent, variable=None, maximum=100, bar_height=8,
                 trough_color=None, fill_color=None, **kwargs):
        super().__init__(parent, height=bar_height,
                         highlightthickness=0, bd=0, bg=parent.cget('bg') if parent.cget('bg') else theme_manager.get_color('BG_CARD'),
                         **kwargs)
        self._bar_height = bar_height
        self._trough_color = trough_color or theme_manager.get_color('BG_DARK')
        self._fill_color = fill_color or theme_manager.get_color('ACCENT')
        self._variable = variable
        self._maximum = maximum
        # 整条 trough 矩形
        self._trough_rect = self.create_rectangle(
            0, 0, 0, bar_height,
            fill=self._trough_color, outline=self._trough_color, width=0,
        )
        # 进度填充矩形（初始 0 宽）
        self._fill_rect = self.create_rectangle(
            0, 0, 0, bar_height,
            fill=self._fill_color, outline=self._fill_color, width=0,
        )
        self.bind('<Configure>', self._on_resize)
        if self._variable is not None:
            # 监听 IntVar 变化
            self._variable.trace_add('write', self._on_var_changed)
            self._on_var_changed()

    def _on_resize(self, event=None):
        """窗口大小变化 / 初次显示时，重画 trough 全宽和当前进度填充"""
        w = self.winfo_width()
        h = self._bar_height
        self.coords(self._trough_rect, 0, 0, w, h)
        self.itemconfigure(self._trough_rect, fill=self._trough_color, outline=self._trough_color)
        self._redraw_fill()

    def _on_var_changed(self, *args):
        """IntVar 变化回调"""
        self._redraw_fill()

    def _redraw_fill(self):
        try:
            val = self._variable.get() if self._variable is not None else 0
        except (tk.TclError, AttributeError):
            val = 0
        ratio = max(0.0, min(1.0, val / float(self._maximum or 1)))
        w = self.winfo_width()
        fill_w = int(w * ratio)
        self.coords(self._fill_rect, 0, 0, fill_w, self._bar_height)
        self.itemconfigure(self._fill_rect, fill=self._fill_color, outline=self._fill_color)


class DetailedProgressbar(Frame):
    """带详细文本的进度条 —— 满足 ``ProgressReporter`` 协议。

    提供 ``set_progress(value, text)`` 与 ``get_progress()``，worker 通过这两个
    方法与 UI 通信，不再用 ``hasattr`` 鸭子类型。

    ``show_label=False`` 时只显示进度条本体（适合状态栏等已有独立文字标签的场景），
    此时 ``set_progress`` 的 ``text`` 参数被忽略。
    """

    def __init__(self, parent, show_label=True, **kwargs):
        bg = parent.cget('bg') if parent.cget('bg') else theme_manager.get_color('BG_PRIMARY')
        super().__init__(parent, bg=bg, **kwargs)
        self._show_label = show_label
        self.progress_var = IntVar(value=0)
        self.progress_bar = ModernProgressbar(self, variable=self.progress_var, maximum=100)
        # 居中：上下 pad 各 6px，让 8px 高的条对齐文字基线
        self.progress_bar.pack(fill='x', expand=True, padx=0, pady=6)
        if show_label:
            self.progress_label = Label(self, text="", font=(FONT_FAMILY_UI, 10),
                                        fg=theme_manager.get_color('FG_SECONDARY'), bg=bg)
            self.progress_label.pack(fill='x', expand=True, pady=(2, 0))

    def set_progress(self, value, text=""):
        """ProgressReporter 协议入口"""
        try:
            self.progress_var.set(int(value))
        except (TypeError, ValueError):
            self.progress_var.set(0)
        if text and self._show_label and hasattr(self, 'progress_label'):
            self.progress_label.config(text=text)

    def get_progress(self):
        return self.progress_var.get()


class LogTag(Frame):
    """日志级别小标签（带颜色的徽章）"""

    def __init__(self, parent, level='INFO', **kwargs):
        super().__init__(parent, **kwargs)
        # Metro：块状色片（实底色 + 白字）
        bg, fg = LOG_TAG_COLORS.get(level, LOG_TAG_COLORS['INFO'])
        self.label = Label(self, text=level, font=(FONT_FAMILY_UI, 9, 'bold'),
                           fg=fg, bg=bg, padx=8, pady=2)
        self.label.pack()
