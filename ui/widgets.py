"""自定义 Tk / ttk 控件。

- ``ModernButton``：自绘按钮（hover / focus / 变体）
- ``ModernEntry``：带 placeholder 的输入框
- ``ModernProgressbar``：ttk 风格化的进度条（Canvas 自绘，DoubleVar 驱动）
- ``DetailedProgressbar``：带详细文本的进度条（实现 ``set_progress(value, text)`` 协议，
  前进值自动 320ms 缓动）
- ``LogTag``：日志级别小标签
"""
import tkinter as tk
from tkinter import Label, Frame, StringVar, DoubleVar
from tkinter import ttk

try:
    from PIL import Image as _PILImage, ImageDraw as _PILImageDraw, ImageTk as _PILImageTk
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False
    _PILImage = _PILImageDraw = _PILImageTk = None

from ui.theme import (
    theme_manager,
    FONT_FAMILY_UI,
    FONT_FAMILY_CODE,
    BUTTON_CORNER_RADIUS,
    LOG_COLORS,
    LOG_TAG_COLORS,
    COLOR_GOLD,
    FONT_SIZE_KPI_VALUE,
    FONT_SIZE_KPI_LABEL,
    CARD_PADDING,
)


def hex_to_rgb(hx):
    """#RRGGBB -> (r, g, b) tuple (0-255)。"""
    hx = str(hx).lstrip('#')
    return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16))


def hex_to_rgba(hx, alpha=255):
    """#RRGGBB -> (r, g, b, alpha) tuple。"""
    r, g, b = hex_to_rgb(hx)
    return (r, g, b, alpha)


