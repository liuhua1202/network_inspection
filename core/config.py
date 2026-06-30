"""配置加载 / 解析 / 验证。

支持的输入：
- devices.csv / devices.txt    ——  设备列表
- device_types.csv / .txt      ——  设备类型定义
- commands/*.txt               ——  巡检命令（支持 # @heavy / # @timeout N 标记）
"""
import csv
import os

from utils.logging_setup import LOG_QUEUE, log_info, debug_log
from utils.validation import validate_ip, validate_port
from core.encoding import detect_file_encoding


# ==================== 通用解析工具 ====================

def is_comment_line(line_parts):
    """判断是否整行都是注释。

    约定：第一个非空字段以 ``#`` 开头即为注释行；
    中间或末尾出现的 ``#`` 视为数据内容（合法设备名/密码/命令都可能含 ``#``）。
    """
    if not line_parts:
        return False
    for part in line_parts:
        stripped = part.strip()
        if stripped:
            return stripped.startswith('#')
    return False


def _parse_selected(value):
    """把 '1'/'0'/'true'/'false'/'yes'/'no' 等解析为 bool；空值默认 True（向后兼容）"""
    if value is None:
        return True
    s = str(value).strip().lower()
    if s == '':
        return True
    if s in ('0', 'false', 'no', 'off', 'n', 'f'):
        return False
    if s in ('1', 'true', 'yes', 'on', 'y', 't'):
        return True
    # 兜底：非空且未识别为 false，则视作 true（不让用户写了中文"是"被静默忽略）
    return True


# ==================== device_types ====================

def load_device_types_config(file_path, encodings):
    """加载设备类型配置。

    格式（每行）：``类型ID|名称|Netmiko SSH 驱动|Netmiko Telnet 驱动|enable 模式(0/1)|分页命令|默认协议|命令文件``
    CSV 用 ``,`` 分隔，TXT 用 ``|`` 分隔，列少于 7 视为坏行跳过。
    """
    log_info(f"开始加载设备类型配置：{file_path}")
    if not file_path or not os.path.exists(file_path):
        error_msg = f"设备类型配置文件不存在：{file_path}"
        LOG_QUEUE.put(error_msg)
        debug_log(error_msg)
        return {}

    device_types = {}
    file_ext = os.path.splitext(file_path)[1].lower()
    debug_log(f"加载设备类型配置文件：{file_path}, 扩展名：{file_ext}")

    encoding = detect_file_encoding(file_path, encodings)
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            if file_ext == '.csv':
                reader = csv.reader(f)
                for row_num, parts in enumerate(reader, 1):
                    if not parts or is_comment_line(parts):
                        continue
                    if len(parts) >= 7:
                        device_id, name, ssh_driver, telnet_driver, enable_mode, paging_cmd, default_proto = [p.strip() for p in parts[:7]]
                        cmd_file = parts[7].strip() if len(parts) > 7 and parts[7].strip() else ""
                        device_types[device_id] = {
                            'name': name,
                            'netmiko_type': {'ssh': ssh_driver, 'telnet': telnet_driver},
                            'enable_mode': bool(int(enable_mode)),
                            'disable_paging_cmd': paging_cmd,
                            'default_protocol': default_proto,
                            'commands_file': cmd_file
                        }
                    else:
                        msg = f"设备类型配置第{row_num}行格式错误"
                        LOG_QUEUE.put(msg)
                        debug_log(msg)
            else:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        continue
                    parts = [p.strip() for p in stripped_line.split('|')]
                    if len(parts) >= 7:
                        device_id, name, ssh_driver, telnet_driver, enable_mode, paging_cmd, default_proto = parts[:7]
                        cmd_file = parts[7] if len(parts) > 7 and parts[7] else ""
                        device_types[device_id] = {
                            'name': name,
                            'netmiko_type': {'ssh': ssh_driver, 'telnet': telnet_driver},
                            'enable_mode': bool(int(enable_mode)),
                            'disable_paging_cmd': paging_cmd,
                            'default_protocol': default_proto,
                            'commands_file': cmd_file
                        }
                    else:
                        msg = f"设备类型配置第{line_num}行格式错误"
                        LOG_QUEUE.put(msg)
                        debug_log(msg)

        msg = f"成功加载设备类型配置：{file_path}，共{len(device_types)}种设备类型"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return device_types

    except Exception as e:
        msg = f"加载设备类型配置失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return {}


def validate_device_types_config(device_types):
    """验证设备类型配置完整性"""
    if not device_types:
        LOG_QUEUE.put("设备类型配置错误：未加载任何设备类型配置")
        debug_log("设备类型配置错误：未加载任何设备类型配置")
        return False

    for device_id, config in device_types.items():
        required_fields = ['name', 'netmiko_type', 'enable_mode', 'disable_paging_cmd', 'default_protocol']
        for field in required_fields:
            if field not in config:
                error_msg = f"设备类型配置错误：设备类型 {device_id} 缺少必要字段：{field}"
                LOG_QUEUE.put(error_msg)
                debug_log(error_msg)
                return False

        if config.get('default_protocol') not in ['ssh', 'telnet']:
            error_msg = f"设备类型配置错误：设备类型 {device_id} 的默认协议无效：{config.get('default_protocol')}"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False

    return True


