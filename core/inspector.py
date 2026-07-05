"""Netmiko 设备连接与命令执行。

``connect_and_execute`` 和 ``connect_with_retry`` 接收 ``stop_event`` 作为参数，
不再依赖模块全局（v2.1 之前用 ``global stop_event`` 串扰连通性测试与主巡检）。

所有阻塞 IO 都用 ``_run_on_conn_interruptible`` 包一层 daemon 线程，stop_event
一 set 就 disconnect 关 socket 让阻塞 IO 立即返回。覆盖：
- ConnectHandler 初始 SSH 握手
- send_command / enable / disable_paging 等基于 socket 的命令
- 死连接上 disconnect 自身 TCP 关闭可能挂 OS 超时，用 ``_disconnect_fast``
  限制到 0.3s 内返回

目标：用户点击停止后，最多 100-300ms 内 worker 全部返回。
"""
import os
import threading
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


def _interruptible_sleep(seconds, stop_event, granularity=0.1):
    """time.sleep 的可中断版本 —— 用户点停止时立刻退出，不再干等。

    返回 True = 睡够了；False = 中途被打断。
    """
    if stop_event is None:
        time.sleep(seconds)
        return True
    elapsed = 0.0
    while elapsed < seconds:
        if stop_event.is_set():
            return False
        time.sleep(min(granularity, seconds - elapsed))
        elapsed += granularity
    return True


def _disconnect_fast(net_connect, timeout=0.3):
    """让 net_connect.disconnect() 不阻塞主流程。

    死连接上的 TCP 关闭可能挂 OS 超时（数十秒），不能让用户等这个。
    在 daemon 线程里跑 disconnect，最多等 timeout 秒就让线程自生自灭。
    """
    if net_connect is None:
        return

    def _runner():
        try:
            net_connect.disconnect()
        except Exception:
            pass

    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    t.join(timeout=timeout)


def _run_on_conn_interruptible(net_connect, func, stop_event, label="op",
                                join_after_disconnect=0.2):
    """通用包装：把任意基于 net_connect 的阻塞调用变得可中断。

    工作流：
    1. daemon 线程里跑 func(net_connect)
    2. 主线程 poll stop_event（默认 100ms 一次）
    3. stop_event 一 set → 调 net_connect.disconnect() 关 socket，
       func 的阻塞 recv() 立刻失败 → runner 线程结束
    4. 最多再等 join_after_disconnect 秒让 runner 收尾，超时就返回

    返回 (result_value, error_msg)：
    - 正常完成   → (func 返回值, None)
    - 用户中断   → (None, "用户中断")
    - 调用异常   → (None, str(exception))
    """
    if stop_event is not None and stop_event.is_set():
        return None, "用户中断"

    state = {"value": None, "error": None, "done": False}

    def _runner():
        try:
            state["value"] = func()
        except Exception as e:
            state["error"] = e
        finally:
            state["done"] = True

    runner = threading.Thread(target=_runner, daemon=True, name=f"netmiko-{label}")
    runner.start()

    while not state["done"]:
        if stop_event is not None and stop_event.is_set():
            # 关 socket 强制让阻塞 IO 失败；超时封顶避免死连接拖死主线程
            _disconnect_fast(net_connect, timeout=0.3)
            runner.join(timeout=join_after_disconnect)
            return None, "用户中断"
        runner.join(timeout=0.1)

    if state["error"] is not None:
        return None, str(state["error"])
    return state["value"], None


def _send_command_interruptible(net_connect, command, read_timeout, stop_event):
    """让 Netmiko 的 ``send_command`` 真正能被 stop_event 中断。

    委托给 ``_run_on_conn_interruptible``，保持外部接口不变（返回 (output, err)）。
    """
    def _call():
        return net_connect.send_command(command, read_timeout=read_timeout)
    return _run_on_conn_interruptible(net_connect, _call, stop_event,
                                       label="send_command")


def _enable_interruptible(net_connect, stop_event):
    """让 ``net_connect.enable()`` 也可中断（之前是裸调，最坏可卡 10s+）"""
    def _call():
        return net_connect.enable()
    return _run_on_conn_interruptible(net_connect, _call, stop_event,
                                       label="enable")


