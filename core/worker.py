"""巡检 worker 线程。

``ProgressReporter`` 协议消除了 ``hasattr(progress_var, 'set_progress')`` 鸭子类型，
让 ``DetailedProgressbar`` 与 ``IntVar`` 各自实现一致的 ``set_progress(value, text)`` 入口。
"""
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from utils.logging_setup import LOG_QUEUE, log_error, debug_log, format_traceback
from core.inspector import connect_and_execute


class ProgressReporter(ABC):
    """进度上报器协议（ABC 风格）—— worker 唯一依赖的接口。

    实现方可以是：
    - ``DetailedProgressbar``（同时显示数值 + 文本）
    - ``IntVarProgressReporter``（只显示数值，向后兼容）
    - 测试中可以用 mock，不引入 Tk 依赖
    """

    @abstractmethod
    def set_progress(self, value, text=""):
        """value: 0-100 的整数；text: 详细描述，可选"""


class DetailedProgressbarAdapter:
    """包装 DetailedProgressbar（已存在 set_progress）"""

    def __init__(self, bar):
        self._bar = bar

    def set_progress(self, value, text=""):
        self._bar.set_progress(value, text)


class IntVarProgressReporter(ProgressReporter):
    """IntVar 适配器（仅数值，无文本）"""

    def __init__(self, int_var):
        self._var = int_var

    def set_progress(self, value, text=""):
        self._var.set(int(value))


def make_progress_reporter(obj):
    """把任意进度对象规整成 ProgressReporter。

    优先识别已有 ``set_progress`` 方法的对象（兼容 DetailedProgressbar），
    否则尝试 IntVar 接口。
    """
    if obj is None:
        return IntVarProgressReporter(_NullVar())
    if hasattr(obj, 'set_progress') and callable(obj.set_progress):
        # DetailedProgressbar / 我们的 adapter 都满足
        if not isinstance(obj, ProgressReporter):
            return DetailedProgressbarAdapter(obj)
        return obj
    # IntVar 兜底
    return IntVarProgressReporter(obj)


class _NullVar:
    def set(self, _): pass


def inspection_worker(devices, device_types, command_files, encodings, status_var,
                      progress_reporter, inspection_results, stop_event,
                      default_encoding=None, max_workers=5):
    """巡检工作线程 —— 顶层 try/except 兜底，绝不静默死亡。

    参数:
        progress_reporter: ProgressReporter 实例（由 make_progress_reporter 构造）
        stop_event: 必传，停止信号
        default_encoding: UI 下拉框选定的默认编码
    """
    try:
        _run_inspection_worker(devices, device_types, command_files, encodings,
                               status_var, progress_reporter, inspection_results,
                               stop_event, default_encoding, max_workers)
    except Exception as e:
        error_msg = f"巡检线程顶层错误：{e}"
        tb_text = format_traceback()
        try:
            LOG_QUEUE.put(f"[ERROR] {error_msg}")
            LOG_QUEUE.put(tb_text)
        except Exception:
            pass
        try:
            log_error(error_msg)
            log_error(tb_text)
        except Exception:
            pass
        _safe_set_status(status_var, f"巡检出错：{e}")


def _safe_set_status(status_var, text):
    """跨线程更新 status_var 的安全封装。

    背景：worker 跑在工作线程，``status_var.set()`` 落在 Tk StringVar 上时，
    新版 Tcl（Py3.12+ / Tk 8.6.13+）会抛 ``RuntimeError: main thread is not
    in main loop``（历史版本下大多数情况静默成功）。

    这里统一 swallow 掉：worker 不应该因为状态栏字符串没设上而 crash。
    UI 端如果想严格主线程更新，应当走 ``self.root.after(0, lambda: ...)``，
    而不是让 worker 直接调 StringVar。
    """
    try:
        status_var.set(text)
    except Exception:
        pass