# ==================== devices ====================

def load_devices(file_path, encodings):
    """加载设备列表。

    支持可选的 `selected` 列（第 10 列，CSV）/ `selected` 字段（| 分隔末尾，txt）。
    取值：1/0/true/false/yes/no。缺省视为 True（向后兼容）。

    列数 < 3、IP/类型 ID 缺失、或单行 int 解析失败（典型：header 行 "端口" 列）会被跳过并打 warning，
    不会让一份坏文件炸掉整次加载。
    """
    log_info(f"开始加载设备列表：{file_path}")
    if not file_path or not os.path.exists(file_path):
        error_msg = f"设备列表文件不存在：{file_path}"
        LOG_QUEUE.put(error_msg)
        debug_log(error_msg)
        return []

    devices = []
    file_ext = os.path.splitext(file_path)[1].lower()

    encoding = detect_file_encoding(file_path, encodings)
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            if file_ext == '.csv':
                reader = csv.reader(f)
                for row_num, parts in enumerate(reader, 1):
                    if not parts or is_comment_line(parts):
                        continue
                    if len(parts) < 3 or not all(parts[i].strip() for i in range(3)):
                        continue
                    try:
                        device = {
                            'device_name': parts[0].strip(),
                            'ip': parts[1].strip(),
                            'device_type': parts[2].strip(),
                            'username': parts[3].strip() if len(parts) > 3 else '',
                            'password': parts[4].strip() if len(parts) > 4 else '',
                            'secret': parts[5].strip() if len(parts) > 5 else '',
                            'port': int(parts[6].strip()) if len(parts) > 6 and parts[6].strip() else 22,
                            'protocol': parts[7].strip().lower() if len(parts) > 7 and parts[7].strip() else None,
                            'encoding': parts[8].strip() if len(parts) > 8 and parts[8].strip() else None,
                            'selected': _parse_selected(parts[9]) if len(parts) > 9 else True,
                        }
                        devices.append(device)
                    except (ValueError, IndexError) as e:
                        warn_msg = f"设备列表第{row_num}行解析失败，已跳过：{e}"
                        LOG_QUEUE.put(f"[WARNING] {warn_msg}")
                        debug_log(warn_msg)
            else:
                for line_num, line in enumerate(f, 1):
                    stripped_line = line.strip()
                    if not stripped_line or stripped_line.startswith('#'):
                        continue
                    parts = [p.strip() for p in stripped_line.split('|')]
                    if len(parts) < 3 or not all(parts[i].strip() for i in range(3)):
                        continue
                    try:
                        device = {
                            'device_name': parts[0],
                            'ip': parts[1],
                            'device_type': parts[2],
                            'username': parts[3] if len(parts) > 3 else '',
                            'password': parts[4] if len(parts) > 4 else '',
                            'secret': parts[5] if len(parts) > 5 else '',
                            'port': int(parts[6]) if len(parts) > 6 and parts[6] else 22,
                            'protocol': parts[7].lower() if len(parts) > 7 and parts[7] else None,
                            'encoding': parts[8].strip() if len(parts) > 8 and parts[8].strip() else None,
                            'selected': _parse_selected(parts[9]) if len(parts) > 9 else True,
                        }
                        devices.append(device)
                    except (ValueError, IndexError) as e:
                        warn_msg = f"设备列表第{line_num}行解析失败，已跳过：{e}"
                        LOG_QUEUE.put(f"[WARNING] {warn_msg}")
                        debug_log(warn_msg)

        msg = f"成功加载设备列表：{file_path}，共{len(devices)}台设备"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return devices

    except Exception as e:
        msg = f"加载设备列表失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return []


def validate_devices_config(devices, device_types):
    """验证设备列表配置（向后兼容的 bool 包装）"""
    return validate_devices_config_with_details(devices, device_types)['valid']


def validate_devices_config_with_details(devices, device_types):
    """验证设备列表配置并返回详细结果"""
    errors = []
    if not devices:
        errors.append("未加载任何设备列表")
        return {'valid': False, 'error_count': len(errors), 'errors': errors}
    if not device_types:
        errors.append("未加载设备类型配置，无法验证设备列表")
        return {'valid': False, 'error_count': len(errors), 'errors': errors}

    for device in devices:
        if not device.get('device_name', '').strip():
            errors.append("设备缺少名称")
            continue

        ip = device.get('ip', '').strip()
        if not ip:
            errors.append(f"设备 {device['device_name']} 的IP地址为空")
        elif not validate_ip(ip):
            errors.append(f"设备 {device['device_name']} 的IP地址格式错误：{ip}")

        device_type = device.get('device_type', '').strip()
        if not device_type:
            errors.append(f"设备 {device['device_name']} 的类型为空")
        elif device_type not in device_types:
            errors.append(f"设备 {device['device_name']} 的类型 {device_type} 不存在")

        protocol = device.get('protocol', '').strip()
        if protocol and protocol not in ['ssh', 'telnet']:
            errors.append(f"设备 {device['device_name']} 的协议 {protocol} 无效")

        try:
            port = int(device.get('port', 22))
            if not validate_port(port):
                errors.append(f"设备 {device['device_name']} 的端口 {port} 超出有效范围 (1-65535)")
        except (TypeError, ValueError):
            errors.append(f"设备 {device['device_name']} 的端口 {device.get('port', 22)} 不是有效数字")

    return {
        'valid': len(errors) == 0,
        'error_count': len(errors),
        'errors': errors
    }


