"""Netmiko 设备连接与命令执行。

``connect_and_execute`` 和 ``connect_with_retry`` 接收 ``stop_event`` 作为参数，
不再依赖模块全局（v2.1 之前用 ``global stop_event`` 串扰连通性测试与主巡检）。
"""
import os
import time
from datetime import datetime

try:
    from netmiko import ConnectHandler, NetMikoAuthenticationException, NetMikoTimeoutException
    NETMIKO_AVAILABLE = True
    missing_netmiko_message = ''
except ImportError as e:
    ConnectHandler = None
    NetMikoAuthenticationException = Exception
    NetMikoTimeoutException = Exception
    NETMIKO_AVAILABLE = False
    missing_netmiko_message = str(e)

from utils.logging_setup import LOG_QUEUE, log_info, log_error, debug_log
from utils.paths import project_log_root
from utils.validation import sanitize_filename
from core.encoding import resolve_effective_encoding, check_encoding_match


def connect_with_retry(device_info, stop_event=None, max_retries=2, retry_delay=2):
    """带重试机制的 Netmiko 连接。

    ``stop_event`` 可选：传入后用户停止时不再 sleep 重试间隔。
    返回 Connection 或 None。
    """
    if not NETMIKO_AVAILABLE:
        LOG_QUEUE.put("netmiko 库未安装，无法建立设备连接")
        return None

    for attempt in range(max_retries + 1):
        if stop_event is not None and stop_event.is_set():
            LOG_QUEUE.put("用户已停止，取消连接重试")
            return None
        try:
            return ConnectHandler(**device_info)
        except NetMikoTimeoutException:
            if attempt < max_retries:
                LOG_QUEUE.put(f"连接超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                if stop_event is not None:
                    # sleep 期间也要响应 stop；分小段 sleep 便于快速退出
                    slept = 0.0
                    while slept < retry_delay and not stop_event.is_set():
                        time.sleep(0.2)
                        slept += 0.2
                else:
                    time.sleep(retry_delay)
            else:
                LOG_QUEUE.put("连接设备失败，已达最大重试次数")
        except NetMikoAuthenticationException:
            LOG_QUEUE.put("认证失败，请检查用户名和密码")
            break  # 认证失败通常不重试
        except Exception as e:
            if attempt < max_retries:
                LOG_QUEUE.put(f"连接异常，{retry_delay}秒后重试: {e}")
                if stop_event is not None:
                    slept = 0.0
                    while slept < retry_delay and not stop_event.is_set():
                        time.sleep(0.2)
                        slept += 0.2
                else:
                    time.sleep(retry_delay)
            else:
                LOG_QUEUE.put(f"连接设备失败: {e}")
    return None


def connect_and_execute(device, device_types, command_files, encodings,
                        stop_event, default_encoding=None):
    """连接设备并执行命令。

    参数:
        encodings: 备用编码列表，用于 Netmiko 返回 bytes 时的 fallback 解码
        default_encoding: UI 下拉框选定的默认编码（如 'gbk' / 'utf-8'）；为 None 时取 'gbk'
        stop_event: 线程安全的停止信号（必传，不再用全局）
    返回: (success: bool, log_file: str|None, error_msg: str)
    """
    if stop_event is not None and stop_event.is_set():
        return False, None, "用户已停止巡检"

    try:
        device_type_id = device['device_type']
        if device_type_id not in device_types:
            error_msg = f"设备 {device['device_name']} 的类型 {device_type_id} 未定义"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False, None, error_msg

        device_config = device_types[device_type_id]

        if device_type_id not in command_files or not command_files[device_type_id][1]:
            error_msg = f"设备 {device['device_name']} 没有配置巡检命令"
            LOG_QUEUE.put(error_msg)
            debug_log(error_msg)
            return False, None, error_msg

        commands = command_files[device_type_id][1]

        protocol = device.get('protocol') or device_config['default_protocol']
        if protocol not in ('ssh', 'telnet'):
            protocol = device_config['default_protocol']

        device_driver = device_config['netmiko_type'][protocol]

        effective_encoding = resolve_effective_encoding(device, device_config, default_encoding)
        LOG_QUEUE.put(f"[INFO] {device['device_name']} 使用编码：{effective_encoding}")
        debug_log(f"{device['device_name']} effective encoding = {effective_encoding}")

        device_info = {
            'device_type': device_driver,
            'ip': device['ip'],
            'port': device['port'],
            'timeout': 60,
            'global_delay_factor': 2,
            'read_timeout_override': 120,
            'encoding': effective_encoding,
        }

        if device.get('username', '').strip():
            device_info['username'] = device['username']
        if device.get('password', '').strip():
            device_info['password'] = device['password']
        if device.get('secret', '').strip():
            device_info['secret'] = device['secret']

        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        log_dir = os.path.join(project_log_root(), datetime.now().strftime("%Y_%m_%d"))
        os.makedirs(log_dir, exist_ok=True)
        safe_name = sanitize_filename(device['device_name']) or 'device'
        safe_ip = sanitize_filename(device['ip']).replace(':', '_')
        log_file = os.path.join(log_dir, f"{safe_name}_{safe_ip}_{timestamp}.txt")

        msg = f"开始处理 {device_config['name']}: {device['device_name']} ({device['ip']})"
        LOG_QUEUE.put(msg)
        log_info(msg)

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"设备名称：{device['device_name']}\n")
            f.write(f"IP 地址：{device['ip']}\n")
            f.write(f"设备类型：{device_config['name']}\n")
            f.write(f"连接协议：{protocol.upper()}\n")
            f.write(f"处理时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"执行命令数：{len(commands)}\n")
            f.write("=" * 50 + "\n\n")

        net_connect = connect_with_retry(device_info, stop_event=stop_event,
                                         max_retries=2, retry_delay=2)
        if net_connect is None:
            error_msg = f"无法连接到设备 {device['device_name']} ({device['ip']})"
            LOG_QUEUE.put(error_msg)
            return False, None, error_msg

        try:
            time.sleep(2)

            if device_config['enable_mode']:
                try:
                    net_connect.enable()
                except Exception as enable_error:
                    debug_log(f"进入特权模式失败：{enable_error}")

            disable_paging_cmd = device_config['disable_paging_cmd']
            if disable_paging_cmd and disable_paging_cmd.strip():
                try:
                    paging_output = net_connect.send_command(disable_paging_cmd, read_timeout=30)
                    # 顺手做一次编码自检
                    check_encoding_match(paging_output, device['device_name'], effective_encoding)
                except Exception as paging_error:
                    warn_msg = f"禁用分页失败({device['device_name']})：{paging_error}，后续命令输出可能被截断"
                    debug_log(warn_msg)
                    LOG_QUEUE.put(f"[WARNING] {warn_msg}")

            with open(log_file, 'a', encoding='utf-8') as f:
                for cmd_tuple in commands:
                    # parse_commands_file 统一返回三元组 (cmd, is_heavy, timeout_override)
                    command, is_heavy, timeout_override = cmd_tuple

                    if stop_event is not None and stop_event.is_set():
                        f.write("巡检被用户终止\n")
                        return False, log_file, "用户中断"

                    # 单条命令超时：显式覆盖 > heavy 默认 180s > 普通 60s
                    if timeout_override is not None and timeout_override > 0:
                        cmd_timeout = timeout_override
                    elif is_heavy:
                        cmd_timeout = 180
                    else:
                        cmd_timeout = 60

                    tag = "[HEAVY]" if is_heavy else "[CMD]"
                    f.write(f"{tag} 执行命令({cmd_timeout}s)：{command}\n")
                    f.write("-" * 50 + "\n")

                    try:
                        output = net_connect.send_command(command, read_timeout=cmd_timeout)

                        # 编码兜底：理论上 Netmiko 已按 encoding 解码成 str；
                        # 这里兜底处理偶发的 bytes 返回
                        if isinstance(output, bytes):
                            decode_order = [effective_encoding] + [e for e in encodings if e != effective_encoding]
                            for enc in decode_order:
                                try:
                                    output = output.decode(enc)
                                    break
                                except Exception:
                                    continue

                        # 编码自检：每条命令输出都查一次替换字符
                        check_encoding_match(output, device['device_name'],
                                             effective_encoding, threshold=2)

                        f.write(output + "\n\n")
                    except UnicodeDecodeError as ude:
                        hint = (f"命令执行失败：编码错误（{ude}）。"
                                f"当前编码 '{effective_encoding}' 不匹配设备输出。"
                                f"请在 devices.csv 第 9 列调整编码（utf-8/gbk/gb2312）。")
                        f.write(hint + "\n\n")
                        LOG_QUEUE.put(f"[ERROR] {device['device_name']} {hint}")
                    except Exception as cmd_error:
                        f.write(f"命令执行失败({cmd_timeout}s 超时或异常)：{cmd_error}\n\n")

        finally:
            try:
                net_connect.disconnect()
            except Exception:
                pass  # 断开失败不影响主流程

        msg = f"{device_config['name']} {device['device_name']} 处理完成"
        LOG_QUEUE.put(msg)
        log_info(msg)
        return True, log_file, ""

    except (NetMikoAuthenticationException, NetMikoTimeoutException) as e:
        error_msg = f"设备 {device['device_name']} 连接异常：{e}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        return False, None, error_msg
    except Exception as e:
        error_msg = f"设备 {device['device_name']} 处理失败：{e}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        return False, None, error_msg
