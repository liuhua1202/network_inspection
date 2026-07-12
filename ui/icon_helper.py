"""Windows 任务栏图标强设工具。

问题：Tkinter + PyInstaller --onefile 打包的 exe 在 Windows 10/11 上跑，
主窗口 / Toplevel / 任务栏图标显示 Tk 默认调色板，不是项目的 favicon.ico。

根因有三：
1. ``window.iconbitmap()`` 内部用 ``WM_SETICON`` 设 per-window icon，
   不会改 WNDCLASSEX.HICON（class icon）。Win10/11 任务栏非合并模式 / 系统
   菜单走的都是 class icon。
2. Tk 内部窗口层次在不同版本 Tk 上不同：
   - 老版本 Tk：``winfo_id()`` 返回 TkChild，``wm frame`` 返回 TkTopLevel
   - Py 3.14 + Tk 8.6 + Win11：``winfo_id()`` **直接就是 top-level**（class
     内部叫 TkChild 但 parent 是 Desktop，``GetParent(hwnd) == 0``）
   所以不能 hardcode 检查 class==``TkTopLevel``，要用 ``GetParent==0 AND
   GetAncestor(GA_PARENT).class=="#32769"`` 判断。
3. Tk 会在 ``Toplevel.__init__`` / paint 事件里用 ``SetClassLongPtr`` 把
   class icon 改回 Tk 默认，所以光设一次不够，需要 ``after()`` 链持续重设。

本模块提供：
- ``apply_icon(window)``：跨平台入口（macOS/Linux 走 iconphoto；Windows
  再走 iconbitmap + Win32 强设 + 60 秒 retry 链）
- ``_apply_icon_win32(window, ico_path)``：直接调 Win32 API 强设
  WM_SETICON + SetClassLongPtrW（HICON / HICONSM）

参考：C:\\Users\\liuhua\\Desktop\\Github\\GitHub-Backup-Manager\\docs\\windows-taskbar-icon.md
"""
import os
import sys
import ctypes
from ctypes import wintypes
from typing import Optional

from utils.paths import PROJECT_ROOT


# 资源文件名（项目根 / _MEIPASS 下均可）
_ICON_FILENAME = "favicon.ico"


def _resolve_icon_path() -> Optional[str]:
    """找到 favicon.ico 的绝对路径；找不到返回 None。

    PyInstaller --onefile 模式下 ``utils.paths.PROJECT_ROOT`` 已经是
    ``sys._MEIPASS``，所以不需要额外处理。
    """
    p = os.path.join(PROJECT_ROOT, _ICON_FILENAME)
    return p if os.path.exists(p) else None


# ============================================================
# 公开入口：apply_icon
# ============================================================

def apply_icon(window) -> None:
    """设置应用图标（窗口装饰 + Windows 任务栏 + 系统菜单）。

    对所有顶层窗口（Tk root + Toplevel）都要调一次。
    Pillow 缺失 / Win32 调用失败都静默，不阻塞启动。
    """
    ico_path = _resolve_icon_path()
    if not ico_path:
        return

    # ── 1. iconphoto（跨平台；macOS / Linux 唯一可用；Windows 标题栏兜底） ──
    try:
        from PIL import Image, ImageTk
        pil_img = Image.open(ico_path)
        if pil_img.mode == "RGBA":
            bg = Image.new("RGB", pil_img.size, (255, 255, 255))
            bg.paste(pil_img, mask=pil_img.split()[3])
            pil_img = bg
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")
        window.iconphoto(False, ImageTk.PhotoImage(pil_img))
    except Exception as e:
        print(f"[apply_icon] iconphoto 失败: {e}", file=sys.stderr)

    # ── 2 & 3. iconbitmap + Win32 强设（Windows only） ─────────
    if sys.platform != "win32":
        return

    try:
        window.iconbitmap(ico_path)
    except Exception as e:
        print(f"[apply_icon] iconbitmap 失败: {e}", file=sys.stderr)

    try:
        _apply_icon_win32(window, ico_path)
    except Exception as e:
        print(f"[apply_icon] win32 强设失败: {e}", file=sys.stderr)

    # ── 60 秒内 12 次重试，覆盖 Tk 在 Toplevel 创建 / paint 时机用
    # SetClassLongPtr 把 class icon 改回默认的副作用 ─────────
    def _retry():
        try:
            _apply_icon_win32(window, ico_path)
        except Exception:
            pass

    try:
        for ms in (50, 150, 300, 600, 1200, 2500, 5000,
                   10000, 20000, 35000, 50000, 60000):
            window.after(ms, _retry)
    except Exception:
        pass