# ==================== commands ====================

def parse_commands_file(file_path, encodings):
    """解析命令文件。

    返回值：[(command: str, is_heavy: bool, timeout_override: int | None), ...]
    注释行被忽略。
    支持两个标记：
        # @heavy           —— 下一条命令用 180s 超时
        # @timeout N       —— 下一条命令用 N 秒超时（最优先）
    """
    commands = []
    if not file_path or not os.path.exists(file_path):
        msg = f"命令文件不存在：{file_path}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands

    encoding = detect_file_encoding(file_path, encodings)
    try:
        pending_heavy = False
        pending_timeout = None
        heavy_count = 0
        with open(file_path, 'r', encoding=encoding) as f:
            for line in f:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                if stripped_line.startswith('#'):
                    lower = stripped_line.lower()
                    if lower == '# @heavy':
                        pending_heavy = True
                    elif lower.startswith('# @timeout'):
                        parts = stripped_line.split()
                        if len(parts) >= 3:
                            try:
                                pending_timeout = int(parts[2])
                            except ValueError:
                                pass
                    # 其它注释一律忽略
                    continue

                cmd = stripped_line
                timeout_override = pending_timeout
                is_heavy = pending_heavy
                if is_heavy:
                    heavy_count += 1
                pending_heavy = False
                pending_timeout = None
                commands.append((cmd, is_heavy, timeout_override))
        msg = f"成功加载命令文件：{file_path}，共{len(commands)}条命令"
        if heavy_count:
            msg += f"，其中重型命令 {heavy_count} 条"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands
    except Exception as e:
        msg = f"解析命令文件失败：{e}"
        LOG_QUEUE.put(msg)
        debug_log(msg)
        return commands


def validate_commands_config(device_types, command_files):
    """验证每个设备类型都关联了至少一条命令"""
    errors = []
    if not device_types:
        return True  # 没设备类型就无需校验

    for device_id, config in device_types.items():
        if device_id not in command_files or not command_files[device_id][1]:
            errors.append(f"设备类型 {device_id} ({config['name']}) 未配置有效巡检命令")

    if errors:
        for error in errors:
            LOG_QUEUE.put(f"命令配置错误：{error}")
            debug_log(f"命令配置错误：{error}")
        return False
    return True


# ==================== 文件结构校验 ====================

def validate_config_file(file_path, required_columns):
    """验证配置文件首行（按文件类型自动选分隔符）。

    行为：
        - 跳过以 # 开头的注释行与空行
        - 按扩展名选分隔符（.csv=逗号, .txt=竖线），扩展名无法识别时从首条数据行推断
        - 取首条非注释数据行，校验列数 ≥ required_columns 且前 N 列均非空
        - 不再要求英文列名（兼容中文表头/无表头两种格式）
    返回: (是否有效, 错误信息列表)
    """
    errors = []
    if isinstance(required_columns, int):
        n_required = required_columns
    else:
        try:
            n_required = len(required_columns)
        except TypeError:
            n_required = 0

    try:
        encoding = detect_file_encoding(file_path, ['utf-8', 'gbk', 'gb2312', 'gb18030', 'utf-8-sig'])
        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext == '.csv':
            sep = ','
        elif file_ext == '.txt':
            sep = '|'
        else:
            sep = None

        first_data_line = None
        line_no = 0
        with open(file_path, 'r', encoding=encoding) as f:
            for raw in f:
                line_no += 1
                s = raw.strip()
                if not s or s.startswith('#'):
                    continue
                first_data_line = s
                first_data_line_no = line_no
                break

        if first_data_line is None:
            return False, ["文件为空或全部为注释行，没有可解析的数据"]

        if sep is None:
            if ',' in first_data_line and '|' not in first_data_line:
                sep = ','
            elif '|' in first_data_line and ',' not in first_data_line:
                sep = '|'
            elif first_data_line.count(',') >= first_data_line.count('|'):
                sep = ','
            else:
                sep = '|'

        columns = [c.strip() for c in first_data_line.split(sep)]
        n_cols = len(columns)

        if n_required > 0 and n_cols < n_required:
            errors.append(
                f"首条数据行（第 {first_data_line_no} 行）只有 {n_cols} 列，"
                f"至少需要 {n_required} 列（必需：设备名/IP/设备类型）"
            )
            return False, errors

        if n_required > 0:
            empty_positions = [
                (i + 1) for i in range(min(n_required, n_cols)) if not columns[i]
            ]
            if empty_positions:
                errors.append(
                    f"首条数据行（第 {first_data_line_no} 行）第 "
                    f"{','.join(str(p) for p in empty_positions)} 列为空"
                    "（必需字段不能为空）"
                )

        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"文件读取错误: {e}"]
