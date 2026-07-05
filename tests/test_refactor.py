"""密码脱敏与新模块的行为单测。"""
import os
import sys
import unittest
import tempfile
import threading

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from utils.logging_setup import _redact_sensitive
from core.worker import (
    ProgressReporter, DetailedProgressbarAdapter, IntVarProgressReporter,
    make_progress_reporter, _NullVar,
)
from utils.validation import validate_ip, validate_port, sanitize_filename


class TestRedactSensitive(unittest.TestCase):
    """密码 / secret 字段脱敏 —— 防止 log 泄露凭据"""

    def test_json_password(self):
        text = '{"username": "admin", "password": "S3cret!@#", "host": "1.2.3.4"}'
        out = _redact_sensitive(text)
        self.assertNotIn("S3cret", out)
        self.assertIn("***", out)
        # 非敏感字段保持原样
        self.assertIn("admin", out)
        self.assertIn("1.2.3.4", out)

    def test_single_quoted_password(self):
        text = "{'password': 'mypwd', 'ip': '10.0.0.1'}"
        out = _redact_sensitive(text)
        self.assertNotIn("mypwd", out)
        self.assertIn("***", out)

    def test_kv_style_password(self):
        text = "登录信息: username=admin password=HelloWorld123 host=1.2.3.4"
        out = _redact_sensitive(text)
        self.assertNotIn("HelloWorld123", out)
        self.assertIn("password=***", out)
        self.assertIn("admin", out)

    def test_secret_redacted(self):
        text = '{"secret": "EnableP@ss"}'
        out = _redact_sensitive(text)
        self.assertNotIn("EnableP@ss", out)

    def test_chinese_keyword_password(self):
        """Netmiko 异常里常含 password 字样"""
        text = "AuthenticationException: password mismatch for user admin"
        out = _redact_sensitive(text)
        # 这里 "password" 是正文，不是键值对，**不应该**被脱敏（否则日志不可读）
        # 我们的实现只看 kv 形式 / JSON 形式，正文中的 "password" 保留
        self.assertIn("password mismatch", out)
        self.assertIn("admin", out)

    def test_no_password_no_change(self):
        text = "正常日志：设备 sw-01 连接成功"
        self.assertEqual(_redact_sensitive(text), text)

    def test_non_string_passthrough(self):
        # 异常对象不抛
        self.assertIsNone(_redact_sensitive(None))
        self.assertEqual(_redact_sensitive(12345), 12345)


class TestProgressReporter(unittest.TestCase):
    @staticmethod
    def _pump_until(root, predicate, timeout_ms=2000, step_ms=20):
        """pump Tk 事件循环直至 predicate 为真，或超时。

        DetailedProgressbar.set_progress 现在对前进值做 320ms 缓动动画，
        测试需要主动驱动事件循环才能读到动画结束后的值。
        """
        elapsed = 0
        while elapsed < timeout_ms:
            root.update()
            if predicate():
                return True
            elapsed += step_ms
            import time as _t
            _t.sleep(step_ms / 1000.0)
        return False

    def test_make_from_intvar(self):
        """IntVar 应该被适配为 IntVarProgressReporter"""
        import tkinter as tk
        root = tk.Tk()
        try:
            var = tk.IntVar()
            r = make_progress_reporter(var)
            self.assertIsInstance(r, IntVarProgressReporter)
            r.set_progress(42, "doing things")
            self.assertEqual(var.get(), 42)
        finally:
            root.destroy()

    def test_make_from_none(self):
        r = make_progress_reporter(None)
        # 应返回一个 Null 实现（不抛）
        r.set_progress(50, "test")
        # _NullVar.set 是 no-op，不报错即可

    def test_make_from_detailed_progressbar(self):
        import tkinter as tk
        from ui.widgets import DetailedProgressbar
        root = tk.Tk()
        try:
            bar = DetailedProgressbar(root)
            r = make_progress_reporter(bar)
            # 已实现 set_progress 协议的对象应该原样或包装返回
            self.assertTrue(hasattr(r, 'set_progress'))
            r.set_progress(75, "three quarters")
            # DetailedProgressbar 现在对前进值做 320ms 60fps 缓动，
            # 测试需要 pump 事件循环直至动画结束再读最终值
            self._pump_until(root, lambda: bar.get_progress() >= 75.0, timeout_ms=2000)
            self.assertEqual(bar.get_progress(), 75)
        finally:
            root.destroy()

    def test_protocol_is_abstract(self):
        """ProgressReporter 本身不能直接实例化"""
        with self.assertRaises(TypeError):
            ProgressReporter()

    def test_forward_progress_animates_not_snaps(self):
        """前进值 (target > current) 必须经过中间帧，不能瞬时跳到 target"""
        import tkinter as tk
        from ui.widgets import DetailedProgressbar
        root = tk.Tk()
        try:
            bar = DetailedProgressbar(root)
            # 直接调用底层 set_progress，跳过 make_progress_reporter 的 adapter 层
            bar.set_progress(50, "")
            # 立刻（动画还没跑完前）读值，应该 < 50，且 > 0
            root.update()  # 让 _animate_progress_to 起步
            mid = bar.get_progress()
            self.assertGreater(mid, 0, "前进动画起步后应该有中间值")
            self.assertLess(mid, 50, "前进动画起步时不应该瞬时跳到 target")
            # 等动画结束
            self._pump_until(root, lambda: bar._progress_tween is None, timeout_ms=2000)
            self.assertEqual(bar.get_progress(), 50)
        finally:
            root.destroy()

    def test_backward_progress_snaps_no_animation(self):
        """后退值 (target < current) 应该直接 snap，不应该回弹动画"""
        import tkinter as tk
        from ui.widgets import DetailedProgressbar
        root = tk.Tk()
        try:
            bar = DetailedProgressbar(root)
            bar.set_progress(80, "")      # 前进到 80
            self._pump_until(root, lambda: bar.get_progress() >= 80.0, timeout_ms=2000)
            # 后退到 30 —— 必须立即 snap，不应该有 tween 在飞
            bar.set_progress(30, "")
            self.assertIsNone(bar._progress_tween,
                              "后退时不应该启动 tween 动画")
            self.assertEqual(bar.get_progress(), 30)
        finally:
            root.destroy()

    def test_small_delta_snaps(self):
        """|delta| < 0.5 时直接 snap，避免 1 帧抖动"""
        import tkinter as tk
        from ui.widgets import DetailedProgressbar
        root = tk.Tk()
        try:
            bar = DetailedProgressbar(root)
            bar.set_progress(50.0, "")
            self._pump_until(root, lambda: bar.get_progress() >= 50.0, timeout_ms=2000)
            # 设一个非常接近的值（差 0.2），应该立即 snap
            bar.set_progress(50.2, "")
            self.assertIsNone(bar._progress_tween)
            self.assertAlmostEqual(bar.get_progress(), 50.2, places=5)
        finally:
            root.destroy()


