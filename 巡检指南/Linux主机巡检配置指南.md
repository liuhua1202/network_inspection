# Linux主机巡检配置指南

## 配置文件说明

### 1. 设备类型配置 (device_types.csv)

已添加Linux主机设备类型：
```csv
6,Linux主机,linux,linux,0,,ssh,commands/commands_linux.txt
```

**配置说明：**
- **类型ID**: 6
- **设备名称**: Linux主机
- **SSH/Telnet驱动**: linux (Netmiko的通用Linux驱动)
- **Enable模式**: 0 (Linux系统不需要enable模式)
- **分页命令**: 空 (Linux使用环境变量控制分页)
- **默认协议**: SSH
- **命令文件**: commands/commands_linux.txt

### 2. 命令配置文件 (commands_linux.txt)

包含以下类别的Linux系统巡检命令：

#### 系统基本信息
- `uname -a` - 系统内核信息
- `hostname` - 主机名
- `whoami` - 当前用户
- `pwd` - 当前目录

#### 系统资源状态
- `df -h` - 磁盘使用情况
- `free -h` - 内存使用情况
- `lscpu` - CPU信息
- `uptime` - 系统运行时间和负载

#### 网络状态
- `ip addr show` - 网络接口信息
- `ip route show` - 路由表
- `ss -tuln` - 网络连接状态
- `netstat -rn` - 网络路由信息

#### 进程和服务状态
- `ps aux --sort=-%cpu | head -20` - CPU使用率最高的20个进程
- `systemctl status` - 系统服务状态
- `systemctl list-failed` - 失败的服务列表

#### 其他监控项
- 存储信息、系统日志、环境变量等

## 设备列表配置

### 基本格式
```
设备名|IP地址|设备类型ID|用户名|密码|secret|端口|协议
```

### Linux主机配置示例

#### 1. 使用SSH密钥认证（推荐）
```
Web服务器1|192.168.1.100|6|webadmin||22|ssh
```
- 密码字段为空，依赖SSH密钥认证
- secret字段为空（Linux不需要）

#### 2. 使用用户名密码认证
```
数据库服务器1|192.168.1.101|6|dbadmin|db123456||22|ssh
```

#### 3. 非标准SSH端口
```
安全服务器1|192.168.1.104|6|secadmin|sec123456||2222|ssh
```

## 特殊配置说明

### Linux设备的特殊处理

根据项目规范，Linux主机设备会享受以下特殊优化：

#### 1. 连接参数优化
- **延迟因子**: 6（较高的延迟以适应Linux系统响应）
- **读取超时**: 300秒（5分钟）
- **连接超时**: 90秒
- **认证超时**: 90秒
- **SSH严格检查**: 禁用

#### 2. 命令执行策略
- **优先timing方式**: 使用`send_command_timing`避免提示符识别问题
- **宽松提示符模式**: 支持多种Linux提示符格式
- **多层容错**: 标准执行 → 提示符匹配 → timing方式

#### 3. 环境变量设置
程序会自动设置：
```bash
export PAGER=cat     # 禁用分页器
export TERM=dumb     # 设置哑终端
```

## 使用注意事项

### 1. SSH配置要求
确保Linux主机SSH服务配置：
```bash
# /etc/ssh/sshd_config
PermitRootLogin yes/no          # 根据需要设置
PasswordAuthentication yes      # 如果使用密码认证
PubkeyAuthentication yes        # 如果使用密钥认证
Port 22                         # 或自定义端口
```

### 2. 用户权限要求
巡检用户需要以下权限：
- **基本系统信息**: 普通用户权限即可
- **系统服务状态**: 可能需要sudo权限
- **系统日志**: 可能需要sudo权限

### 3. 防火墙配置
确保SSH端口在防火墙中开放：
```bash
# Ubuntu/Debian
sudo ufw allow ssh
sudo ufw allow 22/tcp

# CentOS/RHEL
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --reload
```

### 4. 性能考虑
- **执行时间**: Linux主机巡检可能需要5-10分钟
- **并发数建议**: 不超过5个并发连接
- **网络带宽**: 巡检结果可能产生较大的日志文件

## 故障排查

### 1. 连接失败
- 检查SSH服务状态：`systemctl status sshd`
- 验证网络连通性：`ping 目标IP`
- 检查防火墙设置：`iptables -L` 或 `ufw status`

### 2. 认证失败
- 验证用户名密码
- 检查SSH密钥配置
- 查看SSH日志：`journalctl -u sshd`

### 3. 命令执行超时
- 检查系统负载：`top` 或 `htop`
- 适当增加超时时间
- 检查网络延迟

### 4. 权限不足
- 为巡检用户添加sudo权限
- 或使用有足够权限的用户账号

## 日志文件位置

巡检完成后，可在以下位置查看详细日志：
- **巡检结果**: `InspectionLogs/YYYY_MM_DD/设备名_IP_时间戳.txt`
- **会话日志**: `InspectionLogs/YYYY_MM_DD/设备名_IP_session_时间戳.log`
- **调试日志**: `InspectionLogs/debug.log`

## 自定义命令

您可以根据需要修改 `commands_linux.txt` 文件，添加特定的巡检命令：

```bash
# 添加自定义检查
docker ps -a                    # Docker容器状态
nginx -t                        # Nginx配置检查
mysql --version                 # MySQL版本信息
java -version                   # Java版本信息
```

## 安全建议

1. **使用专用巡检账号**: 创建权限最小的专用用户
2. **SSH密钥认证**: 优先使用密钥而非密码认证
3. **网络隔离**: 在管理网络中进行巡检
4. **日志审计**: 定期检查巡检日志，确保无异常访问
5. **密码安全**: 如必须使用密码，确保密码强度和定期更换