"""路径与目录常量。

所有 IO 路径在这里集中定义，模块化后其它模块从这里导入。
"""
import os
import sys


def _project_root():
    """项目根目录。

    - 源码运行：``network_inspection.py`` 所在目录
    - PyInstaller 打包：从 ``sys._MEIPASS`` 取解压根（__file__ 已不可信）
    """
    meipass = getattr(sys, '_MEIPASS', None)
    if meipass:
        # PyInstaller 单文件模式：所有 bundle 资源在这个临时目录里
        return os.path.join(meipass)
    # 源码运行：utils/paths.py 的上级即项目根
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# 项目根
PROJECT_ROOT = _project_root()

# 配置目录：放 devices.csv / device_types.csv / commands/
CONFIG_DIR = os.path.join(PROJECT_ROOT, 'config')
COMMANDS_DIR = os.path.join(CONFIG_DIR, 'commands')

# 巡检日志目录
LOG_DIR_NAME = "InspectionLogs"
LOG_SUBDIR_NAME = "logs"


def project_log_root():
    """运行期日志根目录（按 CWD，便于用户把日志放在工作目录下）"""
    return os.path.join(os.getcwd(), LOG_DIR_NAME)
