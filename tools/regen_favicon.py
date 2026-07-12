"""生成多分辨率 favicon.ico（16/32/48/64/128/256）

Pillow 的 ICO save 不支持 append_images 的多帧（只支持 sizes= 从单源缩放），
所以这里直接手写 ICO 容器。每帧内嵌 PNG（PNG-in-ICO 格式，Win Vista+ 支持）。
"""
from PIL import Image
import os, struct, io


def build_ico(frames: list) -> bytes:
    """frames: list of (PIL.Image, size_int)

    返回完整 ICO 文件字节。
    """
    # ── 1. 把每帧编码成 PNG，存为 bytes ──
    entries = []  # (size, png_bytes)
    for img, size in frames:
        buf = io.BytesIO()
        # 转成 ICO 友好的模式：<=256 色用 P (调色板)，否则 RGBA
        if img.mode == 'RGBA' and size <= 256:
            # PNG-in-ICO 支持 RGBA
            pass
        img.save(buf, format='PNG')
        entries.append((size, buf.getvalue()))

    # ── 2. 写 ICO 头 ──
    count = len(entries)
    # header: 6 bytes = reserved(2) + type(2) + count(2)
    # dir entry: 16 bytes = width(1) + height(1) + color_count(1) + reserved(1)
    #            + planes(2) + bitcount(2) + size(4) + offset(4)
    header_size = 6 + 16 * count
    body = b''
    offsets = []
    for size, png in entries:
        offsets.append(header_size + len(body))
        body += png
    header = struct.pack('<HHH', 0, 1, count)
    dir_bytes = b''
    for (size, png), off in zip(entries, offsets):
        # ICO 用 0 表示 256
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        dir_bytes += struct.pack(
            '<BBBBHHII',
            w, h,                  # width, height
            0,                     # color count (palette images)
            0,                     # reserved
            1,                     # planes
            32,                    # bit count
            len(png),              # size of image data
            off,                   # offset
        )
    return header + dir_bytes + body


def main():
    src_path = r'C:\Users\liuhua\Desktop\Github\network_inspection\favicon.ico'

    src = Image.open(src_path).copy().convert('RGBA')
    print(f'源: {src.size} {src.mode}')

    sizes = [16, 32, 48, 64, 128, 256]
    frames = []
    for s in sizes:
        im = src.resize((s, s), Image.LANCZOS)
        if im.mode != 'RGBA':
            im = im.convert('RGBA')
        frames.append((im, s))

    ico_bytes = build_ico(frames)
    print(f'生成 ICO: {len(ico_bytes)} bytes')

    # 写新文件
    tmp = src_path + '.new'
    with open(tmp, 'wb') as f:
        f.write(ico_bytes)
    os.replace(tmp, src_path)
    print(f'已写入: {os.path.getsize(src_path)} bytes')

    # 验证
    with open(src_path, 'rb') as f:
        data = f.read()
    _, _, count = struct.unpack('<HHH', data[:6])
    print(f'ICO 帧数: {count}')
    for i in range(count):
        off = 6 + i * 16
        w, h, _, _, _, bpp, size, _ = struct.unpack('<BBBBHHII', data[off:off+16])
        w = 256 if w == 0 else w
        h = 256 if h == 0 else h
        print(f'  {w}x{h} {bpp}bpp {size} bytes')


if __name__ == '__main__':
    main()
