# Juniper设备巡检配置指南

## 配置文件说明

### 1. 设备类型配置 (device_types.csv)

Juniper设备类型配置：
```csv
2,Juniper设备,juniper_junos,juniper_junos_telnet,0,set cli screen-length 0,ssh,commands/commands_juniper.txt
```

**配置说明：**
- **类型ID**: 2
- **设备名称**: Juniper设备
- **SSH驱动**: juniper_junos (Netmiko Junos驱动)
- **Telnet驱动**: juniper_junos_telnet
- **Enable模式**: 0 (Juniper设备不需要enable模式)
- **分页命令**: set cli screen-length 0
- **默认协议**: SSH
- **命令文件**: commands/commands_juniper.txt

### 2. 命令配置文件 (commands_juniper.txt)

Juniper设备常用巡检命令包括：

#### 系统基本信息
- `show version` - 显示系统版本信息
- `show chassis hardware` - 显示硬件信息
- `show system uptime` - 显示系统运行时间
- `show system boot-messages` - 显示启动消息

#### 接口状态
- `show interfaces terse` - 显示接口简要信息
- `show interfaces descriptions` - 显示接口描述
- `show interfaces extensive` - 显示详细接口信息
- `show interfaces diagnostics optics` - 显示光模块信息

#### 路由和转发
- `show route summary` - 显示路由摘要
- `show arp` - 显示ARP表
- `show ethernet-switching table` - 显示MAC地址表
- `show bgp summary` - 显示BGP摘要

#### 系统资源
- `show chassis routing-engine` - 显示路由引擎状态
- `show chassis environment` - 显示环境状态
- `show system processes extensive` - 显示进程信息
- `show chassis alarms` - 显示告警信息

#### 协议状态
- `show ospf neighbor` - 显示OSPF邻居
- `show bgp neighbor` - 显示BGP邻居
- `show isis adjacency` - 显示ISIS邻接
- `show mpls lsp` - 显示MPLS LSP

#### 配置和日志
- `show configuration` - 显示当前配置
- `show log messages` - 显示系统日志
- `show log chassisd` - 显示机箱守护进程日志

## 设备列表配置

### 基本格式
```
设备名|IP地址|设备类型ID|用户名|密码|secret|端口|协议
```

### Juniper设备配置示例

#### 1. SSH连接（推荐）
```
Juniper交换机1|192.168.1.30|2|admin|juniper123||22|ssh
Juniper路由器1|192.168.1.31|2|operator|pass123||22|ssh
```

#### 2. Telnet连接
```
Juniper核心路由器1|192.168.1.32|2|admin|juniper123||23|telnet
```

#### 3. 非标准端口
```
Juniper防火墙1|192.168.1.33|2|admin|juniper123||2222|ssh
```

## 特殊配置说明

### Juniper设备的特殊处理

#### 1. 连接参数
- **延迟因子**: 2（Junos系统响应较快）
- **读取超时**: 90秒
- **连接超时**: 30秒
- **认证超时**: 30秒

#### 2. Junos操作系统特点
- **无Enable模式**: Junos不需要特权模式切换
- **CLI模式**: 支持操作模式和配置模式
- **分页控制**: 使用`set cli screen-length 0`禁用分页

#### 3. 命令执行策略
- 标准send_command方式
- 自动分页处理
- 支持Junos特有的命令格式

## 使用注意事项

### 1. SSH配置
```bash
# Juniper设备SSH配置示例
set system services ssh
set system services ssh protocol-version v2
set system services ssh connection-limit 10
```

### 2. 用户权限配置
```bash
# 本地用户配置
set system login user admin uid 2000
set system login user admin class super-user
set system login user admin authentication plain-text-password
```

### 3. 管理接口配置
```bash
# 管理接口配置
set interfaces me0 unit 0 family inet address 192.168.1.30/24
set routing-options static route 0.0.0.0/0 next-hop 192.168.1.1
```

### 4. 性能考虑
- **执行时间**: Juniper设备巡检通常需要3-10分钟
- **并发数建议**: 不超过8个并发连接
- **命令复杂度**: 某些命令可能需要较长时间

## 故障排查

### 1. 连接失败
- 检查SSH服务：`show system services`
- 验证网络连通性：`ping 管理IP`
- 检查接口状态：`show interfaces me0`

### 2. 认证失败
- 验证用户名密码
- 检查用户配置：`show configuration system login`
- 查看认证日志：`show log messages | match login`

### 3. 命令执行问题
- 检查CLI模式：确认在operational mode
- 验证命令语法：参考Junos文档
- 检查设备负载：`show chassis routing-engine`

