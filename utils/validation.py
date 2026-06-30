"""输入验证与文件名清洗（无外部依赖）。"""
import re
import ipaddress


def validate_ip(ip: str) -> bool:
    """验证 IP 地址格式（同时支持 v4 / v6）"""
    if not isinstance(ip, str):
        return False
    try:
        ipaddress.ip_address(ip.strip())
        return True
    except (ValueError, AttributeError):
        return False


def validate_port(port) -> bool:
    """验证端口号范围 1-65535"""
    try:
        p = int(port)
        return 1 <= p <= 65535
    except (TypeError, ValueError):
        return False


# Windows 非法文件名字符
_WIN_ILLEGAL = re.compile(r'[<>:"/\\|?*]')


def sanitize_filename(filename: str) -> str:
    """清理文件名，移除 Windows 非法字符。

    设备名可能含 `<>:"|?*` 之一（用户配错 / 设备名特殊），先清洗再拼路径，
    否则 ``open()`` 抛 OSError。中文字符不在清洗范围，原样保留。
    """
    if not isinstance(filename, str):
        return ''
    return _WIN_ILLEGAL.sub('_', filename)