class TestValidationUtils(unittest.TestCase):
    def test_validate_ip(self):
        self.assertTrue(validate_ip('192.168.1.1'))
        self.assertTrue(validate_ip('::1'))
        self.assertFalse(validate_ip('256.1.1.1'))
        self.assertFalse(validate_ip('not-an-ip'))
        self.assertFalse(validate_ip(None))

    def test_validate_port(self):
        self.assertTrue(validate_port(1))
        self.assertTrue(validate_port(65535))
        self.assertFalse(validate_port(0))
        self.assertFalse(validate_port(65536))
        self.assertFalse(validate_port('abc'))

    def test_sanitize_filename_chinese_preserved(self):
        # 中文字符不应该被清洗
        result = sanitize_filename('浪潮-cisco-sw-01')
        self.assertEqual(result, '浪潮-cisco-sw-01')

    def test_sanitize_filename_windows_illegal(self):
        result = sanitize_filename('a<b>c:d"e/f\\g|h?i*j')
        self.assertEqual(result, 'a_b_c_d_e_f_g_h_i_j')


class TestSendCommandInterruptible(unittest.TestCase):
    """_send_command_interruptible 必须真的能被 stop_event 中断，
    否则用户点停止后会卡 60-180s 等 send_command 超时"""

    def test_returns_quickly_when_stop_set_during_send(self):
        """send_command 模拟长耗时（5s），中途 set stop_event，
        包装函数必须在 < 1s 内返回，而不是等满 5s"""
        import threading
        import time
        from core.inspector import _send_command_interruptible

        stop_event = threading.Event()

        class FakeConn:
            def __init__(self):
                self.disconnect_called = False
            def send_command(self, command, read_timeout=60):
                # 模拟一个慢命令：5s 后才返回
                # 期间 disconnect() 被调用时必须立刻抛异常
                start = time.time()
                while time.time() - start < 5.0:
                    if self.disconnect_called:
                        raise ConnectionResetError("socket closed by peer")
                    time.sleep(0.05)
                return "should not reach"
            def disconnect(self):
                self.disconnect_called = True

        fake = FakeConn()
        # 在 200ms 后 set stop，模拟"用户中途点停止"
        def stopper():
            time.sleep(0.2)
            stop_event.set()
        threading.Thread(target=stopper, daemon=True).start()

        t0 = time.time()
        output, err = _send_command_interruptible(
            fake, "show version", read_timeout=60, stop_event=stop_event
        )
        elapsed = time.time() - t0

        # 必须在 1s 内返回（包装层 100ms poll + disconnect + 线程 join）
        self.assertLess(elapsed, 1.0,
                        f"应该立刻响应 stop，但等了 {elapsed:.2f}s")
        self.assertIsNone(output)
        self.assertEqual(err, "用户中断")
        self.assertTrue(fake.disconnect_called,
                        "stop 时必须调 disconnect 强制关闭 socket")

    def test_normal_completion_returns_output(self):
        """没设 stop_event 时，包装函数应该正常返回 send_command 的输出"""
        from core.inspector import _send_command_interruptible

        class FakeConn:
            disconnect_called = False
            def send_command(self, command, read_timeout=60):
                return f"OK: {command}"
            def disconnect(self):
                self.disconnect_called = True

        stop_event = threading.Event()
        output, err = _send_command_interruptible(
            FakeConn(), "show ip", read_timeout=60, stop_event=stop_event
        )
        self.assertEqual(output, "OK: show ip")
        self.assertIsNone(err)

    def test_already_stopped_returns_immediately(self):
        """stop_event 提前已 set，包装函数应该立即返回，不调 send_command"""
        from core.inspector import _send_command_interruptible

        class FakeConn:
            def send_command(self, command, read_timeout=60):
                raise AssertionError("不应被调用，stop_event 已 set")
            def disconnect(self):
                pass

        stop_event = threading.Event()
        stop_event.set()
        output, err = _send_command_interruptible(
            FakeConn(), "show ip", read_timeout=60, stop_event=stop_event
        )
        self.assertIsNone(output)
        self.assertEqual(err, "用户中断")


if __name__ == '__main__':
    unittest.main(verbosity=2)
