"""进程内验证 apply_icon：起一个 Tk 窗口，调 apply_icon，
然后读 GCLP_HICON / WM_GETICON 对比设前/设后。
"""
import os
import sys
import ctypes
from ctypes import wintypes

# 把项目根加到 sys.path
ROOT = r'C:\Users\liuhua\Desktop\Github\network_inspection'
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tkinter as tk
from ui.icon_helper import apply_icon


def get_hwnd_int(window):
    """拿 wm frame 的 HWND int（兼容 Tk 9.x 的 0x 前缀）"""
    try:
        s = str(window.tk.call("wm", "frame", window._w)).strip()
    except Exception:
        s = str(window.winfo_id())
    return int(s, 16) if s.startswith(("0x", "0X")) else int(s)


def get_class_name(hwnd):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, ctypes.c_int]
    user32.GetClassNameW.restype = ctypes.c_int
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(wintypes.HWND(hwnd), buf, 256)
    return buf.value


def read_icons(hwnd):
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.GetClassLongPtrW.restype = ctypes.c_ssize_t
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                    wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    h = wintypes.HWND(hwnd)
    return {
        "GCLP_HICON":   int(user32.GetClassLongPtrW(h, -14)),
        "GCLP_HICONSM": int(user32.GetClassLongPtrW(h, -34)),
        "WM_GETICON_BIG": int(user32.SendMessageW(h, 0x7F, 1, 0)),
        "WM_GETICON_SM":  int(user32.SendMessageW(h, 0x7F, 0, 0)),
    }


def icon_to_png(hicon, size, out_path):
    """把 HICON 转 PNG 存盘（验证用，目检像素）"""
    if not hicon:
        return None
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    # 用 GetIconInfo 拿 ICONINFO，再用 DrawIconEx 到 DC
    # 更简单：直接 System.Drawing.Icon.FromHandle (跨平台 P/Invoke)
    import ctypes.wintypes as w
    gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

    # 创建内存 DC + bitmap
    CreateCompatibleDC = gdi32.CreateCompatibleDC
    CreateCompatibleDC.argtypes = [w.HDC]
    CreateCompatibleDC.restype = w.HDC

    CreateCompatibleBitmap = gdi32.CreateCompatibleBitmap
    CreateCompatibleBitmap.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int]
    CreateCompatibleBitmap.restype = w.HBITMAP

    SelectObject = gdi32.SelectObject
    SelectObject.argtypes = [w.HDC, w.HGDIOBJ]
    SelectObject.restype = w.HGDIOBJ

    DrawIconEx = user32.DrawIconEx
    DrawIconEx.argtypes = [w.HDC, ctypes.c_int, ctypes.c_int, w.HICON,
                           ctypes.c_int, ctypes.c_int, w.UINT, w.HBRUSH, w.UINT]
    DrawIconEx.restype = w.BOOL

    hdc = CreateCompatibleDC(None)
    hbm = CreateCompatibleBitmap(hdc, size, size)
    SelectObject(hdc, hbm)
    DrawIconEx(hdc, 0, 0, w.HICON(hicon), size, size, 0, None, 0x0003)  # DI_NORMAL

    # 用 Pillow 转 PNG
    try:
        from PIL import Image
        # BITMAPINFOHEADER
        class BITMAPINFOHEADER(ctypes.Structure):
            _fields_ = [
                ("biSize", ctypes.c_uint32),
                ("biWidth", ctypes.c_int32),
                ("biHeight", ctypes.c_int32),
                ("biPlanes", ctypes.c_uint16),
                ("biBitCount", ctypes.c_uint16),
                ("biCompression", ctypes.c_uint32),
                ("biSizeImage", ctypes.c_uint32),
                ("biXPelsPerMeter", ctypes.c_int32),
                ("biYPelsPerMeter", ctypes.c_int32),
                ("biClrUsed", ctypes.c_uint32),
                ("biClrImportant", ctypes.c_uint32),
            ]
        class BITMAPINFO(ctypes.Structure):
            _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                        ("bmiColors", ctypes.c_uint32 * 3)]

        GetDIBits = gdi32.GetDIBits
        GetDIBits.argtypes = [w.HDC, w.HBITMAP, w.UINT, w.UINT, ctypes.c_void_p,
                              ctypes.POINTER(BITMAPINFO), w.UINT]
        GetDIBits.restype = ctypes.c_int

        bmi = BITMAPINFO()
        bmi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        bmi.bmiHeader.biWidth = size
        bmi.bmiHeader.biHeight = -size  # top-down
        bmi.bmiHeader.biPlanes = 1
        bmi.bmiHeader.biBitCount = 32
        bmi.bmiHeader.biCompression = 0  # BI_RGB
        buf = (ctypes.c_uint32 * (size * size))()
        GetDIBits(hdc, hbm, 0, size, ctypes.cast(buf, ctypes.c_void_p),
                  ctypes.byref(bmi), 0)

        img = Image.frombuffer("RGBA", (size, size), bytes(buf), "raw", "BGRA", 0, 1)
        img.save(out_path)
        return out_path
    except Exception as e:
        return f"(save failed: {e})"


def main():
    root = tk.Tk()
    root.title("verify taskbar icon")
    root.geometry("600x400")

    hwnd = get_hwnd_int(root)
    cls = get_class_name(hwnd)
    print(f"[before] hwnd=0x{hwnd:x} class={cls}")
    before = read_icons(hwnd)
    for k, v in before.items():
        print(f"  {k} = 0x{v:x}")

    # 调 apply_icon
    apply_icon(root)
    # 同步处理事件
    root.update_idletasks()
    root.update()

    print(f"[after ] hwnd=0x{hwnd:x} class={cls}")
    after = read_icons(hwnd)
    for k, v in after.items():
        print(f"  {k} = 0x{v:x}")

    # 抽 GCLP_HICON 像素存盘
    out = r'C:\Users\liuhua\Desktop\Github\network_inspection\tools\verify_after.png'
    saved = icon_to_png(after["GCLP_HICON"], 32, out)
    print(f"[saved] {saved}")

    # 抽 WM_GETICON_BIG 像素存盘
    out2 = r'C:\Users\liuhua\Desktop\Github\network_inspection\tools\verify_wmi.png'
    saved2 = icon_to_png(after["WM_GETICON_BIG"], 32, out2)
    print(f"[saved] {saved2}")

    # 验证：after 的 GCLP_HICON 和 WM_GETICON_BIG 都不为 0，且 GCLP != WM_GETICON？
    # 实际我们的 apply_icon 两者都设同一个 HICON，所以应该相等
    if after["GCLP_HICON"] and after["WM_GETICON_BIG"]:
        print("[OK] GCLP_HICON 和 WM_GETICON_BIG 都非零，图标已生效")
    else:
        print("[FAIL] GCLP_HICON 或 WM_GETICON_BIG 为零")

    if before["GCLP_HICON"] != after["GCLP_HICON"]:
        print(f"[OK] GCLP_HICON 已变化: 0x{before['GCLP_HICON']:x} -> 0x{after['GCLP_HICON']:x}")
    else:
        print(f"[WARN] GCLP_HICON 未变化 (0x{after['GCLP_HICON']:x})")

    # 等一下让 50ms 后的 retry 跑一次
    root.after(200, root.quit)
    root.mainloop()


if __name__ == "__main__":
    main()
