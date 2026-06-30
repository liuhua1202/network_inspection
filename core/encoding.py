"""编码处理：检测、解析、替换字符告警。"""
import os

from utils.logging_setup import LOG_QUEUE, debug_log

# 模块级编码缓存：同一文件多次加载时复用结果
_encoding_cache: dict = {}


def detect_file_encoding(file_path, encodings):
    """按顺序尝试 encodings，返回第一个能成功解码文件前 1KB 的编码。

    结果缓存到模块级 dict，文件路径为 key；命中缓存时直接返回。
    缓存大小未做限制 —— 加载 N 个配置文件 N 次属于一次性成本，进程内不会反复加载。
    """
    if file_path in _encoding_cache:
        cached = _encoding_cache[file_path]
        debug_log(f"使用缓存的编码：{file_path} -> {cached}")
        return cached

    debug_log(f"开始检测文件编码：{file_path}")
    for encoding in encodings:
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                f.read(1024)  # 只读前 1KB 检测
            _encoding_cache[file_path] = encoding
            debug_log(f"检测到文件编码：{file_path} -> {encoding}")
            return encoding
        except UnicodeDecodeError:
            continue
        except Exception as e:
            debug_log(f"编码检测异常：{file_path} -> {encoding}: {e}")
            continue

    # 所有编码都失败：兜底用第一个（不抛，避免一处坏文件炸掉整次启动）
    fallback = encodings[0] if encodings else 'utf-8'
    debug_log(f"所有编码尝试失败，使用默认编码：{fallback}")
    _encoding_cache[file_path] = fallback
    return fallback


def resolve_effective_encoding(device, device_config, default_encoding):
    """决定实际传给 Netmiko 的编码。

    优先级：device['encoding'] > device_config['encoding'] > default_encoding > 'gbk'
    返回小写字符串；空值 / None 视为未指定。
    默认 GBK 是因为项目中文环境、devices.csv 用 GBK 保存。
    """
    for src in (device.get('encoding') if isinstance(device, dict) else None,
                device_config.get('encoding') if isinstance(device_config, dict) else None,
                default_encoding):
        if isinstance(src, str) and src.strip():
            return src.strip().lower()
    return 'gbk'


def check_encoding_match(output, device_name, current_encoding, threshold=2):
    """检查输出是否含 Unicode 替换字符（U+FFFD），是则编码不匹配。

    参数:
        threshold: 超过该数量才算"明显不匹配"，避免单字符巧合

    返回: (matched: bool, bad_count: int)
    """
    if not output or not isinstance(output, str):
        return True, 0
    bad_count = output.count('\ufffd')
    if bad_count >= threshold:
        LOG_QUEUE.put(
            f"[WARNING] {device_name} 输出含 {bad_count} 个 Unicode 替换字符，"
            f"当前编码 '{current_encoding}' 似不匹配。"
            f"建议在 devices.csv 第 9 列指定正确编码（utf-8 / gbk / gb2312 / gb18030）。"
        )
        return False, bad_count
    return True, bad_count