### 4. 权限不足
- 确认用户class权限
- 使用具有足够权限的账号
- 检查用户组配置

## 常见Juniper设备型号

### 交换机系列
- **EX系列**: EX2300, EX3400, EX4300, EX4600
- **QFX系列**: QFX5100, QFX5200, QFX10000
- **ELS系列**: 增强型局域网交换

### 路由器系列
- **MX系列**: MX240, MX480, MX960, MX10003
- **PTX系列**: PTX1000, PTX3000, PTX5000
- **ACX系列**: ACX1000, ACX2000, ACX5000

### 安全设备
- **SRX系列**: SRX300, SRX1500, SRX4600
- **vSRX**: 虚拟化安全设备

### 无线设备
- **WLC系列**: 无线局域网控制器
- **AP系列**: 无线接入点

## 配置模板

### 基础巡检命令模板
```bash
# 系统信息
show version
show chassis hardware
show system uptime

# 接口状态
show interfaces terse
show interfaces descriptions

# 路由信息
show route summary
show arp

# 系统状态
show chassis routing-engine
show chassis environment
```

### 详细巡检命令模板
```bash
# 详细系统信息
show version
show chassis hardware detail
show chassis environment
show system uptime
show system boot-messages
show system core-dumps

# 接口详细信息
show interfaces extensive
show interfaces descriptions
show interfaces diagnostics optics
show interfaces queue

# 网络协议详情
show route
show route summary
show arp
show ethernet-switching table
show lldp neighbors

# 路由协议
show ospf neighbor
show ospf database
show bgp summary
show bgp neighbor
show isis adjacency
show mpls lsp

# 系统性能
show chassis routing-engine
show system processes extensive
show system memory
show chassis pic fpc-slot 0 pic-slot 0

# 告警和日志
show chassis alarms
show log messages | last 50
show log chassisd | last 20

# 配置信息
show configuration | display set
show system commit
```

### 交换机专用命令
```bash
# VLAN信息
show vlans
show vlans extensive
show ethernet-switching table

# 生成树
show spanning-tree bridge
show spanning-tree interface

# 链路聚合
show interfaces ae0
show lacp interfaces

# 端口镜像
show interfaces xe-0/0/0 extensive
```

### 路由器专用命令
```bash
# 路由表详情
show route
show route protocol bgp
show route protocol ospf
show route forwarding-table

# MPLS信息
show mpls lsp
show mpls path
show rsvp session

# 流量工程
show mpls lsp
show ted database
```

### 安全设备专用命令
```bash
# 安全策略
show security policies
show security zones
show security nat

# 会话信息
show security flow session
show security ike security-associations
show security ipsec security-associations

# 威胁检测
show security utm anti-virus status
show security utm web-filtering status
```

## Junos CLI操作模式

### 1. 操作模式 (Operational Mode)
```bash
# 查看命令
show version
show interfaces
show route

# 清除命令
clear arp
clear log messages
clear bgp neighbor
```

### 2. 配置模式 (Configuration Mode)
```bash
# 进入配置模式
configure

# 配置命令
set interfaces ge-0/0/0 description "To Core Switch"
set protocols ospf area 0.0.0.0 interface ge-0/0/0

# 提交配置
commit
exit
```

## 安全建议

1. **访问控制**: 配置防火墙过滤器
```bash
set firewall family inet filter mgmt-access term allow-ssh from source-address 192.168.100.0/24
set firewall family inet filter mgmt-access term allow-ssh then accept
```

2. **用户管理**: 使用强密码和适当权限
```bash
set system login user admin class super-user
set system login user admin authentication plain-text-password
```

3. **协议安全**: 配置安全的管理协议
```bash
set system services ssh protocol-version v2
set system services netconf ssh
```

4. **日志记录**: 启用系统日志
```bash
set system syslog user * any emergency
set system syslog file messages any notice
set system syslog file security authorization info
```

5. **SNMP安全**: 配置SNMPv3
```bash
set snmp v3 usm local-engine user admin authentication-sha authentication-password
set snmp v3 usm local-engine user admin privacy-des privacy-password
```

## 支持的Junos命令集

### 查看命令 (show)
- 系统信息: `show version`, `show chassis`
- 接口状态: `show interfaces`
- 路由信息: `show route`, `show arp`
- 协议状态: `show ospf`, `show bgp`

### 操作命令 (clear, restart, request)
- 清除操作: `clear arp`, `clear log`
- 重启操作: `restart routing`
- 请求操作: `request system reboot`

### 监控命令 (monitor)
- 接口监控: `monitor interface ge-0/0/0`
- 流量监控: `monitor traffic interface ge-0/0/0`