def _run_inspection_worker(devices, device_types, command_files, encodings,
                            status_var, progress_reporter, inspection_results,
                            stop_event, default_encoding, max_workers):
    """inspection_worker 的实际实现"""
    if inspection_results is None:
        inspection_results = []

    try:
        selected_devices = [d for d in devices if d.get('selected', True)]
        total_devices = len(selected_devices)

        if total_devices == 0:
            _safe_set_status(status_var, "没有选中任何设备")
            LOG_QUEUE.put("没有选中任何设备进行巡检")
            return

        success_count = 0
        interrupted = False
        lock = threading.Lock()
        actual_max_workers = min(max_workers, len(selected_devices))

        def process_device(device, index):
            """处理单个设备"""
            nonlocal success_count

            result = {
                'device_name': device.get('device_name', ''),
                'ip': device.get('ip', ''),
                'device_type': device.get('device_type', ''),
                'protocol': (device.get('protocol') or device_types.get(device.get('device_type', ''), {}).get('default_protocol', '')),
                'start_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'end_time': '',
                'duration': 0.0,
                'status': 'pending',
                'log_file': '',
                'error': ''
            }

            if stop_event.is_set():
                result['status'] = 'interrupted'
                result['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                with lock:
                    inspection_results.append(result)
                return False

            start_ts = time.time()
            success, log_file, error_msg = connect_and_execute(
                device, device_types, command_files, encodings,
                stop_event=stop_event,
                default_encoding=default_encoding,
            )
            end_ts = time.time()

            result['log_file'] = log_file or ''
            result['duration'] = round(end_ts - start_ts, 2)
            result['end_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            result['error'] = error_msg or ''
            result['status'] = 'success' if success else 'failed'

            with lock:
                inspection_results.append(result)
                if success:
                    success_count += 1
                processed = index + 1
                # status_var.set 在 worker 里直接调是历史遗留 —— Tk StringVar
                # 在多数版本下安全，但新版 Tcl 严格要求主线程（_safe_set_status
                # 已经 swallow，这里仅在 stop_event 未触发时更新，避免与停止
                # 状态互相覆盖）。
                if not stop_event.is_set():
                    _safe_set_status(
                        status_var,
                        f"正在处理 {device['device_name']} ({processed}/{total_devices})",
                    )
                progress_reporter.set_progress(
                    int((processed / total_devices) * 100),
                    f"已完成 {processed}/{total_devices} 台设备"
                )
            return success

        with ThreadPoolExecutor(max_workers=actual_max_workers) as executor:
            futures = []
            for i, device in enumerate(selected_devices):
                if stop_event.is_set():
                    interrupted = True
                    break
                future = executor.submit(process_device, device, i)
                futures.append(future)

            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    log_error(f"任务执行异常：{e}")

        failed_total = total_devices - success_count
        # 总结行：失败=0 走 SUCCESS（绿色），失败>0 走 ERROR（红色）。
        # 不能依赖 _detect_log_level 的关键字启发 —— "失败 0 台" 也含"失败"
        # 会被误判成 ERROR，所以这里显式打 [LEVEL] 前缀。
        summary_level = "ERROR" if failed_total > 0 else "SUCCESS"
        if interrupted or stop_event.is_set():
            _safe_set_status(
                status_var,
                f"巡检已停止：成功{success_count}/{total_devices}台设备",
            )
            LOG_QUEUE.put(
                f"[{summary_level}] 巡检已停止：成功{success_count}台，失败{failed_total}台"
            )
        else:
            _safe_set_status(
                status_var,
                f"巡检完成：共{total_devices}台，成功{success_count}台",
            )
            LOG_QUEUE.put(
                f"[{summary_level}] 巡检完成：成功{success_count}台，失败{failed_total}台"
            )

        progress_reporter.set_progress(
            100 if not interrupted else progress_reporter.get_progress() if hasattr(progress_reporter, 'get_progress') else 0,
            f"巡检完成：{success_count}/{total_devices}台设备"
        )

    except Exception as e:
        error_msg = f"巡检线程错误：{e}"
        LOG_QUEUE.put(error_msg)
        log_error(error_msg)
        _safe_set_status(status_var, f"巡检出错：{e}")