def connect_with_retry(device_info, stop_event=None, max_retries=2, retry_delay=2):
    """带重试机制的 Netmiko 连接。

    ``stop_event`` 可选：传入后用户停止时不再 sleep 重试间隔。
    返回 Connection 或 None。
    """

    for attempt in range(max_retries + 1):
        if stop_event is not None and stop_event.is_set():
            LOG_QUEUE.put("用户已停止，取消连接重试")
            return None
        # ConnectHandler 是初始 SSH 握手（可能阻塞数十秒），用 daemon 线程包一层
        conn, err = _connect_handler_interruptible(device_info, stop_event)
        if err == "用户中断":
            LOG_QUEUE.put("用户已停止，取消连接")
            return None
        if err is not None:
            # err 是 (exc_instance, str_repr) —— 用类型分发，不靠字符串匹配
            exc, _msg = err
            if isinstance(exc, NetMikoTimeoutException):
                if attempt < max_retries:
                    LOG_QUEUE.put(f"连接超时，{retry_delay}秒后重试 ({attempt + 1}/{max_retries})")
                    if stop_event is not None and not _interruptible_sleep(retry_delay, stop_event):
                        LOG_QUEUE.put("用户已停止，取消连接重试")
                        return None
                else:
                    LOG_QUEUE.put("连接设备失败，已达最大重试次数")
            elif isinstance(exc, NetMikoAuthenticationException):
                LOG_QUEUE.put("认证失败，请检查用户名和密码")
                return None  # 认证失败通常不重试
            else:
                if attempt < max_retries:
                    LOG_QUEUE.put(f"连接异常，{retry_delay}秒后重试: {_msg}")
                    if stop_event is not None and not _interruptible_sleep(retry_delay, stop_event):
                        LOG_QUEUE.put("用户已停止，取消连接重试")
                        return None
                else:
                    LOG_QUEUE.put(f"连接设备失败: {_msg}")
            continue
        return conn


def _connect_handler_interruptible(device_info, stop_event):
    """包 ``ConnectHandler(**device_info)``，让它响应 stop_event。

    ConnectHandler 是初始 SSH 握手，没有连接可关。stop 一 set 立刻返回，
    runner 线程会自然超时（device_info['timeout'] 秒），由 daemon GC 兜底。

    返回 (conn, error)：
    - 正常       → (ConnectHandler 实例, None)
    - 用户中断   → (None, "用户中断")
    - 异常       → (None, (exc_instance, str_repr))  ← 用 isinstance 分发
    """
    if stop_event is not None and stop_event.is_set():
        return None, "用户中断"

    state = {"conn": None, "error": None, "done": False}

    def _runner():
        try:
            state["conn"] = ConnectHandler(**device_info)
        except Exception as e:
            state["error"] = e
        finally:
            state["done"] = True

    runner = threading.Thread(target=_runner, daemon=True, name="netmiko-connect")
    runner.start()

    while not state["done"]:
        if stop_event is not None and stop_event.is_set():
            # 没有连接可关；只多等 100ms 让 runner 自检一次
            runner.join(timeout=0.1)
            if state["done"]:
                if state["error"] is not None:
                    return None, (state["error"], str(state["error"]))
                return state["conn"], None
            return None, "用户中断"
        runner.join(timeout=0.1)

    if state["error"] is not None:
        return None, (state["error"], str(state["error"]))
    return state["conn"], None


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
            # time.sleep 换成可中断版本 —— 用户点停止立即退出，不再干等 2s
            if not _interruptible_sleep(2, stop_event):
                f.write("巡检被用户终止\n")
                return False, log_file, "用户中断"

            if device_config['enable_mode']:
                # enable() 也是阻塞 socket IO，单独包一层
                _, enable_err = _enable_interruptible(net_connect, stop_event)
                if enable_err == "用户中断":
                    f.write("巡检被用户终止\n")
                    return False, log_file, "用户中断"
                if enable_err is not None:
                    debug_log(f"进入特权模式失败：{enable_err}")

            disable_paging_cmd = device_config['disable_paging_cmd']
            if disable_paging_cmd and disable_paging_cmd.strip():
                # 用可中断包装：用户点击停止时立即放弃，不要等 30s read_timeout
                paging_output, paging_err = _send_command_interruptible(
                    net_connect, disable_paging_cmd, read_timeout=30, stop_event=stop_event
                )
                if paging_err == "用户中断":
                    f.write("巡检被用户终止\n")
                    return False, log_file, "用户中断"
                if paging_err is not None:
                    warn_msg = f"禁用分页失败({device['device_name']})：{paging_err}，后续命令输出可能被截断"
                    debug_log(warn_msg)
                    LOG_QUEUE.put(f"[WARNING] {warn_msg}")
                else:
                    # 顺手做一次编码自检
                    check_encoding_match(paging_output, device['device_name'], effective_encoding)

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

                    # 可中断包装：用户点击停止时立即放弃，不再干等 read_timeout
                    output, cmd_err = _send_command_interruptible(
                        net_connect, command, read_timeout=cmd_timeout, stop_event=stop_event
                    )

                    if cmd_err == "用户中断":
                        f.write("巡检被用户终止\n")
                        return False, log_file, "用户中断"

                    try:
                        if cmd_err is not None:
                            raise Exception(cmd_err)

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
            # 死连接上 disconnect 可能挂 OS TCP 超时，用 _disconnect_fast 封顶 0.3s
            _disconnect_fast(net_connect, timeout=0.3)

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
