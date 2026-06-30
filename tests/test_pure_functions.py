"""纯函数单测：不依赖 Tk / Netmiko / 文件系统。

被测函数都从 network_inspection 顶层导入（暂时在单文件模式下；
后续模块化后只需改 import 行，测试本身不变）。
"""
import os
import sys
import unittest
import tempfile

# 把项目根加入 sys.path，确保 import network_inspection 命中源码
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import network_inspection as ni


class TestParseSelected(unittest.TestCase):
    def test_truthy_values(self):
        for v in ['1', 'true', 'TRUE', 'yes', 'YES', 'on', 'y', 't', '1']:
            self.assertTrue(ni._parse_selected(v), f"{v!r} should be True")

    def test_falsy_values(self):
        for v in ['0', 'false', 'FALSE', 'no', 'NO', 'off', 'n', 'f', '0']:
            self.assertFalse(ni._parse_selected(v), f"{v!r} should be False")

    def test_empty_and_none_default_true(self):
        """向后兼容：空值视为 True（默认勾选）"""
        self.assertTrue(ni._parse_selected(''))
        self.assertTrue(ni._parse_selected(None))
        self.assertTrue(ni._parse_selected('   '))

    def test_unknown_string_defaults_true(self):
        """未识别的非空值兜底为 True，不让用户写了中文"是"被静默忽略"""
        self.assertTrue(ni._parse_selected('是'))
        self.assertTrue(ni._parse_selected('xxx'))


class TestIsCommentLine(unittest.TestCase):
    def test_hash_prefix(self):
        self.assertTrue(ni.is_comment_line(['# 注释']))
        self.assertTrue(ni.is_comment_line(['  # 注释']))

    def test_pipe_separator_with_comment(self):
        """# 出现在数据行中间不是注释行（设备名/密码里都可能含 #）"""
        self.assertFalse(ni.is_comment_line(['设备', '# 注释']))

    def test_first_field_is_comment(self):
        """第一个非空字段以 # 开头才算整行注释"""
        self.assertTrue(ni.is_comment_line(['# 整行是注释', '', '']))
        self.assertTrue(ni.is_comment_line(['#header', 'data', 'data']))

    def test_non_comment(self):
        self.assertFalse(ni.is_comment_line(['设备名', 'IP']))
        self.assertFalse(ni.is_comment_line([]))


class TestSanitizeFilename(unittest.TestCase):
    def test_windows_illegal_chars(self):
        self.assertEqual(ni.sanitize_filename('a<b>c:d"e/f\\g|h?i*j'),
                         'a_b_c_d_e_f_g_h_i_j')

    def test_passthrough_safe(self):
        self.assertEqual(ni.sanitize_filename('device-01_192.168.1.1'),
                         'device-01_192.168.1.1')

    def test_chinese_preserved(self):
        # 中文字符不在 Windows 非法字符列表里，原样保留
        self.assertEqual(ni.sanitize_filename('浪潮-cisco-sw-01'),
                         '浪潮-cisco-sw-01')


class TestValidateIP(unittest.TestCase):
    def test_valid_v4(self):
        self.assertTrue(ni.validate_ip('192.168.1.1'))
        self.assertTrue(ni.validate_ip('10.0.0.1'))

    def test_invalid(self):
        self.assertFalse(ni.validate_ip('256.1.1.1'))
        self.assertFalse(ni.validate_ip('not-an-ip'))
        self.assertFalse(ni.validate_ip(''))

    def test_valid_v6(self):
        # ipaddress.ip_address 也接受 IPv6
        self.assertTrue(ni.validate_ip('::1'))


class TestValidatePort(unittest.TestCase):
    def test_range(self):
        self.assertTrue(ni.validate_port(1))
        self.assertTrue(ni.validate_port(22))
        self.assertTrue(ni.validate_port(65535))
        self.assertFalse(ni.validate_port(0))
        self.assertFalse(ni.validate_port(65536))
        self.assertFalse(ni.validate_port(-1))