def render_button_pil(width, height, radius, fill, border=None, border_width=1, icon_name=None, text=None, use_bold=False):
    """模块级辅助：用 PIL 渲染带圆角 + icon + text 的按钮。

    用于需要在 Tkinter Canvas 之外直接渲染按钮图的场景（如预览、截图）。
    """
    if not _PIL_AVAILABLE:
        return None
    try:
        from PIL import Image, ImageDraw, ImageTk
        scale = 6
        sw, sh = width * scale, height * scale
        sr = radius * scale
        img = Image.new('RGBA', (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        def hex_to_rgba(hx, alpha=255):
            hx = hx.lstrip('#')
            return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), alpha)

        if border and border != fill and border_width > 0:
            draw.rounded_rectangle((0, 0, sw - 1, sh - 1), radius=sr, fill=hex_to_rgba(border))
            inset = border_width * scale
            draw.rounded_rectangle((inset, inset, sw - 1 - inset, sh - 1 - inset),
                                    radius=max(sr - inset, 1), fill=hex_to_rgba(fill))
        else:
            draw.rounded_rectangle((0, 0, sw - 1, sh - 1), radius=sr, fill=hex_to_rgba(fill))

        if icon_name:
            icon_img = IconLibrary.render(icon_name, color=fill if not border else border, size=16)
            if icon_img:
                icon_big = icon_img.resize((16 * scale, 16 * scale), Image.Resampling.LANCZOS)
                img.paste(icon_big, (12 * scale, (height // 2 - 8) * scale), icon_big)

        if text:
            try:
                from PIL import ImageFont
                # Try to load Microsoft YaHei
                font_paths = [r'C:\Windows\Fonts\msyh.ttc', r'C:\Windows\Fonts\msyh.ttf']
                f = None
                for fp in font_paths:
                    if os.path.exists(fp):
                        try:
                            weight = 'bold' if use_bold else 'regular'
                            f = ImageFont.truetype(fp, 10 * scale, index=1 if weight == 'bold' and fp.endswith('.ttc') else 0)
                            break
                        except Exception:
                            pass
                if f is None:
                    f = ImageFont.load_default()
                # Calculate text width
                bbox = f.getbbox(text)
                text_w = bbox[2] - bbox[0]
                # Layout: [icon] [padding=6] [text] 整体居中
                if icon_name:
                    total_w = 16 * scale + 6 * scale + text_w
                    text_cx = sw / 2 + (16 * scale + 6 * scale) / 2
                else:
                    text_cx = sw / 2
                draw.text((text_cx, sh / 2), text, fill=hex_to_rgba(fill if not border else border), font=f, anchor='mm')
            except Exception:
                pass

        return img.resize((width, height), Image.Resampling.LANCZOS)
    except Exception:
        return None



class ModernButton(tk.Canvas):
    """现代化按钮 ── Canvas 自绘（圆角 + icon + hover/focus/disabled）。"""
    _registry = []  # 主题切换时批量重绘

    def __init__(self, parent, text, command=None, variant='primary',
                 width=120, height=40, aria_label=None, icon=None,
                 icon_size=16, icon_color=None, icon_tile=None, icon_tile_pad=4, **kwargs):
        try:
            parent_bg = parent.cget('bg')
        except Exception:
            parent_bg = theme_manager.get_color('BG_PRIMARY')
        if not parent_bg or parent_bg == 'SystemButtonFace':
            parent_bg = theme_manager.get_color('BG_PRIMARY')

        self._outer_pad = 3
        self._btn_w = width
        self._btn_h = height
        sw, sh = width + 2 * self._outer_pad, height + 2 * self._outer_pad

        super().__init__(parent, width=sw, height=sh, highlightthickness=0, bd=0,
                         bg=parent_bg, cursor='hand2', **kwargs)

        # 状态
        self._text = text
        self._command = command
        self._variant = variant
        self._is_hover = False
        self._is_focused = False
        self._is_pressed = False
        self._is_disabled = False
        self._aria_label = aria_label or text
        self._icon = icon
        self._icon_size = icon_size
        self._icon_color = icon_color
        self._icon_tile = icon_tile
        self._icon_tile_pad = icon_tile_pad
        self._icon_padding = 6
        self.original_command = command
        self.default_bg = None
        self.default_fg = None

        # 绘制资源 id
        self._bg_image_id = None
        self._icon_id = None
        self._text_id = None
        self._focus_rect = None
        self._icon_photo = None        # 按钮背景图（历史命名，勿删）
        self._btn_icon_photo = None    # 图标 PhotoImage：必须持久引用，否则会被 GC

        ModernButton._registry.append(self)
        self._apply_style()

        # 事件
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)
        self.bind('<ButtonPress-1>', self._on_press)
        self.bind('<ButtonRelease-1>', self._on_release)
        self.bind('<FocusIn>', self._on_focus_in)
        self.bind('<FocusOut>', self._on_focus_out)
        self.bind('<space>', self._on_key_press)
        self.bind('<Return>', self._on_key_press)
        self.config(takefocus=True)

    @property
    def variant(self):
        return self._variant

    @property
    def is_disabled(self):
        return self._is_disabled

    def _variant_palette(self):
        """(bg, fg, hover_bg, pressed_bg, border, border_width, use_bold)"""
        try:
            accent = theme_manager.get_color('ACCENT')
            accent_dark = theme_manager.get_color('ACCENT_DARK')
            error = theme_manager.get_color('ERROR')
            fg_primary = theme_manager.get_color('FG_PRIMARY')
            card_bg = theme_manager.get_color('BG_CARD')
            btn_neutral = theme_manager.get_color('BUTTON_NEUTRAL')
            btn_neutral_hover = theme_manager.get_color('BUTTON_NEUTRAL_HOVER')
            border_color = theme_manager.get_color('BORDER')
        except Exception:
            accent = '#1E3A8A'
            accent_dark = '#0b5ba8'
            error = '#DC2626'
            fg_primary = '#0F172A'
            card_bg = '#FFFFFF'
            btn_neutral = '#F1F5F9'
            btn_neutral_hover = '#E2E8F0'
            border_color = '#E2E8F0'

        if self._variant == 'primary':
            return (accent, '#ffffff', accent, accent_dark, accent, 0, True)
        elif self._variant == 'danger':
            return (error, '#ffffff', error, '#991b1b', error, 0, True)
        elif self._variant == 'secondary':
            return (btn_neutral, accent, btn_neutral_hover, btn_neutral_hover, border_color, 1, False)
        elif self._variant == 'ghost':
            return (card_bg, fg_primary, btn_neutral, btn_neutral_hover, card_bg, 0, False)
        else:
            return (btn_neutral, fg_primary, btn_neutral_hover, btn_neutral_hover, border_color, 1, False)

    def _disabled_palette(self):
        try:
            bg = theme_manager.get_color('BUTTON_DISABLED')
            fg = theme_manager.get_color('BUTTON_DISABLED_FG')
            border = theme_manager.get_color('BORDER')
        except Exception:
            bg = '#F1F5F9'
            fg = '#94A3B8'
            border = '#E2E8F0'
        return bg, fg, border

    def _apply_style(self):
        if self._is_disabled:
            bg, fg, border = self._disabled_palette()
            border_width = 1
            use_bold = False
        else:
            bg, fg, hover_bg, pressed_bg, border, border_width, use_bold = self._variant_palette()
            if self._is_pressed:
                bg = pressed_bg
            elif self._is_hover:
                bg = hover_bg
        self.default_bg = bg
        self.default_fg = fg
        self._redraw(bg=bg, fg=fg, border=border, border_width=border_width, use_bold=use_bold)

    def _render_button_bg(self, width, height, radius, fill_hex, border_hex=None, border_width=1):
        """用 PIL 渲染像素级平滑的圆角矩形按钮背景（增强抗锯齿）。

        抗锯齿关键技术：
        - 8× 超采样 ── 圆角边缘亚像素级平滑
        - 1px padding 防止 LANCZOS 重采样时边缘裁切
        - LANCZOS 高质量重采样 ── 业界标准下采样滤波器
        失败时返回 None（调用方回退到 Canvas polygon）。
        """
        if not _PIL_AVAILABLE:
            return None
        try:
            scale = 8
            pad = 1
            w = (width + 2 * pad) * scale
            h = (height + 2 * pad) * scale
            r = radius * scale
            img = _PILImage.new('RGBA', (w, h), (0, 0, 0, 0))
            draw = _PILImageDraw.Draw(img)
            if border_hex and border_hex != fill_hex and border_width > 0:
                draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=hex_to_rgb(border_hex))
                inset = border_width * scale
                draw.rounded_rectangle((inset, inset, w - 1 - inset, h - 1 - inset),
                                       radius=max(r - inset, 1), fill=hex_to_rgb(fill_hex))
            else:
                draw.rounded_rectangle((0, 0, w - 1, h - 1), radius=r, fill=hex_to_rgb(fill_hex))
            # LANCZOS 重采样 + 裁剪回原尺寸（保留 AA 边缘）
            result = img.resize((width + 2 * pad, height + 2 * pad), _PILImage.LANCZOS)
            return result.crop((pad, pad, pad + width, pad + height))
        except Exception:
            return None

    def _measure_text_width(self, text, use_bold=False):
        """用 Tk font metrics 准确测量文字像素宽度。"""
        try:
            import tkinter.font as _tkfont
            f = _tkfont.Font(family=FONT_FAMILY_UI, size=10, weight='bold' if use_bold else 'normal')
            return f.measure(text)
        except Exception:
            # 降级估算
            cjk = sum(1 for c in text if '一' <= c <= '鿿')
            other = len(text) - cjk
            return cjk * 13 + other * 6

    def _build_icon_image(self, name, color, size, tile):
        """生成按钮图标 PhotoImage。

        tile=(hex, alpha) 时渲染 **Duotone 双色块**：浅色圆角底 + 居中矢量图标，
        与 StatCard 的 KPI 图标 tile 视觉统一；否则返回普通单色矢量图标。
        """
        if not _PIL_AVAILABLE or not name:
            return None
        if not tile:
            return IconLibrary.to_photoimage(name, color=color, size=size)
        try:
            tile_color, tile_alpha = tile
            pad = self._icon_tile_pad
            tile_px = size + pad * 2
            scale = 4
            px = tile_px * scale
            img = _PILImage.new('RGBA', (px, px), (0, 0, 0, 0))
            draw = _PILImageDraw.Draw(img)
            r = int(px * 0.28)
            draw.rounded_rectangle((0, 0, px - 1, px - 1), radius=r,
                                   fill=hex_to_rgba(tile_color, tile_alpha))
            glyph = IconLibrary.render(name, color=color, size=px, stroke_width=1.6)
            if glyph is not None:
                img.paste(glyph, (0, 0), glyph)
            final = img.resize((tile_px, tile_px), _PILImage.LANCZOS)
            return _PILImageTk.PhotoImage(final)
        except Exception:
            return IconLibrary.to_photoimage(name, color=color, size=size)

    def _redraw(self, bg, fg, border, border_width, use_bold):
        self.delete('all')
        pad = self._outer_pad
        x1, y1 = pad, pad
        x2, y2 = pad + self._btn_w, pad + self._btn_h
        radius = BUTTON_CORNER_RADIUS

        # focus 环
        if self._is_focused and not self._is_disabled:
            try:
                focus_color = theme_manager.get_color('FOCUS_RING')
            except Exception:
                focus_color = '#3B82F6'
            self._focus_rect = self.create_polygon(
                self._rounded_rect_points(x1 - 2, y1 - 2, x2 + 2, y2 + 2, radius + 1),
                fill='', outline=focus_color, width=2, smooth=True,
            )

        # 背景：PIL 渲染（像素级平滑圆角）
        bg_image = None
        if _PIL_AVAILABLE:
            bg_image = self._render_button_bg(self._btn_w, self._btn_h, radius,
                                              fill_hex=bg, border_hex=border,
                                              border_width=border_width)
        if bg_image is not None:
            self._icon_photo = _PILImageTk.PhotoImage(bg_image)
            # 整数像素定位 + .5 偏移（避免子像素混叠，圆角边缘更顺滑）
            self._bg_image_id = self.create_image(
                int((x1 + x2) / 2) + 0.5, int((y1 + y2) / 2) + 0.5,
                image=self._icon_photo,
            )
        else:
            # 降级到 Canvas 多边形
            pts = self._rounded_rect_points(x1, y1, x2, y2, radius)
            if border_width > 0 and border != bg:
                self._bg_image_id = self.create_polygon(pts, fill=bg, outline=border,
                                                       width=border_width, smooth=True)
            else:
                self._bg_image_id = self.create_polygon(pts, fill=bg, outline=bg,
                                                       width=0, smooth=True)

        # Icon + 文字布局
        font_tuple = (FONT_FAMILY_UI, 10, 'bold' if use_bold else 'normal')
        icon_img = None
        if self._icon and _PIL_AVAILABLE:
            icon_color = self._icon_color if self._icon_color else fg
            try:
                icon_img = self._build_icon_image(self._icon, icon_color,
                                                  self._icon_size, self._icon_tile)
            except Exception:
                icon_img = None

        if icon_img is not None:
            icon_w = self._icon_size + (self._icon_tile_pad * 2 if self._icon_tile else 0)
            icon_padding = self._icon_padding
            text_w = self._measure_text_width(self._text, use_bold)
            total_w = icon_w + icon_padding + text_w
            center_x = (x1 + x2) / 2
            icon_cx = center_x - total_w / 2 + icon_w / 2
            text_cx = center_x + total_w / 2 - text_w / 2
            cy = (y1 + y2) / 2
            # icon ── 整数像素定位，并把 PhotoImage 持久化到 self 防 GC
            self._btn_icon_photo = icon_img
            self._icon_id = self.create_image(
                int(icon_cx) + 0.5, int(cy) + 0.5, image=self._btn_icon_photo
            )
            # 文字
            self._text_id = self.create_text(
                int(text_cx) + 0.5, int(cy) + 0.5, text=self._text, fill=fg,
                font=font_tuple, anchor='center', justify='center',
            )
        else:
            font = (FONT_FAMILY_UI, 10, 'bold' if use_bold else 'normal')
            self._text_id = self.create_text(
                int((x1 + x2) / 2) + 0.5, int((y1 + y2) / 2) + 0.5,
                text=self._text, fill=fg, font=font,
                anchor='center', justify='center',
            )
            self._icon_id = None

    @staticmethod
    def _rounded_rect_points(x1, y1, x2, y2, r):
        """生成圆角矩形多边形点列表（顺时针）。"""
        if x2 - x1 < 2 * r or y2 - y1 < 2 * r or r <= 0:
            return [x1, y1, x2, y1, x2, y2, x1, y2]
        import math
        steps = 6
        pts = []
        pts.extend([x1, y1 + r])
        for i in range(steps + 1):
            angle = math.pi + (math.pi / 2) * (i / steps)
            pts.extend([x1 + r + r * math.cos(angle), y1 + r + r * math.sin(angle)])
        pts.extend([x1 + r, y1])
        for i in range(steps + 1):
            angle = -math.pi / 2 + (math.pi / 2) * (i / steps)
            pts.extend([x2 - r + r * math.cos(angle), y1 + r + r * math.sin(angle)])
        pts.extend([x2, y1 + r])
        for i in range(steps + 1):
            angle = 0 + (math.pi / 2) * (i / steps)
            pts.extend([x2 - r + r * math.cos(angle), y2 - r + r * math.sin(angle)])
        pts.extend([x2 - r, y2])
        for i in range(steps + 1):
            angle = math.pi / 2 + (math.pi / 2) * (i / steps)
            pts.extend([x1 + r + r * math.cos(angle), y2 - r + r * math.sin(angle)])
        return pts

    # ----------------- 事件 -----------------
    def _on_enter(self, event=None):
        if self._is_disabled:
            return
        self._is_hover = True
        self._apply_style()

    def _on_leave(self, event=None):
        if self._is_disabled:
            return
        self._is_hover = False
        self._is_pressed = False
        self._apply_style()

    def _on_press(self, event=None):
        if self._is_disabled:
            return
        self._is_pressed = True
        self._apply_style()

    def _on_release(self, event=None):
        if self._is_disabled:
            return
        was_pressed = self._is_pressed
        self._is_pressed = False
        self._apply_style()
        if was_pressed and self._is_hover and self._command:
            try:
                self._command()
            except Exception as e:
                try:
                    from utils.logging_setup import log_error
                    log_error(f'按钮命令执行错误：{e}')
                except Exception:
                    print(f'按钮命令执行错误：{e}')

    def _on_key_press(self, event=None):
        if self._is_disabled:
            return
        if self._command:
            try:
                self._command()
            except Exception as e:
                try:
                    from utils.logging_setup import log_error
                    log_error(f'按钮命令执行错误：{e}')
                except Exception:
                    print(f'按钮命令执行错误：{e}')

    def _on_focus_in(self, event=None):
        if self._is_disabled:
            return
        self._is_focused = True
        self._apply_style()

    def _on_focus_out(self, event=None):
        self._is_focused = False
        self._apply_style()

    def disable(self):
        self._is_disabled = True
        try:
            self.config(cursor='arrow', state='disabled', takefocus=False)
        except Exception:
            pass
        self._apply_style()

    def enable(self):
        self._is_disabled = False
        try:
            self.config(cursor='hand2', state='normal', takefocus=True)
        except Exception:
            pass
        self._apply_style()

    def set_variant(self, variant):
        self._variant = variant
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
    - configure(variable=DoubleVar) 通过 DoubleVar 跟踪进度
    - ``cget('value')`` / ``itemconfigure(value=...)`` 用于读 / 写
    简化实现：监听 ``variable``（DoubleVar 0-100）变化时重绘。
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
            # 监听 DoubleVar 变化
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
        """DoubleVar 变化回调"""
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

    内部 ``progress_var`` 使用 ``DoubleVar``，所以 ``set_progress`` 收到前进值
    （target > current）时会启动 320ms 60fps 缓动动画；后退 / 重置直接 snap。
    """

    def __init__(self, parent, show_label=True, **kwargs):
        bg = parent.cget('bg') if parent.cget('bg') else theme_manager.get_color('BG_PRIMARY')
        super().__init__(parent, bg=bg, **kwargs)
        self._show_label = show_label
        # DoubleVar：让 _animate_progress_to 能以 < 1% 的步长平滑过渡
        # （IntVar 会在 set() 时截断小数，60fps 步进对动画就完全没意义了）
        self.progress_var = DoubleVar(value=0.0)
        self._progress_tween = None
        self._progress_after_id = None
        self.progress_bar = ModernProgressbar(self, variable=self.progress_var, maximum=100)
        # 居中：上下 pad 各 6px，让 8px 高的条对齐文字基线
        self.progress_bar.pack(fill='x', expand=True, padx=0, pady=6)
        if show_label:
            self.progress_label = Label(self, text="", font=(FONT_FAMILY_UI, 10),
                                        fg=theme_manager.get_color('FG_SECONDARY'), bg=bg)
            self.progress_label.pack(fill='x', expand=True, pady=(2, 0))

    def set_progress(self, value, text=""):
        """ProgressReporter 协议入口

        前进 (target > current) → 启动 320ms 缓动动画
        后退 / 重置 (target <= current) → 直接 snap，避免动画回弹
        """
        try:
            target = float(value)
        except (TypeError, ValueError):
            target = 0.0
        current = self.progress_var.get()
        if target > current:
            self._animate_progress_to(target)
        else:
            self.progress_var.set(target)
            self._cancel_pending_tick()
        if text and self._show_label and hasattr(self, 'progress_label'):
            self.progress_label.config(text=text)

    def get_progress(self):
        return self.progress_var.get()

    def destroy(self):
        """销毁前清掉 in-flight 动画，避免 after() 回调触发 "invalid command name"
        （Tk 的 after callback 是按 widget 注册的，destroy 后命令名失效）
        """
        self._cancel_pending_tick()
        super().destroy()

    # ==================== 进度条前进动画 ====================

    def _animate_progress_to(self, target: float, duration_ms: int = 320) -> None:
        """把进度从当前值平滑过渡到 target。

        60fps (16ms/step)；当 |delta| < 0.5 时直接 snap，避免无意义的
        一帧抖动。多次调用会覆盖在飞的 tween（新的 target 接管）。
        """
        start = self.progress_var.get()
        delta = target - start
        if abs(delta) < 0.5:                      # 已经接近就 snap
            self.progress_var.set(target)
            self._cancel_pending_tick()
            return
        steps = max(1, int(duration_ms / 16))    # 60fps
        self._progress_tween = {"delta": delta / steps, "left": steps, "target": target}
        self._tick_progress_animation()

    def _tick_progress_animation(self) -> None:
        tween = self._progress_tween
        if not tween:
            return
        if tween["left"] <= 0:
            self.progress_var.set(tween["target"])
            self._cancel_pending_tick()
            return
        self.progress_var.set(self.progress_var.get() + tween["delta"])
        tween["left"] -= 1
        self._progress_after_id = self.after(16, self._tick_progress_animation)

    def _cancel_pending_tick(self) -> None:
        """清掉 tween 并取消已 schedule 但还没跑的 after 帧"""
        self._progress_tween = None
        if getattr(self, '_progress_after_id', None):
            try:
                self.after_cancel(self._progress_after_id)
            except tk.TclError:
                pass
            self._progress_after_id = None



class IconLibrary:
    """图标库 ── PIL 矢量绘制（替代 emoji 作为 UI 图标）。"""
    GRID = 16
    SCALE = 4

    @classmethod
    def render(cls, name, color="#1E3A8A", size=16, stroke_width=1.5):
        if not _PIL_AVAILABLE:
            return None
        try:
            scale = cls.SCALE
            px = size * scale
            sw = max(1, int(round(stroke_width * scale)))
            img = _PILImage.new("RGBA", (px, px), (0, 0, 0, 0))
            draw = _PILImageDraw.Draw(img)
            s = px / cls.GRID
            def p(x, y):
                return (x * s, y * s)
            if name == "play":
                draw.polygon([p(4, 3), p(13, 8), p(4, 13)], fill=color)
            elif name == "stop":
                draw.rectangle([p(4, 4), p(12, 12)], fill=color)
            elif name == "pause":
                draw.rectangle([p(4.5, 3.5), p(6.5, 12.5)], fill=color)
                draw.rectangle([p(9.5, 3.5), p(11.5, 12.5)], fill=color)
            elif name == "download":
                draw.line([p(8, 2), p(8, 11)], fill=color, width=int(sw * 2))
                draw.polygon([p(4.5, 8), p(8, 12), p(11.5, 8)], fill=color)
                draw.line([p(3, 14), p(13, 14)], fill=color, width=sw)
            elif name == "upload":
                draw.line([p(8, 14), p(8, 5)], fill=color, width=int(sw * 2))
                draw.polygon([p(4.5, 8), p(8, 4), p(11.5, 8)], fill=color)
                draw.line([p(3, 2), p(13, 2)], fill=color, width=sw)
            elif name == "chart":
                draw.rectangle([p(3, 9), p(5.5, 13)], fill=color)
                draw.rectangle([p(7.25, 5), p(9.75, 13)], fill=color)
                draw.rectangle([p(11.5, 2), p(14, 13)], fill=color)
            elif name == "folder":
                draw.polygon([p(2, 5), p(6, 5), p(7, 3.5), p(14, 3.5),
                              p(14, 12.5), p(2, 12.5)], fill=color)
            elif name == "list":
                for y in [4, 8, 12]:
                    draw.ellipse([p(3, y - 1), p(4.5, y + 0.5)], fill=color)
                    draw.line([p(6, y), p(13, y)], fill=color, width=int(sw * 1.5))
            elif name == "search":
                draw.ellipse([p(2.5, 2.5), p(10.5, 10.5)], outline=color, width=int(sw * 1.5))
                draw.line([p(9.5, 9.5), p(14, 14)], fill=color, width=int(sw * 2))
            elif name == "doc":
                # 现代化 terminal 样式：圆角窗口 + 顶部 title bar + > prompt + text line
                # 外框（圆角窗口）
                draw.rounded_rectangle([p(2.5, 2.5), p(13.5, 13.5)],
                                        radius=p(1, 1)[0], fill=(255, 255, 255, 0),
                                        outline=color, width=sw)
                # 顶部 title bar
                draw.line([p(3.5, 4.5), p(12.5, 4.5)], fill=color, width=sw)
                # 左侧 3 个圆点（红/黄/绿 terminal 风格）
                draw.ellipse([p(3.5, 3), p(3.9, 3.4)], fill=color)
                draw.ellipse([p(4.2, 3), p(4.6, 3.4)], fill=color)
                draw.ellipse([p(4.9, 3), p(5.3, 3.4)], fill=color)
                # "> " prompt
                draw.line([p(4, 7), p(5.2, 8)], fill=color, width=int(sw * 1.2))
                draw.line([p(5.2, 8), p(4, 9)], fill=color, width=int(sw * 1.2))
                # 第一行文字
                draw.line([p(6, 8.5), p(11, 8.5)], fill=color, width=sw)
                # 第二行 prompt
                draw.line([p(4, 10.5), p(5.2, 11.5)], fill=color, width=int(sw * 1.2))
                draw.line([p(5.2, 11.5), p(4, 12.5)], fill=color, width=int(sw * 1.2))
                # 第二行文字
                draw.line([p(6, 12), p(9.5, 12)], fill=color, width=sw)
            elif name == "console":
                # 控制台样式：与 doc 类似但 prompt 是 $ 符号
                draw.rounded_rectangle([p(2.5, 2.5), p(13.5, 13.5)],
                                        radius=p(1, 1)[0], outline=color, width=sw)
                draw.line([p(3.5, 4.5), p(12.5, 4.5)], fill=color, width=sw)
                # $ 符号（左上）
                draw.line([p(6, 7), p(4, 7)], fill=color, width=sw)
                draw.line([p(4, 7), p(4, 9.5)], fill=color, width=sw)
                draw.line([p(4, 9.5), p(6, 9.5)], fill=color, width=sw)
                draw.line([p(6, 9.5), p(6, 11.5)], fill=color, width=sw)
                draw.line([p(6, 11.5), p(4, 11.5)], fill=color, width=sw)
                # 文字行
                draw.line([p(7.5, 8), p(12, 8)], fill=color, width=sw)
                draw.line([p(5, 12), p(11, 12)], fill=color, width=sw)
            elif name == "copy":
                draw.rectangle([p(5, 2), p(12, 9)], fill=color)
                draw.rectangle([p(3, 5), p(11, 13)], fill=(255, 255, 255, 255), outline=color, width=sw)
                for y in [7.5, 9.5, 11.5]:
                    draw.line([p(4.5, y), p(9.5, y)], fill=color, width=int(sw * 0.8))
            elif name == "save":
                draw.rectangle([p(3, 3), p(13, 13)], outline=color, width=sw)
                draw.rectangle([p(5, 3), p(11, 6.5)], fill=color)
                draw.rectangle([p(7, 8.5), p(11, 12)], fill=color)
            elif name == "trash":
                draw.rectangle([p(3, 3), p(13, 4.5)], fill=color)
                draw.line([p(6, 3), p(6, 1.5)], fill=color, width=sw)
                draw.line([p(10, 3), p(10, 1.5)], fill=color, width=sw)
                draw.line([p(5.5, 1.5), p(10.5, 1.5)], fill=color, width=sw)
                draw.polygon([p(4, 5), p(12, 5), p(11, 14), p(5, 14)], fill=color)
                for y in [8, 10.5, 13]:
                    draw.line([p(7, y), p(9, y)], fill=(255, 255, 255, 200), width=int(sw * 0.8))
            elif name == "check":
                draw.line([p(3, 8), p(6.5, 11.5)], fill=color, width=int(sw * 2))
                draw.line([p(6.5, 11.5), p(13, 4.5)], fill=color, width=int(sw * 2))
            elif name == "circle":
                draw.ellipse([p(4, 4), p(12, 12)], fill=color)
            elif name == "warn":
                draw.polygon([p(8, 3), p(14, 13), p(2, 13)], fill=color)
                draw.line([p(8, 6.5), p(8, 9.5)], fill=(255, 255, 255, 255), width=int(sw * 1.5))
                draw.ellipse([p(7.3, 10.8), p(8.7, 12)], fill=(255, 255, 255, 255))
            elif name == "info":
                draw.ellipse([p(3, 3), p(13, 13)], outline=color, width=sw)
                draw.ellipse([p(7.3, 5.8), p(8.7, 7.2)], fill=color)
                draw.line([p(8, 8.5), p(8, 11)], fill=color, width=int(sw * 1.5))
            elif name == "error":
                draw.line([p(4, 4), p(12, 12)], fill=color, width=int(sw * 2))
                draw.line([p(12, 4), p(4, 12)], fill=color, width=int(sw * 2))
            elif name == "cpu":
                # CPU/Chip 样式：方形主体 + 上下左右各 2 个引脚
                # 主体
                draw.rectangle([p(4, 4), p(12, 12)], fill=color)
                # 引脚（上）
                draw.rectangle([p(5.5, 2), p(6.5, 4)], fill=color)
                draw.rectangle([p(9.5, 2), p(10.5, 4)], fill=color)
                # 引脚（下）
                draw.rectangle([p(5.5, 12), p(6.5, 14)], fill=color)
                draw.rectangle([p(9.5, 12), p(10.5, 14)], fill=color)
                # 引脚（左）
                draw.rectangle([p(2, 5.5), p(4, 6.5)], fill=color)
                draw.rectangle([p(2, 9.5), p(4, 10.5)], fill=color)
                # 引脚（右）
                draw.rectangle([p(12, 5.5), p(14, 6.5)], fill=color)
                draw.rectangle([p(12, 9.5), p(14, 10.5)], fill=color)
                # 中心圆点（白色）
                draw.ellipse([p(7, 7), p(9, 9)], fill=(255, 255, 255, 255))
            elif name == "code":
                # Code 样式：</> 角括号
                # 左 < 
                draw.line([p(6, 4), p(3, 8)], fill=color, width=int(sw * 1.8))
                draw.line([p(3, 8), p(6, 12)], fill=color, width=int(sw * 1.8))
                # 右 >
                draw.line([p(10, 4), p(13, 8)], fill=color, width=int(sw * 1.8))
                draw.line([p(13, 8), p(10, 12)], fill=color, width=int(sw * 1.8))
                # 中间斜杠 /
                draw.line([p(9, 3), p(7, 13)], fill=color, width=int(sw * 1.5))
            elif name == "clock":
                # Clock 样式：圆形 + 12 点 + 中心 + 时针/分针
                draw.ellipse([p(3, 3), p(13, 13)], outline=color, width=int(sw * 1.5))
                # 12 点
                draw.ellipse([p(7.7, 3.5), p(8.3, 4.3)], fill=color)
                # 中心
                draw.ellipse([p(7.5, 7.5), p(8.5, 8.5)], fill=color)
                # 时针（指向 10 点）
                draw.line([p(8, 8), p(5.5, 6)], fill=color, width=int(sw * 1.3))
                # 分针（指向 2 点）
                draw.line([p(8, 8), p(11, 7)], fill=color, width=sw)
            elif name == "level":
                # Level 样式：3 根递增的横条（音量/等级条）
                # 短 - 中 - 长
                draw.rectangle([p(3, 10), p(5.5, 13)], fill=color)
                draw.rectangle([p(6.5, 7.5), p(9, 13)], fill=color)
                draw.rectangle([p(10, 4), p(12.5, 13)], fill=color)
                # 底部基线
                draw.line([p(2.5, 13.5), p(13, 13.5)], fill=color, width=sw)
            elif name == "gear":
                # 实心齿轮剪影：8 齿，填充色，确保 16~24px 都清晰可辨。
                # 小尺寸下线描齿轮会糊成一团，实心剪影可读性最好。
                import math
                cx, cy = 8, 8
                outer_r, inner_r = 6.2, 4.4
                pts = []
                for i in range(8):
                    a_out = i * math.pi / 4
                    a_in = (i + 0.5) * math.pi / 4
                    pts.append((cx + outer_r * math.cos(a_out),
                                cy + outer_r * math.sin(a_out)))
                    pts.append((cx + inner_r * math.cos(a_in),
                                cy + inner_r * math.sin(a_in)))
                draw.polygon([p(x, y) for x, y in pts], fill=color)
                # 不画中心孔：16~24px 下实心齿轮剪影语义已足够清晰，
                # 中心孔会让小尺寸更乱。
            elif name == "server":
                # 服务器机箱：圆角外框 + 三条横槽 + 两个状态点
                draw.rounded_rectangle([p(2.5, 3), p(13.5, 13)],
                                       radius=p(1, 1)[0], outline=color, width=sw)
                for y in [5.5, 8, 10.5]:
                    draw.line([p(4, y), p(10, y)], fill=color, width=int(sw * 1.2))
                draw.ellipse([p(11.5, 5), p(12.5, 6)], fill=color)
                draw.ellipse([p(11.5, 9.5), p(12.5, 10.5)], fill=color)
            elif name == "check-circle":
                # 圆形勾选：外环 + 内部对勾
                draw.ellipse([p(2.5, 2.5), p(13.5, 13.5)], outline=color, width=int(sw * 1.6))
                draw.line([p(5, 8.2), p(7, 10.5)], fill=color, width=int(sw * 2))
                draw.line([p(7, 10.5), p(11.5, 5.5)], fill=color, width=int(sw * 2))
            elif name == "activity":
                # 心跳折线（巡检中）
                draw.line([p(2, 8), p(5, 8), p(6.5, 4.5), p(8, 11.5),
                           p(9.5, 8), p(14, 8)], fill=color, width=int(sw * 1.8))
            elif name == "select-all":
                # 全选：圆角方框 + 内部对勾（区别于 check-circle 的圆形）
                draw.rounded_rectangle([p(2.5, 2.5), p(13.5, 13.5)],
                                       radius=p(1, 1)[0], outline=color, width=sw)
                draw.line([p(5, 8), p(7.5, 10.5)], fill=color, width=int(sw * 2))
                draw.line([p(7.5, 10.5), p(12, 5.5)], fill=color, width=int(sw * 2))
            elif name == "invert":
                # 反选：左右两组反向箭头（上⇄下 交换）
                draw.line([p(4.5, 4), p(4.5, 11)], fill=color, width=int(sw * 1.5))
                draw.polygon([p(3, 8.5), p(4.5, 11.5), p(6, 8.5)], fill=color)
                draw.line([p(11.5, 5), p(11.5, 12)], fill=color, width=int(sw * 1.5))
                draw.polygon([p(10, 7.5), p(11.5, 4.5), p(13, 7.5)], fill=color)
            elif name == "signal":
                # 连通性：WiFi 信号弧（圆心在底部，向上辐射）
                import math
                for rb in (7, 4.5, 2):
                    box = [p(8 - rb, 13 - rb), p(8 + rb, 13 + rb)]
                    draw.arc(box, start=225, end=315, fill=color, width=sw)
                draw.ellipse([p(7.2, 12.2), p(8.8, 13.8)], fill=color)
            elif name == "theme":
                # 主题（外观）：太阳 ── 中心圆 + 八向光芒
                import math
                draw.ellipse([p(6, 6), p(10, 10)], fill=color)
                cx, cy = 8, 8
                for ang in range(0, 360, 45):
                    a = math.radians(ang)
                    x1, y1 = cx + 5.2 * math.cos(a), cy + 5.2 * math.sin(a)
                    x2, y2 = cx + 3.4 * math.cos(a), cy + 3.4 * math.sin(a)
                    draw.line([(x1 * s, y1 * s), (x2 * s, y2 * s)],
                              fill=color, width=int(sw * 1.2))
            elif name == "contrast":
                # 高对比度：左半实心 + 右半描边 的圆（经典 contrast 图标）
                draw.pieslice([p(3, 3), p(13, 13)], start=90, end=270, fill=color)
                draw.arc([p(3, 3), p(13, 13)], start=270, end=90, fill=color, width=sw)
            elif name == "help":
                # 帮助：圆 + 问号
                draw.ellipse([p(2.5, 2.5), p(13.5, 13.5)], outline=color, width=sw)
                draw.arc([p(5.5, 4.5), p(10.5, 8.5)], start=200, end=340, fill=color, width=sw)
                draw.line([p(8, 8), p(8, 10.5)], fill=color, width=sw)
                draw.ellipse([p(7.3, 11), p(8.7, 12.4)], fill=color)
            else:
                return None
            return img.resize((size, size), _PILImage.LANCZOS)
        except Exception:
            return None

    # 缓存的是 PIL Image（与 Tk 解耦），不是 PhotoImage（与 Tk root 绑定）
    # 原因：PhotoImage 在 Tk root 销毁后失效，导致测试或多窗口场景下图像丢失
    _cache = {}

    @classmethod
    def to_photoimage(cls, name, color="#1E3A8A", size=16, stroke_width=1.5):
        if not _PIL_AVAILABLE:
            return None
        key = (name, color.lower(), size, stroke_width)
        # 缓存的是 PIL Image（共享），每次创建新的 PhotoImage（绑定当前 Tk）
        if key not in cls._cache:
            cls._cache[key] = cls.render(name, color, size, stroke_width)
        img = cls._cache[key]
        if img is None:
            return None
        return _PILImageTk.PhotoImage(img)

    @classmethod
    def clear_cache(cls):
        cls._cache.clear()


def make_icon_label(parent, icon_name, text, font, fg, bg, icon_size=16, icon_color=None,
                    match_text_height=False):
    """创建一个 [icon] [text] 横向排列的 Label 容器。

    Args:
        parent: 父容器
        icon_name: IconLibrary 中的图标名（如 "list"、"doc"）
        text: 文字
        font: 文字 font tuple
        fg: 文字颜色
        bg: 背景颜色
        icon_size: 图标像素大小（match_text_height=False 时生效）
        icon_color: 图标颜色（默认同 fg）
        match_text_height: 为 True 时图标像素高度自动对齐文字行高
            （font linespace），保证图标与文字视觉等高、垂直居中对齐。

    Returns:
        (frame, text_label) ── 包含图标的 Frame 和文字 Label
    """
    if icon_color is None:
        icon_color = fg
    frame = Frame(parent, bg=bg)
    # Text
    text_label = Label(frame, text=text, font=font, fg=fg, bg=bg)

    # 计算图标尺寸：默认用 icon_size；match_text_height 时对齐文字行高
    size = icon_size
    if match_text_height:
        try:
            import tkinter.font as tkfont
            fnt = tkfont.Font(font=font)
            linespace = fnt.metrics('linespace')
            # 对齐到文字行高（图标高度 === 文字高度），最小 8px 兜底
            size = max(8, int(round(linespace)))
        except Exception:
            pass

    # Icon
    icon_photo = IconLibrary.to_photoimage(icon_name, color=icon_color, size=size)
    if icon_photo is not None:
        icon_label = Label(frame, image=icon_photo, bg=bg)
        icon_label.image = icon_photo  # 防止 GC
        icon_label.pack(side="left", padx=(0, 6))
    text_label.pack(side="left")
    return frame, text_label



class LogTag(Frame):
    """日志级别小标签（带颜色的徽章）"""

    def __init__(self, parent, level='INFO', **kwargs):
        super().__init__(parent, **kwargs)
        # Metro：块状色片（实底色 + 白字）
        bg, fg = LOG_TAG_COLORS.get(level, LOG_TAG_COLORS['INFO'])
        self.label = Label(self, text=level, font=(FONT_FAMILY_UI, 9, 'bold'),
                           fg=fg, bg=bg, padx=8, pady=2)
        self.label.pack()


class StatCard(Frame):
    """KPI 统计卡片 ── 图标 tile + 大数值 + 标签 + 可选副文案。主题感知。

    落地 README v2.2.0 承诺的 KPI 卡片，复用 theme.py 已预留的
    ``COLOR_GOLD`` / ``FONT_SIZE_KPI_VALUE`` token。数值支持 ``set_value``
    实时刷新（带 ~300ms 缓动计数动画），契合 premium 调性。

    用法::

        card = StatCard(parent, 'server', '设备总数', value=0)
        card.set_value(42)                 # 缓动计数到 42
        card.set_caption('已加载')          # 更新副文案
    """

    def __init__(self, parent, icon_name, label, value=0, value_color=None,
                 caption="", accent=None, icon_size=34, tile_size=42, **kwargs):
        bg = parent.cget('bg') if parent.cget('bg') else theme_manager.get_color('BG_CARD')
        super().__init__(parent, bg=bg,
                         highlightthickness=1,
                         highlightbackground=theme_manager.get_color('BORDER'),
                         bd=0, **kwargs)
        self._icon_name = icon_name
        self._label = label
        self._value = int(value)
        self._caption = caption
        self._accent = accent or theme_manager.get_color('ACCENT')
        self._value_color = value_color or theme_manager.get_color('GOLD')
        self._icon_size = icon_size
        self._tile_size = tile_size
        self._icon_photo = None
        self._value_tween = None
        self._build()

    # ----------------- 构建 -----------------

    def _build(self):
        inner = Frame(self, bg=self.cget('bg'))
        # 横向排版：图标 tile ─ 大数值 ─ 文字说明（标签/副文案堆叠），三者并排
        inner.pack(fill='both', expand=True, padx=CARD_PADDING, pady=4)
        # 图标 tile（浅色 tint 圆角方块 + 矢量图标）
        self._tile_label = Label(inner, bg=self.cget('bg'))
        self._tile_label.pack(side='left', padx=(0, 12))
        # 大数值（与说明并排）
        self._value_label = Label(inner, text=str(self._value),
                                  font=(FONT_FAMILY_UI, FONT_SIZE_KPI_VALUE, 'bold'),
                                  fg=self._value_color, bg=self.cget('bg'))
        self._value_label.pack(side='left', padx=(0, 10))
        # 文字说明块（标签 + 副文案 竖直堆叠，与数值右对齐并排）
        desc_block = Frame(inner, bg=self.cget('bg'))
        desc_block.pack(side='left', fill='y')
        self._label_label = Label(desc_block, text=self._label,
                                  font=(FONT_FAMILY_UI, FONT_SIZE_KPI_LABEL),
                                  fg=theme_manager.get_color('FG_SECONDARY'),
                                  bg=self.cget('bg'))
        self._label_label.pack(anchor='w', pady=(1, 0))
        self._caption_label = Label(desc_block, text=self._caption,
                                     font=(FONT_FAMILY_UI, 9),
                                     fg=theme_manager.get_color('FG_LIGHT'),
                                     bg=self.cget('bg'))
        self._caption_label.pack(anchor='w', pady=(2, 0))
        self._render_tile()

    def _render_tile(self):
        """用 PIL 渲染 [tint 圆角底 + 居中矢量图标] 的 tile。"""
        if not _PIL_AVAILABLE:
            return
        try:
            scale = 4
            px = self._tile_size * scale
            img = _PILImage.new('RGBA', (px, px), (0, 0, 0, 0))
            draw = _PILImageDraw.Draw(img)
            r = 11 * scale
            # 浅色 tint 底（accent @ ~10% 透明度，柔和不抢戏）
            draw.rounded_rectangle((0, 0, px - 1, px - 1), radius=r,
                                   fill=self._hex_to_rgba(self._accent, 26))
            # 图标：同尺寸超采样渲染后直接叠加（已含透明通道）
            icon_img = IconLibrary.render(self._icon_name, color=self._accent,
                                          size=px, stroke_width=1.6)
            if icon_img is not None:
                img.paste(icon_img, (0, 0), icon_img)
            final = img.resize((self._tile_size, self._tile_size), _PILImage.LANCZOS)
            self._icon_photo = _PILImageTk.PhotoImage(final)
            self._tile_label.configure(image=self._icon_photo)
        except Exception:
            pass

    @staticmethod
    def _hex_to_rgba(hx, alpha=255):
        hx = hx.lstrip('#')
        return (int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16), alpha)

    # ----------------- 实时更新接口 -----------------

    def set_value(self, value, animate=True):
        """更新大数值。animate=True 时 ~300ms 缓动计数（线程安全，主线程 after 驱动）。"""
        try:
            target = int(round(value))
        except (TypeError, ValueError):
            target = 0
        if not animate or not self.winfo_exists():
            self._value = target
            self._value_label.config(text=str(target))
            return
        if self._value == target:
            return
        start = self._value
        delta = target - start
        steps = max(1, min(24, abs(delta)))
        self._value_tween = {'delta': delta / steps, 'left': steps, 'target': target}
        self._tick_value()

    def _tick_value(self):
        t = getattr(self, '_value_tween', None)
        if not t or not self.winfo_exists():
            self._value_tween = None
            return
        if t['left'] <= 0:
            self._value = t['target']
            self._value_label.config(text=str(t['target']))
            self._value_tween = None
            return
        self._value = int(round(self._value + t['delta']))
        self._value_label.config(text=str(self._value))
        t['left'] -= 1
        self.after(16, self._tick_value)

    def set_caption(self, text):
        self._caption = text
        if self.winfo_exists():
            self._caption_label.config(text=text)

    def set_accent(self, accent=None, value_color=None):
        if accent:
            self._accent = accent
        if value_color:
            self._value_color = value_color
            self._value_label.config(fg=self._value_color)
        self._render_tile()