# ============================================================
# 内部：_apply_icon_win32
# ============================================================

def _apply_icon_win32(window, ico_path: str) -> None:
    """Windows 任务栏图标强制覆盖：Win32 API 直接 LoadImage + WM_SETICON +
    SetClassLongPtrW，绕开 Tk 内置 iconbitmap 的局限。

    HWND 拿法（兼容老 / 新版本 Tk）：
    1. 先试 ``wm frame`` —— 老版本 Tk 返回 TkTopLevel HWND
    2. 否则用 ``winfo_id()`` —— Py 3.14 + Tk 8.6 + Win11 上本身就是 top-level
    3. 用 ``GetParent==0 AND GetAncestor(GA_PARENT).class=="#32769"`` 验证
       是真 top-level，避免误改别人的 class
    """
    user32 = ctypes.WinDLL("user32", use_last_error=True)

    LR_LOADFROMFILE = 0x00000010
    IMAGE_ICON = 1
    WM_SETICON = 0x0080
    ICON_BIG = 1
    ICON_SMALL = 0
    GCLP_HICON = -14
    GCLP_HICONSM = -34
    GA_PARENT = 1

    # ── 1. 拿 top-level HWND（先 wm frame，再 winfo_id） ──
    hwnd_int = None
    try:
        frame_id = window.tk.call("wm", "frame", window._w)
        s = str(frame_id).strip()
        hwnd_int = int(s, 16) if s.startswith(("0x", "0X")) else int(s)
    except Exception:
        pass
    if hwnd_int is None:
        hwnd_int = int(window.winfo_id())
    hwnd = wintypes.HWND(hwnd_int)

    # ── 2. 验证是 top-level：GetParent==0 且 GetAncestor(GA_PARENT) is Desktop ──
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    GetParent = user32.GetParent
    GetParent.argtypes = [wintypes.HWND]
    GetParent.restype = wintypes.HWND
    GetAncestor = user32.GetAncestor
    GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    GetAncestor.restype = wintypes.HWND

    parent = GetParent(hwnd)
    ga_parent = GetAncestor(hwnd, GA_PARENT)
    desktop_class = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(ga_parent, desktop_class, 256)

    # top-level 的特征：没有父窗口 OR 父窗口是 Desktop
    if parent != wintypes.HWND(0) and desktop_class.value != "#32769":
        return  # 不是 top-level，放弃（不要乱改别人的 class）

    # ── 3. ctypes 签名（64-bit 上不配会 crash 在 stdcall 栈错位） ──
    LoadImageW = user32.LoadImageW
    LoadImageW.argtypes = [
        wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT,
        ctypes.c_int, ctypes.c_int, wintypes.UINT,
    ]
    LoadImageW.restype = wintypes.HANDLE

    SendMessageW = user32.SendMessageW
    SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                             wintypes.WPARAM, wintypes.LPARAM]
    SendMessageW.restype = ctypes.c_ssize_t  # LRESULT，wintypes 没提供

    SetClassLongPtrW = user32.SetClassLongPtrW
    SetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    SetClassLongPtrW.restype = ctypes.c_ssize_t  # LONG_PTR = pointer-sized signed

    # ── 4. 加载 16/32 两个 HICON ──
    hicon_small = LoadImageW(None, ico_path, IMAGE_ICON, 16, 16, LR_LOADFROMFILE)
    hicon_big = LoadImageW(None, ico_path, IMAGE_ICON, 32, 32, LR_LOADFROMFILE)

    # ── 5. per-window：WM_SETICON（任务栏【合并】模式 + 标题栏） ──
    if hicon_small:
        SendMessageW(hwnd, WM_SETICON, ICON_SMALL, hicon_small)
    if hicon_big:
        SendMessageW(hwnd, WM_SETICON, ICON_BIG, hicon_big)

    # ── 6. class-level：SetClassLongPtrW（任务栏【非合并】模式 + 系统菜单） ──
    if hicon_big:
        try:
            SetClassLongPtrW(hwnd, GCLP_HICON, hicon_big)
        except Exception:
            pass
    if hicon_small:
        try:
            SetClassLongPtrW(hwnd, GCLP_HICONSM, hicon_small)
        except Exception:
            pass