class TestResolveEffectiveEncoding(unittest.TestCase):
    """_resolve_effective_encoding 三级优先级：device > device_type > default > 'gbk'"""

    def test_device_encoding_wins(self):
        device = {'encoding': 'utf-8'}
        cfg = {'encoding': 'gbk'}
        self.assertEqual(ni._resolve_effective_encoding(device, cfg, 'utf-8'), 'utf-8')

    def test_device_type_fallback(self):
        device = {'encoding': ''}   # 空值视为未指定
        cfg = {'encoding': 'gb2312'}
        self.assertEqual(ni._resolve_effective_encoding(device, cfg, 'utf-8'), 'gb2312')

    def test_default_fallback(self):
        device = {}
        cfg = {}
        self.assertEqual(ni._resolve_effective_encoding(device, cfg, 'utf-8'), 'utf-8')

    def test_gbk_hardcoded_fallback(self):
        """全空时兜底 GBK（项目中文环境、devices.csv 用 GBK 保存）"""
        device = {}
        cfg = None  # 非 dict 也得稳
        self.assertEqual(ni._resolve_effective_encoding(device, cfg, None), 'gbk')

    def test_none_cfg_handled(self):
        device = {'encoding': 'utf-8'}
        self.assertEqual(ni._resolve_effective_encoding(device, None, 'gbk'), 'utf-8')

    def test_lowercased(self):
        device = {'encoding': 'UTF-8'}
        self.assertEqual(ni._resolve_effective_encoding(device, {}, 'gbk'), 'utf-8')


class TestCheckEncodingMatch(unittest.TestCase):
    def test_clean_output(self):
        matched, n = ni._check_encoding_match('正常输出 hello', 'sw-01', 'utf-8')
        self.assertTrue(matched)
        self.assertEqual(n, 0)

    def test_replacement_chars_triggered(self):
        # 阈值默认 2，3 个替换字符应该告警
        out = '乱码 \ufffd\ufffd\ufffd 更多乱码'
        matched, n = ni._check_encoding_match(out, 'sw-01', 'utf-8', threshold=2)
        self.assertFalse(matched)
        self.assertEqual(n, 3)

    def test_below_threshold(self):
        out = '单个 \ufffd 字符可能是巧合'
        matched, n = ni._check_encoding_match(out, 'sw-01', 'utf-8', threshold=2)
        self.assertTrue(matched)
        self.assertEqual(n, 1)

    def test_empty_output(self):
        matched, n = ni._check_encoding_match('', 'sw-01', 'utf-8')
        self.assertTrue(matched)
        self.assertEqual(n, 0)

    def test_non_string_input(self):
        matched, n = ni._check_encoding_match(None, 'sw-01', 'utf-8')
        self.assertTrue(matched)
        self.assertEqual(n, 0)


