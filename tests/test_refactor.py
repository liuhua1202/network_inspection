"""密码脱敏与新模块的行为单测。"""
import os
import sys
import unittest
import tempfile

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
            self.assertEqual(bar.get_progress(), 75)
        finally:
            root.destroy()

    def test_protocol_is_abstract(self):
        """ProgressReporter 本身不能直接实例化"""
        with self.assertRaises(TypeError):
            ProgressReporter()


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
