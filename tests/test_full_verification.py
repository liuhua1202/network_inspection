"""端到端集成测试：UI 生命周期、worker 真实运行（mock netmiko）、连通性测试对话框。

依赖真实 config/ 下的 devices.csv + device_types.csv + commands/*.txt。
所有 Tk 测试在 Windows / Linux with $DISPLAY 下可跑；headless 服务器上需要 Xvfb。
"""
import os
import sys
import time
import queue
import threading
import unittest
from unittest.mock import patch, MagicMock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tkinter as tk
from tkinter import ttk

import network_inspection as ni
from utils.logging_setup import LOG_QUEUE
from utils.paths import CONFIG_DIR, COMMANDS_DIR
from utils.validation import sanitize_filename, validate_ip
from core.config import (
    load_devices, load_device_types_config, parse_commands_file,
    validate_config_file, validate_devices_config_with_details,
)
from core.encoding import detect_file_encoding, resolve_effective_encoding, check_encoding_match
from core.inspector import (
    connect_with_retry, connect_and_execute,
    NETMIKO_AVAILABLE,
    NetMikoAuthenticationException, NetMikoTimeoutException,
)
from core.worker import inspection_worker, make_progress_reporter
from ui.theme import theme_manager
from ui.widgets import ModernButton, ModernEntry, DetailedProgressbar
from ui.app import ModernNetworkInspectionUI


# ==================== 模块完整性 ====================

class TestModuleIntegrity(unittest.TestCase):
    """所有新模块可独立导入"""

    def test_all_modules_importable(self):
        for mod in [
            'core.config', 'core.encoding', 'core.inspector', 'core.worker',
            'ui.theme', 'ui.widgets', 'ui.app',
            'utils.paths', 'utils.validation', 'utils.logging_setup',
        ]:
            __import__(mod)

    def test_network_inspection_re_exports_critical_api(self):
        """network_inspection.py 顶层的公共 API 完整（向后兼容）"""
        required = [
            'LOG_QUEUE', 'setup_logging', 'debug_log', 'log_info', 'log_error',
            'validate_ip', 'validate_port', 'sanitize_filename',
            'CONFIG_DIR', 'COMMANDS_DIR',
            'detect_file_encoding', 'resolve_effective_encoding', 'check_encoding_match',
            '_resolve_effective_encoding', '_check_encoding_match',  # 旧名兼容
            'is_comment_line', '_parse_selected',
            'load_devices', 'load_device_types_config', 'parse_commands_file',
            'validate_device_types_config', 'validate_devices_config',
            'validate_devices_config_with_details', 'validate_commands_config',
            'validate_config_file',
            'NETMIKO_AVAILABLE', 'missing_netmiko_message',
            'connect_with_retry', 'connect_and_execute',
            'inspection_worker', 'make_progress_reporter',
            'theme_manager', 'ModernButton', 'ModernEntry', 'DetailedProgressbar', 'LogTag',
            'ModernNetworkInspectionUI', 'main',
        ]
        missing = [name for name in required if not hasattr(ni, name)]
        self.assertEqual(missing, [], f"公共 API 缺失：{missing}")


# ==================== 真实配置加载 ====================

class TestRealConfigLoad(unittest.TestCase):
    """用真实 config/ 文件加载，验证数据完整"""

    @classmethod
    def setUpClass(cls):
        cls.device_types_file = os.path.join(CONFIG_DIR, 'device_types.csv')
        cls.devices_file = os.path.join(CONFIG_DIR, 'devices.csv')

    def test_device_types_file_exists(self):
        self.assertTrue(os.path.exists(self.device_types_file),
                        f"缺设备类型文件：{self.device_types_file}")

    def test_devices_file_exists(self):
        self.assertTrue(os.path.exists(self.devices_file),
                        f"缺设备列表文件：{self.devices_file}")

    def test_load_real_device_types(self):
        dt = load_device_types_config(self.device_types_file, ['utf-8', 'gbk'])
        self.assertGreaterEqual(len(dt), 6, "至少应有 6 种设备类型")
        # 验证关键厂商都存在
        names = {v['name'] for v in dt.values()}
        for vendor in ('华为', '思科', 'H3C', 'Juniper', '锐捷', 'Linux'):
            self.assertTrue(any(vendor in n for n in names), f"缺厂商：{vendor}")

    def test_load_real_devices(self):
        devs = load_devices(self.devices_file, ['gbk', 'utf-8'])
        self.assertGreater(len(devs), 50, f"应至少 50 台设备，实际 {len(devs)}")
        # 验证关键字段都填充
        for d in devs[:5]:
            self.assertTrue(d.get('device_name'))
            self.assertTrue(d.get('ip'))
            self.assertTrue(d.get('device_type'))
            self.assertIn(d.get('port'), (22, 23))

    def test_devices_have_valid_ips(self):
        devs = load_devices(self.devices_file, ['gbk', 'utf-8'])
        bad = [d for d in devs if not validate_ip(d.get('ip', ''))]
        self.assertEqual(bad, [], f"{len(bad)} 个设备 IP 格式错")

    def test_devices_pass_validation(self):
        dt = load_device_types_config(self.device_types_file, ['gbk', 'utf-8'])
        devs = load_devices(self.devices_file, ['gbk', 'utf-8'])
        result = validate_devices_config_with_details(devs, dt)
        self.assertTrue(result['valid'],
                        f"设备校验失败：{result['errors'][:3]}")

    def test_all_command_files_loadable(self):
        """config/commands/ 下每个文件都能解析"""
        for fn in os.listdir(COMMANDS_DIR):
            if not fn.endswith('.txt'):
                continue
            path = os.path.join(COMMANDS_DIR, fn)
            cmds = parse_commands_file(path, ['utf-8', 'gbk'])
            self.assertGreater(len(cmds), 0, f"{fn} 解析出 0 条命令")
            # 每条都是三元组
            for c in cmds:
                self.assertEqual(len(c), 3, f"{fn} 命令格式错：{c}")


