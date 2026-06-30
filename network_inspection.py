# -*- coding: utf-8 -*-
"""
网络设备自动巡检工具 v2.1.1
Network Device Inspection Tool

启动入口：``python network_inspection.py``

本文件只做两件事：
1. 调用 ``main()`` 启动 GUI
2. 把拆分到 core/ ui/ utils/ 的公共 API 重新汇出，保留
   ``import network_inspection as ni`` 风格的向后兼容（包括旧测试）。
"""
import os
import sys
import traceback
import tkinter as tk
from tkinter import Tk, messagebox

# ============== 把项目根加入 sys.path（支持 ``python network_inspection.py`` 直接跑） ==============
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# ============== 公共 API 汇出（兼容旧调用方） ==============
from utils.logging_setup import (
    LOG_QUEUE, setup_logging, debug_log, log_info, log_warning, log_error,
    format_traceback,
)
from utils.validation import validate_ip, validate_port, sanitize_filename
from utils.paths import CONFIG_DIR, COMMANDS_DIR, project_log_root, LOG_DIR_NAME, LOG_SUBDIR_NAME

from core.encoding import detect_file_encoding, resolve_effective_encoding, check_encoding_match
from core.config import (
    is_comment_line, _parse_selected,
    load_device_types_config, validate_device_types_config,
    load_devices, validate_devices_config, validate_devices_config_with_details,
    parse_commands_file, validate_commands_config, validate_config_file,
)
from core.inspector import (
    NETMIKO_AVAILABLE, missing_netmiko_message,
    ConnectHandler, NetMikoAuthenticationException, NetMikoTimeoutException,
    connect_with_retry, connect_and_execute,
)
from core.worker import (
    inspection_worker, _run_inspection_worker,
    ProgressReporter, DetailedProgressbarAdapter, IntVarProgressReporter,
    make_progress_reporter,
)
from ui.theme import theme_manager
from ui.widgets import ModernButton, ModernEntry, ModernProgressbar, DetailedProgressbar, LogTag
from ui.app import ModernNetworkInspectionUI

# 旧版曾用过的别名：``_resolve_effective_encoding`` -> ``resolve_effective_encoding``
_resolve_effective_encoding = resolve_effective_encoding
_check_encoding_match = check_encoding_match
_run_inspection_worker = _run_inspection_worker
# _inspection_lock 是 v2.1 旧 API；现在由 UI 实例持有，这里给个属性化的桩
class _CompatLock:
    def __init__(self): self._lock = __import__('threading').Lock()
    def __enter__(self): self._lock.acquire(); return self
    def __exit__(self, *a): self._lock.release()
_inspection_lock = _CompatLock()


# ============== 入口 ==============

def main():
    """主程序入口"""
    logger = setup_logging()
    log_info("程序开始启动")
    log_info(f"Python 版本：{sys.version}")
    log_info(f"运行路径：{os.getcwd()}")
    debug_log("日志系统初始化完成")

    try:
        root = Tk()
        app = ModernNetworkInspectionUI(root)
        root.mainloop()
    except Exception as e:
        error_log_path = os.path.join(project_log_root(), "logs", "inspection_error.log")
        os.makedirs(os.path.dirname(error_log_path), exist_ok=True)
        with open(error_log_path, "w", encoding="utf-8") as f:
            f.write(f"程序启动失败：{e}\n")
            f.write(traceback.format_exc())
        try:
            error_root = tk.Tk()
            error_root.withdraw()
            messagebox.showerror("启动失败", f"程序启动失败，错误信息已写入 {error_log_path}")
            error_root.destroy()
        except Exception:
            pass
        log_error(f"程序启动失败：{e}")
        debug_log(traceback.format_exc(), "ERROR")


if __name__ == "__main__":
    main()