class TestParseCommandsFile(unittest.TestCase):
    def _write(self, content, enc='utf-8'):
        fd, path = tempfile.mkstemp(suffix='.txt')
        with os.fdopen(fd, 'w', encoding=enc) as f:
            f.write(content)
        return path

    def test_basic_commands(self):
        p = self._write('show version\nshow ip int brief\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual(cmds, [
                ('show version', False, None),
                ('show ip int brief', False, None),
            ])
        finally:
            os.unlink(p)

    def test_heavy_marker(self):
        p = self._write('# @heavy\ndisplay current-configuration\nshow version\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual(len(cmds), 2)
            self.assertEqual(cmds[0], ('display current-configuration', True, None))
            self.assertEqual(cmds[1], ('show version', False, None))
        finally:
            os.unlink(p)

    def test_timeout_marker(self):
        p = self._write('# @timeout 90\nshow tech-support\nshow version\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual(cmds[0], ('show tech-support', False, 90))
            self.assertEqual(cmds[1], ('show version', False, None))
        finally:
            os.unlink(p)

    def test_timeout_overrides_heavy(self):
        """@timeout 应优先于 @heavy"""
        p = self._write('# @heavy\n# @timeout 45\nshow tech\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual(cmds, [('show tech', True, 45)])
        finally:
            os.unlink(p)

    def test_comments_and_blank_lines_skipped(self):
        p = self._write('# 普通注释\n\nshow version\n# 另一条注释\nshow ip\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual([c[0] for c in cmds], ['show version', 'show ip'])
        finally:
            os.unlink(p)

    def test_gbk_file(self):
        p = self._write('显示当前配置\n显示版本\n', enc='gbk')
        try:
            cmds = ni.parse_commands_file(p, ['gbk', 'utf-8'])
            self.assertEqual([c[0] for c in cmds], ['显示当前配置', '显示版本'])
        finally:
            os.unlink(p)

    def test_nonexistent_returns_empty(self):
        cmds = ni.parse_commands_file('/nonexistent/xx.txt', ['utf-8'])
        self.assertEqual(cmds, [])

    def test_heavy_marker_consumed(self):
        """@heavy 只对紧跟的下一条命令生效"""
        p = self._write('# @heavy\ncmd1\ncmd2\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            self.assertEqual([(c[1]) for c in cmds], [True, False])
        finally:
            os.unlink(p)

    def test_invalid_timeout_ignored(self):
        p = self._write('# @timeout abc\nshow x\n')
        try:
            cmds = ni.parse_commands_file(p, ['utf-8'])
            # 非法 timeout 应回退为 None
            self.assertEqual(cmds, [('show x', False, None)])
        finally:
            os.unlink(p)


class TestLoadDevicesConfig(unittest.TestCase):
    def _write(self, content, enc='utf-8'):
        fd, path = tempfile.mkstemp(suffix='.csv')
        with os.fdopen(fd, 'w', encoding=enc) as f:
            f.write(content)
        return path

    def test_basic_csv(self):
        p = self._write('设备名,IP,类型ID,用户名,密码,enable密码,端口,协议,编码,selected\n'
                        'sw-01,192.168.1.1,1,admin,secret,,22,ssh,utf-8,1\n'
                        'sw-02,192.168.1.2,1,admin,secret,,22,ssh,utf-8,0\n')
        try:
            devs = ni.load_devices(p, ['utf-8'])
            self.assertEqual(len(devs), 2)
            self.assertEqual(devs[0]['device_name'], 'sw-01')
            self.assertEqual(devs[0]['ip'], '192.168.1.1')
            self.assertEqual(devs[0]['port'], 22)
            self.assertEqual(devs[0]['selected'], True)
            self.assertEqual(devs[1]['selected'], False)
        finally:
            os.unlink(p)

    def test_pipe_separator_with_comment(self):
        p = self._write('# 注释行\n'
                        'sw-01|192.168.1.1|1|admin|pwd||22|ssh|utf-8|1\n',
                        enc='utf-8')
        # 改成 .txt 扩展名才会用 | 分隔
        new_p = p.replace('.csv', '.txt')
        os.rename(p, new_p)
        try:
            devs = ni.load_devices(new_p, ['utf-8'])
            self.assertEqual(len(devs), 1)
            self.assertEqual(devs[0]['device_name'], 'sw-01')
            self.assertEqual(devs[0]['protocol'], 'ssh')
        finally:
            os.unlink(new_p)

    def test_default_port_22(self):
        p = self._write('name,ip,type\nsw,10.0.0.1,1\n')
        try:
            devs = ni.load_devices(p, ['utf-8'])
            self.assertEqual(devs[0]['port'], 22)
            self.assertEqual(devs[0]['protocol'], None)
        finally:
            os.unlink(p)

    def test_no_selected_column_defaults_true(self):
        p = self._write('name,ip,type\nsw,10.0.0.1,1\n')
        try:
            devs = ni.load_devices(p, ['utf-8'])
            self.assertEqual(devs[0]['selected'], True)
        finally:
            os.unlink(p)

    def test_gbk_file(self):
        p = self._write('设备名,IP,类型ID,用户名,密码,enable密码,端口,协议,编码,selected\n'
                        '浪潮-cisco-sw-01,192.168.139.1,1,cisco,cisco,cisco,22,ssh,gbk,1\n',
                        enc='gbk')
        try:
            devs = ni.load_devices(p, ['gbk', 'utf-8'])
            self.assertEqual(devs[0]['device_name'], '浪潮-cisco-sw-01')
            self.assertEqual(devs[0]['encoding'], 'gbk')
        finally:
            os.unlink(p)

    def test_empty_file(self):
        p = self._write('')
        try:
            devs = ni.load_devices(p, ['utf-8'])
            self.assertEqual(devs, [])
        finally:
            os.unlink(p)


class TestLoadDeviceTypesConfig(unittest.TestCase):
    def _write(self, content, ext='.csv'):
        fd, path = tempfile.mkstemp(suffix=ext)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_csv_basic(self):
        p = self._write('0,华为设备,huawei,huawei_telnet,0,screen-length 0 temporary,ssh,commands/commands_huawei.txt\n'
                        '1,思科设备,cisco_ios,cisco_ios_telnet,1,terminal length 0,ssh,commands/commands_cisco.txt\n')
        try:
            dt = ni.load_device_types_config(p, ['utf-8'])
            self.assertEqual(len(dt), 2)
            self.assertEqual(dt['0']['name'], '华为设备')
            self.assertEqual(dt['0']['netmiko_type']['ssh'], 'huawei')
            self.assertTrue(dt['1']['enable_mode'])
            self.assertEqual(dt['1']['commands_file'], 'commands/commands_cisco.txt')
        finally:
            os.unlink(p)

    def test_pipe_separator(self):
        p = self._write('# 注释\n'
                        '0|华为设备|huawei|huawei_telnet|0|screen-length 0 temporary|ssh|cmd.txt\n',
                        ext='.txt')
        try:
            dt = ni.load_device_types_config(p, ['utf-8'])
            self.assertIn('0', dt)
            self.assertEqual(dt['0']['default_protocol'], 'ssh')
        finally:
            os.unlink(p)

    def test_short_rows_skipped(self):
        """少于 7 列的行被跳过，不抛异常"""
        p = self._write('0,华为,huawei\n'  # 只有 3 列，坏行
                        '1,思科,cisco_ios,cisco_ios_telnet,1,terminal length 0,ssh,cmd.txt\n')
        try:
            dt = ni.load_device_types_config(p, ['utf-8'])
            self.assertIn('1', dt)
            self.assertNotIn('0', dt)
        finally:
            os.unlink(p)

    def test_empty_returns_empty_dict(self):
        p = self._write('')
        try:
            self.assertEqual(ni.load_device_types_config(p, ['utf-8']), {})
        finally:
            os.unlink(p)


class TestValidateDevicesConfig(unittest.TestCase):
    def _dev(self, **kw):
        base = {'device_name': 'sw-01', 'ip': '192.168.1.1',
                'device_type': '1', 'username': 'a', 'password': 'b',
                'secret': '', 'port': 22, 'protocol': 'ssh',
                'encoding': None, 'selected': True}
        base.update(kw)
        return base

    def test_all_valid(self):
        dt = {'1': {'name': 'cisco'}}
        devs = [self._dev()]
        r = ni.validate_devices_config_with_details(devs, dt)
        self.assertTrue(r['valid'])
        self.assertEqual(r['error_count'], 0)

    def test_bad_ip(self):
        dt = {'1': {'name': 'cisco'}}
        r = ni.validate_devices_config_with_details([self._dev(ip='999.1.1.1')], dt)
        self.assertFalse(r['valid'])
        self.assertTrue(any('IP' in e for e in r['errors']))

    def test_unknown_type(self):
        dt = {'1': {'name': 'cisco'}}
        r = ni.validate_devices_config_with_details([self._dev(device_type='99')], dt)
        self.assertFalse(r['valid'])
        self.assertTrue(any('类型' in e for e in r['errors']))

    def test_bad_port(self):
        dt = {'1': {'name': 'cisco'}}
        r = ni.validate_devices_config_with_details([self._dev(port=99999)], dt)
        self.assertFalse(r['valid'])

    def test_empty_name_skips_to_next(self):
        dt = {'1': {'name': 'cisco'}}
        r = ni.validate_devices_config_with_details([self._dev(device_name=''),
                                                     self._dev()], dt)
        self.assertFalse(r['valid'])
        self.assertEqual(r['error_count'], 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