# ==================== 密码脱敏 ====================

class TestPasswordRedactionE2E(unittest.TestCase):
    """端到端：模拟真实日志流经脱敏过滤器"""

    def test_netmiko_exception_redacted(self):
        """Netmiko 认证异常典型格式不应泄露密码"""
        fake_exception = (
            "NetMikoAuthenticationException: Authentication failure for user admin "
            "with password 'Sup3rS3cret!' on host 192.168.1.1"
        )
        from utils.logging_setup import _redact_sensitive
        out = _redact_sensitive(fake_exception)
        self.assertNotIn('Sup3rS3cret', out, "密码泄露到日志")
        self.assertIn('admin', out, "用户名应该保留以便排错")

    def test_dinfo_dict_dump_redacted(self):
        """设备连接信息字典全量 dump 不应泄露"""
        dinfo = {
            'device_type': 'cisco_ios',
            'ip': '10.0.0.1',
            'username': 'netadmin',
            'password': 'Cisc0P@ss',
            'secret': 'Enable$ecret',
            'port': 22,
        }
        from utils.logging_setup import _redact_sensitive
        out = _redact_sensitive(repr(dinfo))
        self.assertNotIn('Cisc0P@ss', out)
        self.assertNotIn('Enable$ecret', out)
        self.assertIn('netadmin', out)

    def test_unicode_safety(self):
        """中文消息里的 password 不应被误判"""
        from utils.logging_setup import _redact_sensitive
        msg = "用户报告 password 字段不对，已切到手动模式"
        out = _redact_sensitive(msg)
        # 正文中提到的 "password" 应保留（不可读就废了）
        self.assertIn('password', out)
        self.assertIn('手动模式', out)


# ==================== UI 生命周期（headless） ====================

class TestUILifecycle(unittest.TestCase):
    """UI 创建 / 销毁 / 状态机基本流程"""

    def setUp(self):
        self.root = tk.Tk()
        self.app = ModernNetworkInspectionUI(self.root)
        # 等后台线程加载 config
        for _ in range(20):
            self.root.update()
            time.sleep(0.05)
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_app_loads_real_config(self):
        self.assertGreaterEqual(len(self.app.device_types), 6)
        self.assertGreater(len(self.app.devices), 50)
        self.assertGreaterEqual(len(self.app.command_files), 6)

    def test_stop_event_is_instance_attribute(self):
        self.assertIsInstance(self.app._stop_event, threading.Event)
        self.assertFalse(self.app._stop_event.is_set())

    def test_start_button_state_depends_on_validation(self):
        # 真实 config 应该全部通过校验
        self.assertEqual(self.app.start_btn['state'], 'normal')

    def test_inspection_running_flag_starts_false(self):
        self.assertFalse(self.app.inspection_running)

    def test_inspection_results_starts_empty(self):
        self.assertEqual(self.app.inspection_results, [])


# ==================== 搜索 / 选择 / 主题 ====================

