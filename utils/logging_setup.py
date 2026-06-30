"""日志系统与日志队列。

设计要点：
- ``LOG_QUEUE`` 仍为模块级单例：worker 线程、连通性测试线程、UI 主线程都要读它。
- ``debug_log`` 兼容历史调用方式（``debug_log(msg, level='INFO')``）。
- 日志文件按启动时间戳命名，单次启动一个；写入 UTF-8。
- 输出到 stderr 不重复，UI 自身的 Text 控件才是用户真正看到的地方。
- **v2.1.1 修复**：进入文件 / 控制台前对 ``password=...`` ``secret=...``
  ``auth_password=...`` 等敏感字段做脱敏（替换为 ``***``）。
"""
import os
import re
import queue
import logging
import traceback
from datetime import datetime

from utils.paths import project_log_root

LOG_QUEUE = queue.Queue()
_logger = None

# 敏感字段脱敏：形如 'password': 'xxx' / "secret"="xxx" / password=xxx / password 'xxx'
# 抓取时尽量限定引号边界，避免误伤正文里的 "password" 这个词
_SENSITIVE_KEYS = ('password', 'passwd', 'secret', 'auth_password', 'enable_password')
_REDACT_PATTERNS = [
    # JSON 风格:  "password": "xxx"   或   'password': 'xxx'
    re.compile(
        r'(["\'])(?P<key>password|passwd|secret|auth_password|enable_password)\1\s*:\s*'
        r'(["\'])(?P<val>[^"\']*)\3',
        re.IGNORECASE
    ),
    # 关键字=值 风格: password=xxx
    re.compile(
        r'(?P<key>\b(?:password|passwd|secret|auth_password|enable_password))'
        r'\s*=\s*(?P<val>[^\s,;]+)',
        re.IGNORECASE
    ),
    # Netmiko 异常风格：password 'xxx' / password "xxx"
    # 必须带引号 —— 避免误吞"password mismatch""password ok"这种正文
    re.compile(
        r'\b(?P<key>password|passwd|secret|auth_password|enable_password)\b'
        r'\s+(?P<val>[\'"][^\'"]+[\'"])',
        re.IGNORECASE
    ),
]


def _redact_sensitive(text: str) -> str:
    """把消息里的敏感字段值替换为 ``***``，返回新字符串。

    三个 pattern 顺序：
    1. JSON 风格（带冒号）   — ``"password": "xxx"``
    2. key=value 风格         — ``password=xxx``
    3. Netmiko 异常风格       — ``password 'xxx'`` / ``secret Sup3rS3cret``

    注意：第 3 个 pattern 也可能误伤正文里的 "password" 单词；
    这是个固有权衡 —— 选安全优先，宁可偶尔脱敏过度。
    """
    if not isinstance(text, str):
        return text

    def _json_repl(m):
        quote, key, _vq, _val = m.group(1), m.group('key'), m.group(3), m.group('val')
        return f"{quote}{key}{quote}: {quote}***{quote}"

    def _kv_repl(m):
        return f"{m.group('key')}=***"

    def _space_repl(m):
        # Netmiko 风格：保留引号但替换内容
        return f"{m.group('key')} ***"

    out = _REDACT_PATTERNS[0].sub(_json_repl, text)
    out = _REDACT_PATTERNS[1].sub(_kv_repl, out)
    out = _REDACT_PATTERNS[2].sub(_space_repl, out)
    return out


def setup_logging():
    """初始化日志系统；可重复调用（每次重启产生新文件）"""
    global _logger

    logs_dir = os.path.join(project_log_root(), "logs")
    os.makedirs(logs_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(
                os.path.join(logs_dir, f"all_logs_{timestamp}.log"),
                encoding='utf-8'
            ),
            logging.FileHandler(
                os.path.join(logs_dir, f"debug_{timestamp}.log"),
                encoding='utf-8'
            ),
            logging.StreamHandler()
        ]
    )

    debug_handler = logging.getLogger().handlers[1]
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.addFilter(lambda record: record.levelno == logging.DEBUG)

    console_handler = logging.getLogger().handlers[2]
    console_handler.setLevel(logging.INFO)

    _logger = logging.getLogger()
    return _logger


def debug_log(message, level="DEBUG"):
    """记录日志到文件 + 控制台（统一入口；自动脱敏）"""
    global _logger
    if _logger is None:
        _logger = setup_logging()

    safe = _redact_sensitive(message)

    level = (level or "DEBUG").upper()
    if level == "DEBUG":
        _logger.debug(safe)
    elif level == "INFO":
        _logger.info(safe)
    elif level == "WARNING":
        _logger.warning(safe)
    elif level == "ERROR":
        _logger.error(safe)
    elif level == "CRITICAL":
        _logger.critical(safe)
    else:
        _logger.debug(safe)


def log_info(message):
    debug_log(message, "INFO")


def log_warning(message):
    debug_log(message, "WARNING")


def log_error(message):
    debug_log(message, "ERROR")


def format_traceback() -> str:
    """返回当前异常的完整 traceback 字符串（敏感字段已脱敏）"""
    return _redact_sensitive(traceback.format_exc())
