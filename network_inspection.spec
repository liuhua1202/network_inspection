# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec —— 网络设备自动巡检工具 v2.1.1

构建命令（项目根）：
    pyinstaller --clean network_inspection.spec

产物：dist/NetworkInspector-v2.1.1.exe（单文件，便携，零安装）
"""
import sys
from pathlib import Path

# --- 项目根 ---
PROJECT_ROOT = Path(SPECPATH).resolve()  # PyInstaller 注入的 spec 所在目录

# --- 数据文件：用 list 写"源相对路径, bundle 内目标路径" ---
added_files = [
    # config/ 整体目录：运行时需要 devices.csv + device_types.csv + commands/
    (str(PROJECT_ROOT / 'config'), 'config'),
    # favicon.ico：窗口图标（exe root）
    (str(PROJECT_ROOT / 'favicon.ico'), '.'),
]

# --- 隐藏导入（防止 PyInstaller 静态分析漏掉） ---
# 注意：pandas / openpyxl / netmiko 是显式依赖，import-time 已能扫到
# 这里列的是动态 import（如 `import pandas as pd` 在 try/except 内）
hidden_imports = [
    'pandas',
    'openpyxl',
    'netmiko',
]

a = Analysis(
    [str(PROJECT_ROOT / 'network_inspection.py')],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 体积优化：剔掉明显用不到的大依赖
        'matplotlib', 'numpy.tests', 'scipy', 'PyQt5', 'PyQt6',
        'IPython', 'jupyter', 'notebook',
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='NetworkInspector-v2.1.1',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                # --windowed：双击无控制台
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=str(PROJECT_ROOT / 'favicon.ico'),  # 可选；未嵌入时 Windows 用默认图标
)