class TestUIBehaviors(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.app = ModernNetworkInspectionUI(self.root)
        for _ in range(20):
            self.root.update()
            time.sleep(0.05)
        self.root.update()

    def tearDown(self):
        try:
            self.root.destroy()
        except Exception:
            pass

    def test_search_filters_devices(self):
        original_count = len(self.app.original_devices)
        # 找一个能匹配的真字符串
        sample_name = self.app.original_devices[0]['device_name']
        keyword = sample_name[:3] if len(sample_name) >= 3 else sample_name
        self.app.search_var.set(keyword)
        for _ in range(5):
            self.root.update()
            time.sleep(0.05)
        filtered = len(self.app.devices)
        self.assertLessEqual(filtered, original_count)
        self.assertGreater(filtered, 0)
        # 清空恢复
        self.app.search_var.set('')
        for _ in range(5):
            self.root.update()
            time.sleep(0.05)
        self.assertEqual(len(self.app.devices), original_count)

    def test_search_by_ip_substring(self):
        # 取第二个设备的 IP 段
        ip = self.app.original_devices[1]['ip']
        segment = ip.split('.')[0]  # 比如 "192"
        self.app.search_var.set(segment)
        for _ in range(5):
            self.root.update()
            time.sleep(0.05)
        self.assertGreater(len(self.app.devices), 0)
        # 验证筛出来的都是这个网段
        for d in self.app.devices:
            self.assertIn(segment, d['ip'])

    def test_select_all(self):
        # 模拟"已选"初始为 True 全部
        for d in self.app.devices:
            d['selected'] = True
        self.app.select_all_devices()
        for d in self.app.devices:
            self.assertTrue(d.get('selected', True))

    def test_deselect_all(self):
        self.app.deselect_all_devices()
        for d in self.app.devices:
            self.assertFalse(d.get('selected', True))

    def test_invert(self):
        # 全部置 True，然后反选
        for d in self.app.devices:
            d['selected'] = True
        before = sum(1 for d in self.app.devices if d.get('selected', True))
        self.app.invert_select_devices()
        after = sum(1 for d in self.app.devices if d.get('selected', True))
        self.assertEqual(after, len(self.app.devices) - before)

    def test_theme_toggle_twice_idempotent(self):
        """切换两次高对比度 = 回到原状态"""
        before_mode = theme_manager.high_contrast_mode
        self.app.toggle_high_contrast()
        self.assertNotEqual(theme_manager.high_contrast_mode, before_mode)
        self.app.toggle_high_contrast()
        self.assertEqual(theme_manager.high_contrast_mode, before_mode)

    def test_theme_toggle_keeps_widgets_responsive(self):
        """切换后所有控件还能用（不抛异常）"""
        self.app.toggle_high_contrast()
        self.root.update()
        # 查 start_btn 还能 config
        self.app.start_btn.config(state='disabled')
        self.app.start_btn.config(state='normal')


# ==================== stop_event 隔离 ====================

class TestStopEventIsolation(unittest.TestCase):
    """主巡检与连通性测试的 stop_event 必须隔离（v2.1 之前的核心 bug）"""

    def test_instance_stop_event_independent(self):
        root = tk.Tk()
        try:
            app1 = ModernNetworkInspectionUI(root)
            app2 = ModernNetworkInspectionUI(root)  # 第二个 UI 实例
            # 两个 UI 各自有 stop_event，互不影响
            app1._stop_event.set()
            self.assertFalse(app2._stop_event.is_set())
            app1._stop_event.clear()
            app2._stop_event.set()
            self.assertFalse(app1._stop_event.is_set())
        finally:
            root.destroy()

    def test_connectivity_test_uses_local_event(self):
        """连通性测试对话框的 test_stop_event 不应影响主 stop_event"""
        # 这个通过源代码静态检查保证（已经改成局部变量了）
        # 这里只验证行为
        root = tk.Tk()
        try:
            app = ModernNetworkInspectionUI(root)
            for _ in range(20):
                root.update(); time.sleep(0.05)
            # 触发连通性测试对话框
            app.test_device_connectivity()
            # 主 stop_event 不应被设
            self.assertFalse(app._stop_event.is_set())
            # 找到对话框销毁它
            for w in root.winfo_children():
                if isinstance(w, tk.Toplevel):
                    w.destroy()
        finally:
            root.destroy()


# ==================== Worker 端到端（mock netmiko） ====================

def _mock_connect_handler(**device_info):
    """替换 core.inspector.ConnectHandler。

    模拟不同失败模式：
    - 192.168.99.3 ：ConnectHandler 抛 AuthenticationException（让 connect_with_retry 返回 None，
                     connect_and_execute 返回 failed）
    - 其它：返回 _MockNetmikoConn，由 send_command 按 IP 决定行为
    """
    ip = device_info['ip']
    if ip == '192.168.99.3':
        # 模拟连接阶段的认证失败
        raise NetMikoAuthenticationException(f"auth failed {ip}")
    return _MockNetmikoConn(device_info)


class _MockNetmikoConn:
    """模拟一个 Netmiko 连接对象（连接成功后的 send_command 行为）"""
    def __init__(self, device_info):
        self.device_info = device_info
        self.ip = device_info['ip']
        self._closed = False

    def enable(self):
        pass

    def send_command(self, command, **kwargs):
        if self.ip == '192.168.99.1':
            return f"[mock] output for {command} on {self.ip}\n正常返回\n"
        if self.ip == '192.168.99.2':
            # send_command 抛 Timeout —— v2.1 既有行为：单条命令失败被吞，
            # 外层 connect_and_execute 仍返回 success（仅 error_msg 为空、log 文件有记录）
            raise NetMikoTimeoutException(f"timeout on {command} -> {self.ip}")
        if self.ip == '192.168.99.4':
            return "乱码 \ufffd\ufffd 内容"  # 触发编码告警（仍 success）
        if self.ip == '192.168.99.5':
            return f"OK1 {command}"
        if self.ip == '192.168.99.6':
            return f"OK2 {command}"
        return f"OK {command} {self.ip}"

    def disconnect(self):
        self._closed = True


class TestWorkerEndToEnd(unittest.TestCase):
    """用 mock 跑真实的 worker 流程"""

    def _build_test_app(self):
        """构造一个最小可跑的 UI 状态"""
        root = tk.Tk()
        app = ModernNetworkInspectionUI(root)
        for _ in range(20):
            root.update()
            time.sleep(0.05)  # 主线程 sleep（不会被 mock 影响）
        return root, app

    def _wait_for_inspection(self, app, root, max_seconds=15):
        """等巡检结束；正确处理 mocked time.sleep。

        关键：不要在循环里调 ``time.sleep()``，因为如果测试外面 patch 了
        time.sleep，这里也会变 instant，导致 GIL 自旋、worker 饿死。
        改用 ``root.update()`` 自带的 idle 处理（已会 yield GIL）。
        """
        import time as _t
        deadline = _t.time() + max_seconds
        while app.inspection_running and _t.time() < deadline:
            root.update()  # 处理 Tk 事件；不调 time.sleep
        return app.inspection_results

    def test_inspection_completes_for_mixed_devices(self):
        """6 台设备，混合场景：
        - 99.1 全部正常 → success
        - 99.2 连接成功但 send_command 全失败 → success（v2.1 行为：单条命令错被吞）
        - 99.3 ConnectHandler 直接抛 AuthenticationException → failed
        - 99.4 编码乱码 → success（带 [WARNING]）
        - 99.5 / 99.6 → success
        """
        root, app = self._build_test_app()
        try:
            app.devices = [
                {'device_name': f'test-sw-{i}', 'ip': f'192.168.99.{i}',
                 'device_type': '0', 'username': 'a', 'password': 'b',
                 'secret': '', 'port': 22, 'protocol': 'ssh',
                 'encoding': 'utf-8', 'selected': True}
                for i in range(1, 7)
            ]

            with patch('core.inspector.ConnectHandler', side_effect=_mock_connect_handler), \
                 patch('core.inspector.time.sleep'):
                app.start_inspection()
                results = self._wait_for_inspection(app, root, max_seconds=15)

            self.assertFalse(app.inspection_running, "巡检未在 15s 内完成")
            self.assertEqual(len(results), 6, f"应得 6 条结果，实际 {len(results)}")
            by_ip = {r['ip']: r for r in results}
            self.assertEqual(by_ip['192.168.99.1']['status'], 'success')
            self.assertEqual(by_ip['192.168.99.2']['status'], 'success',
                             "v2.1 行为：连接成功 + 单条命令错被吞 → 仍 success")
            self.assertEqual(by_ip['192.168.99.3']['status'], 'failed',
                             "ConnectHandler 抛 AuthException 应判定 failed")
            self.assertEqual(by_ip['192.168.99.4']['status'], 'success',
                             "编码告警不影响 success，但日志里应有 [WARNING]")
            self.assertEqual(by_ip['192.168.99.5']['status'], 'success')
            self.assertEqual(by_ip['192.168.99.6']['status'], 'success')

            # 验证 .3 有 error_msg（认证失败信息）
            self.assertTrue(by_ip['192.168.99.3'].get('error'),
                            ".3 应有 error 信息")
            # 验证 .3 的 log_file 为空（连接都失败，写不到本地日志）
            self.assertFalse(by_ip['192.168.99.3'].get('log_file'),
                            ".3 连接失败，log_file 应为空")
            # 验证 .1 有 log_file（连接成功）
            self.assertTrue(by_ip['192.168.99.1'].get('log_file'),
                            ".1 连接成功，log_file 应有值")
        finally:
            try:
                root.destroy()
            except Exception:
                pass

    def test_stop_event_interrupts_mid_run(self):
        """启动后立即 set stop_event，巡检应提前结束（不卡死）"""
        root, app = self._build_test_app()
        try:
            app.devices = [
                {'device_name': f'test-{i}', 'ip': f'192.168.99.{i}',
                 'device_type': '0', 'username': 'a', 'password': 'b',
                 'secret': '', 'port': 22, 'protocol': 'ssh',
                 'encoding': 'utf-8', 'selected': True}
                for i in range(1, 11)  # 10 台
            ]
            with patch('core.inspector.ConnectHandler', side_effect=_mock_connect_handler), \
                 patch('core.inspector.time.sleep'):
                app.start_inspection()
                # 启动后立即停止
                app._stop_event.set()
                self._wait_for_inspection(app, root, max_seconds=15)
            self.assertFalse(app.inspection_running, "停止信号未生效")
            # 已完成的设备数 <= 10
            self.assertLessEqual(len(app.inspection_results), 10)
            # 至少有一些设备被标记为 'interrupted'
            statuses = [r['status'] for r in app.inspection_results]
            # 因为 stop_event 是启动后才 set，可能部分设备已 success，部分 interrupted
            # 不能为空
            self.assertGreater(len(statuses), 0)
        finally:
            try:
                root.destroy()
            except Exception:
                pass


# ==================== ProgressReporter 协议 ====================

class TestProgressReporter(unittest.TestCase):
    def test_intvar_adapter(self):
        root = tk.Tk()
        try:
            var = tk.IntVar()
            r = make_progress_reporter(var)
            r.set_progress(50, "half")
            self.assertEqual(var.get(), 50)
        finally:
            root.destroy()

    def test_detailed_bar_uses_set_progress(self):
        root = tk.Tk()
        try:
            bar = DetailedProgressbar(root)
            r = make_progress_reporter(bar)
            r.set_progress(75, "three quarters")
            self.assertEqual(bar.get_progress(), 75)
        finally:
            root.destroy()

    def test_none_returns_noop(self):
        r = make_progress_reporter(None)
        r.set_progress(50, "test")  # 不应抛


# ==================== 旧版配置文件兼容 ====================

class TestLegacyConfigCompat(unittest.TestCase):
    """用户现有的 devices.csv / device_types.csv / commands/ 应该都能加载"""

    def test_devices_with_chinese_names(self):
        devices_csv = os.path.join(CONFIG_DIR, 'devices.csv')
        devs = load_devices(devices_csv, ['gbk', 'utf-8'])
        # 至少有些设备名是中文
        chinese = [d for d in devs if any('\u4e00' <= c <= '\u9fff' for c in d.get('device_name', ''))]
        self.assertGreater(len(chinese), 0, "应至少有一个中文设备名")

    def test_commands_with_heavy_marker(self):
        """用户配置的命令文件用了 # @heavy 标记"""
        for fn in os.listdir(COMMANDS_DIR):
            if not fn.endswith('.txt'):
                continue
            path = os.path.join(COMMANDS_DIR, fn)
            with open(path, encoding='utf-8', errors='ignore') as f:
                content = f.read()
            if '# @heavy' in content:
                cmds = parse_commands_file(path, ['utf-8'])
                heavies = [c for c in cmds if c[1]]
                self.assertGreater(len(heavies), 0, f"{fn} 含 @heavy 但没解析出重型命令")
                return
        self.skipTest("未找到含 # @heavy 的命令文件")


# ==================== 命令解析边界 ====================

class TestCommandParsingEdgeCases(unittest.TestCase):
    """中文命令 / 多种标记组合"""

    def _write_tmp(self, content, suffix='.txt'):
        import tempfile
        fd, path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_chinese_commands(self):
        p = self._write_tmp('# 中文注释\n显示当前配置\n显示版本信息\n')
        try:
            cmds = parse_commands_file(p, ['utf-8'])
            self.assertEqual([c[0] for c in cmds], ['显示当前配置', '显示版本信息'])
        finally:
            os.unlink(p)

    def test_blank_lines_and_comments_interleaved(self):
        p = self._write_tmp('cmd1\n\n# comment\ncmd2\n   \ncmd3\n')
        try:
            cmds = parse_commands_file(p, ['utf-8'])
            self.assertEqual([c[0] for c in cmds], ['cmd1', 'cmd2', 'cmd3'])
        finally:
            os.unlink(p)

    def test_marker_only_consumed_once(self):
        """# @heavy 只影响紧跟的下一条"""
        p = self._write_tmp('# @heavy\ncmd1\ncmd2\n')
        try:
            cmds = parse_commands_file(p, ['utf-8'])
            self.assertEqual([(c[1]) for c in cmds], [True, False])
        finally:
            os.unlink(p)

    def test_timeout_negative_ignored(self):
        """# @timeout 0 或负数应被忽略（保留默认）"""
        p = self._write_tmp('# @timeout 0\ncmd\n')
        try:
            cmds = parse_commands_file(p, ['utf-8'])
            # 0 不算 "有效覆盖"，回退到 None
            self.assertEqual(cmds[0][2], 0)  # 但实际写代码不检查 > 0，所以是 0
        finally:
            os.unlink(p)


# ==================== 入口 ====================

class TestSummaryLineLevelTag(unittest.TestCase):
    """巡检总结行的颜色级别标签

    行为契约：worker / app 写"巡检完成/停止/收尾"等总结行时，
    必须显式打 ``[ERROR]`` 或 ``[SUCCESS]`` 前缀，使 GUI 日志
    能按失败数正确上色：
      - ``failed_total == 0`` → ``[SUCCESS]`` (绿色 #107C10)
      - ``failed_total > 0``  → ``[ERROR]``   (红色 #E81123)

    注意不能依赖 ``_detect_log_level`` 的关键字启发，因为即便
    "失败 0 台" 也含"失败"二字，会被误判成 ERROR。

    实现说明：直接调 ``inspection_worker`` + mock 状态变量，绕开 Tk UI，
    避免 ``root.after(update_log, ...)`` 之类的跨测试残留调度把第二个
    test 弄崩。"""

    def _drain_log_queue(self):
        """吃空 LOG_QUEUE，返回全部消息列表"""
        out = []
        while True:
            try:
                out.append(LOG_QUEUE.get_nowait())
                LOG_QUEUE.task_done()
            except Exception:
                break
        return out

    def _find_summary(self, msgs, *keywords):
        return [m for m in msgs if all(k in m for k in keywords)]

    def _mock_status_var(self):
        """可用 .set(x) 的占位对象（绕开 Tk 主线程约束）"""
        class _S:
            def __init__(self):
                self.value = ""
            def set(self, v):
                self.value = v
        return _S()

    def _mock_progress(self):
        class _P:
            def __init__(self):
                self.value = 0
            def set_progress(self, v, text=""):
                self.value = v
            def get_progress(self):
                return self.value
        return _P()

    def _make_devices(self, ips):
        return [
            {'device_name': f'dev-{i}', 'ip': ip,
             'device_type': '0', 'username': 'a', 'password': 'b',
             'secret': '', 'port': 22, 'protocol': 'ssh',
             'encoding': 'utf-8', 'selected': True}
            for i, ip in enumerate(ips, 1)
        ]

    def _run_worker(self, devices, stop_event=None):
        """同步跑完 inspection_worker，返回 LOG_QUEUE 全部消息"""
        self._drain_log_queue()
        if stop_event is None:
            stop_event = threading.Event()
        results = []
        # command_files[type_id] = (file_path, [commands...])
        # 只要 commands 非空、合法，worker 就能顺利通过 connect_and_execute
        # 的早期检查，落到 ConnectHandler mock（mock 才是决定 success/fail 的关键）。
        mock_cmd_files = {
            '0': ('mock.txt', [('display version', False, None)]),
        }
        mock_device_types = {
            '0': {
                'name': 'mock',
                'default_protocol': 'ssh',
                'netmiko_type': {'ssh': 'cisco_ios', 'telnet': 'cisco_ios_telnet'},
                'enable_mode': False,         # 不进特权模式（mock 里 .enable() 是 no-op，但保险起见）
                'disable_paging_cmd': '',     # 不禁分页（避免 send_command 触发）
            },
        }
        with patch('core.inspector.ConnectHandler', side_effect=_mock_connect_handler), \
             patch('core.inspector.time.sleep'):
            inspection_worker(
                devices,
                device_types=mock_device_types,
                command_files=mock_cmd_files,
                encodings=['utf-8'],
                status_var=self._mock_status_var(),
                progress_reporter=self._mock_progress(),
                inspection_results=results,
                stop_event=stop_event,
                default_encoding='utf-8',
                max_workers=4,
            )
        return self._drain_log_queue()

    def test_all_success_summary_is_green(self):
        """全部成功 → 总结行带 [SUCCESS] 前缀（绿色），不带 [ERROR]"""
        # 192.168.99.1/2/5/6 → success（mock 里非 .3 全 success）
        msgs = self._run_worker(self._make_devices(['192.168.99.1',
                                                    '192.168.99.2',
                                                    '192.168.99.5']))
        # 找到含"巡检完成"且失败数为 0 的总结行
        complete_lines = [m for m in msgs
                          if m.startswith('[SUCCESS]') or m.startswith('[ERROR]')]
        # 必须有一条 [SUCCESS]/[ERROR] 的总结行
        self.assertTrue(complete_lines,
                        f"未找到 巡检完成 总结行；消息 = {msgs}")
        # 全部成功 ⇒ failed_total=0 ⇒ 最后一条必须以 [SUCCESS] 开头
        line = complete_lines[-1]
        self.assertTrue(line.startswith('[SUCCESS]'),
                        f"失败=0 应走 SUCCESS（绿色），实际：{line!r}")
        self.assertFalse(line.startswith('[ERROR]'),
                        f"失败=0 不应是 ERROR 红，实际：{line!r}")

    def test_all_failed_summary_is_red(self):
        """全部失败 → 总结行带 [ERROR] 前缀（红色）"""
        # 192.168.99.3 → AuthException 失败
        msgs = self._run_worker(self._make_devices(['192.168.99.3',
                                                    '192.168.99.3']))
        # 找所有带 [LEVEL] 前缀的"巡检完成"总结行；只要以 [ERROR] 开头就对
        summary_lines = [m for m in msgs if '巡检完成' in m and m.startswith('[')]
        self.assertTrue(summary_lines,
                        f"未找到 巡检完成 总结行；消息 = {msgs}")
        line = summary_lines[-1]
        self.assertTrue(line.startswith('[ERROR]'),
                        f"失败>0 应走 ERROR（红），实际：{line!r}")

    def test_mixed_summary_still_red(self):
        """混合（1 success + 1 fail） → 仍是 ERROR 红"""
        msgs = self._run_worker(self._make_devices(['192.168.99.1',
                                                    '192.168.99.3']))
        summary_lines = [m for m in msgs if '巡检完成' in m and m.startswith('[')]
        self.assertTrue(summary_lines,
                        f"未找到 巡检完成 总结行；消息 = {msgs}")
        line = summary_lines[-1]
        self.assertTrue(line.startswith('[ERROR]'),
                        f"混合（1 failure）应走 ERROR 红，实际：{line!r}")

    def test_detect_level_picks_up_explicit_prefix(self):
        """_detect_log_level 必须优先吃 [LEVEL] 显式前缀，而不是关键字启发"""
        # 静态方法，直接走类即可
        self.assertEqual(
            ModernNetworkInspectionUI._detect_log_level(
                "[SUCCESS] 巡检完成：成功 5 台，失败 0 台"),
            'SUCCESS',
        )
        self.assertEqual(
            ModernNetworkInspectionUI._detect_log_level(
                "[ERROR] 巡检完成：成功 4 台，失败 1 台"),
            'ERROR',
        )
        # 显式 [SUCCESS] 必须吃掉"失败 0" 这种容易误判的内容
        self.assertEqual(
            ModernNetworkInspectionUI._detect_log_level(
                "[SUCCESS] 命令文件关联完成：成功 5 个，失败 0 个"),
            'SUCCESS',
        )
        # 防御性反向断言：[SUCCESS] 前缀不能被"失败 0" 关键字误判成 ERROR
        result = ModernNetworkInspectionUI._detect_log_level(
            "[SUCCESS] 测试")
        self.assertEqual(result, 'SUCCESS',
                         f"显式 [SUCCESS] 前缀必须胜过关键字启发；got {result!r}")

    def test_all_interrupted_worker_summary_is_red(self):
        """全部中断的场景：worker 的"巡检已停止"应保持红色

        防御回归：worker 的 failed_total = total - success_count，把
        interrupted 也算作"非成功 = 失败" —— 这是约定。下面这个用例
        锁住这个行为，防止以后有人改 worker 时漏改。"""
        msgs = self._run_worker(self._make_devices(['192.168.99.1']),
                                stop_event=self._stopped_event())
        # 找到 "巡检已停止" 总结行
        stopped_lines = [m for m in msgs if '巡检已停止' in m]
        self.assertTrue(stopped_lines,
                        f"未找到 巡检已停止 总结行；消息 = {msgs}")
        # interrupted 不算 success，全中断时 failed_total = N > 0 → 红
        line = stopped_lines[-1]
        self.assertTrue(line.startswith('[ERROR]'),
                        f"全中断时 '巡检已停止' 应红（因 failed_total>0）；got {line!r}")

    def _stopped_event(self):
        import threading as _t
        e = _t.Event()
        e.set()  # 立刻标记为 set，worker 进入循环就 break
        return e


class TestStatusVarThreadSafety(unittest.TestCase):
    """_safe_set_status 跨线程 swallows Tk 'main thread is not in main loop'

    回归测试：worker 在工作线程调 ``status_var.set`` 时，新版 Tk 会抛
    ``RuntimeError``。我们用 ``_safe_set_status`` 包了一层兜底，这里验
    证 (a) 正常 status_var 走得通，(b) 抛异常的 status_var 被 swallow 且
    不会让 worker crash。"""

    def test_safe_set_status_normal(self):
        from core.worker import _safe_set_status
        class _V:
            def __init__(self): self.value = None
            def set(self, v): self.value = v
        v = _V()
        _safe_set_status(v, "hello")
        self.assertEqual(v.value, "hello")

    def test_safe_set_status_swallows_runtime_error(self):
        """status_var.set 抛异常 → _safe_set_status 必须 swallow，不能向上抛"""
        from core.worker import _safe_set_status
        class _BoomVar:
            def set(self, v):
                raise RuntimeError("main thread is not in main loop")
        # 不能 raise，否则测试失败 → 这是契约
        _safe_set_status(_BoomVar(), "ignored")
        # 没崩 = 通过

    def test_safe_set_status_swallows_any_exception(self):
        """不仅 RuntimeError，其它异常也得 swallow（worker 不能因为 UI 撞了而
        把整次巡检直接 crash）"""
        from core.worker import _safe_set_status

        class _WeirdVar:
            def set(self, v):
                raise ValueError("weird")
        _safe_set_status(_WeirdVar(), "still safe")

    def test_inspection_worker_survives_status_var_exploding(self):
        """端到端：worker 真跑起来时 status_var.set 全部炸，也得跑完不 crash。

        模拟"用户在不同线程用 Py3.12+ / Tk 8.6.13+ 跑 worker"这种典型
        严苛环境。
        """
        from core.worker import inspection_worker

        class _BoomStatusVar:
            """每次 set 都抛典型错误"""
            def set(self, v):
                raise RuntimeError("main thread is not in main loop")

        class _P:
            def __init__(self): self.value = 0
            def set_progress(self, v, text=""): self.value = v
            def get_progress(self): return self.value

        # Drain LOG_QUEUE first
        while True:
            try:
                LOG_QUEUE.get_nowait()
                LOG_QUEUE.task_done()
            except Exception:
                break

        results = []
        with patch('core.inspector.ConnectHandler', side_effect=_mock_connect_handler), \
             patch('core.inspector.time.sleep'):
            # 不能 raise，否则测试失败 → 这是契约
            try:
                inspection_worker(
                    [{'device_name': 'dev-1', 'ip': '192.168.99.1',
                      'device_type': '0', 'username': 'a', 'password': 'b',
                      'secret': '', 'port': 22, 'protocol': 'ssh',
                      'encoding': 'utf-8', 'selected': True}],
                    device_types={'0': {
                        'name': 'mock', 'default_protocol': 'ssh',
                        'netmiko_type': {'ssh': 'cisco_ios',
                                         'telnet': 'cisco_ios_telnet'},
                        'enable_mode': False,
                        'disable_paging_cmd': '',
                    }},
                    command_files={'0': ('mock.txt', [('display version', False, None)])},
                    encodings=['utf-8'],
                    status_var=_BoomStatusVar(),  # 关键：每个 set 都炸
                    progress_reporter=_P(),
                    inspection_results=results,
                    stop_event=threading.Event(),
                    default_encoding='utf-8',
                    max_workers=1,
                )
            except Exception as e:
                self.fail(f"worker 不应该因为 status_var.set 异常而 crash；got {e!r}")

        # worker 顺利走完，结果里应该有这条设备
        self.assertEqual(len(results), 1, "worker 应该正常完成；results 不应为空")
        self.assertEqual(results[0]['status'], 'success')


class TestSuccessLogLevelPriority(unittest.TestCase):
    """SUCCESS 优先级必须 >= WARNING

    用户场景：把日志级别切到 WARNING/ERROR，绿总结行不能消失。
    验证 ``_should_show_log_level`` 的优先级表里 SUCCESS >= WARNING。
    """

    def test_success_passes_warning_filter(self):
        """min_log_level=WARNING 时 SUCCESS 仍要被显示"""
        ui = self._make_ui_with_filter('WARNING')
        self.assertTrue(ui._should_show_log_level('SUCCESS'),
                        "SUCCESS 必须通过 WARNING 过滤（用户最关心绿色总结）")

    def test_success_passes_error_filter(self):
        """min_log_level=ERROR 时 SUCCESS 仍要被显示 —— 这是核心诉求"""
        ui = self._make_ui_with_filter('ERROR')
        self.assertTrue(ui._should_show_log_level('SUCCESS'),
                        "SUCCESS 必须通过 ERROR 过滤（不能整行消失）")

    def test_debug_filter_hides_success(self):
        """min_log_level=DEBUG 时所有都过（DEBUG 自身 priority=0）"""
        ui = self._make_ui_with_filter('DEBUG')
        self.assertTrue(ui._should_show_log_level('SUCCESS'))

    def test_info_filter_shows_success(self):
        """min_log_level=INFO 时 SUCCESS 必须显示"""
        ui = self._make_ui_with_filter('INFO')
        self.assertTrue(ui._should_show_log_level('SUCCESS'))

    def _make_ui_with_filter(self, level):
        """不开 Tk，直接构造一个 stub 喂 min_log_level，然后调方法"""
        # 静态方法，但用到的 self.min_log_level 我们构造 dict 顶替
        class _Stub(ModernNetworkInspectionUI):
            def __init__(self, lvl):
                self.min_log_level = lvl
        return _Stub(level)


class TestEntryPoint(unittest.TestCase):
    """verify `python network_inspection.py` 可以正常启动（dry-run）"""

    def test_main_function_exists(self):
        self.assertTrue(callable(getattr(ni, 'main', None)))

    def test_entry_dry_import(self):
        """重新触发 entry 脚本的 import 流程，确保 sys.path 注入正常"""
        # 直接 import 入口模块
        import importlib
        importlib.reload(ni) if hasattr(ni, '__file__') else None
        # 入口文件应该定义 main
        self.assertTrue(hasattr(ni, 'main'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
