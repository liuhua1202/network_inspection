# H3C设备巡检配置指南

## 配置文件说明

### 1. 设备类型配置 (device_types.csv)

H3C设备类型配置：
```csv
3,H3C设备,hp_comware,hp_comware_telnet,0,screen-length disable,ssh,commands/commands_h3c.txt
```

**配置说明：**
- **类型ID**: 3
- **设备名称**: H3C设备
- **SSH驱动**: hp_comware (Netmiko H3C Comware驱动)
- **Telnet驱动**: hp_comware_telnet
- **Enable模式**: 0 (H3C设备通常不需要enable模式)
- **分页命令**: screen-length disable
- **默认协议**: SSH
- **命令文件**: commands/commands_h3c.txt

### 2. 命令配置文件 (commands_h3c.txt)

H3C设备常用巡检命令包括：

#### 系统基本信息
- `display version` - 显示系统版本信息
- `display device` - 显示设备硬件信息
- `display clock` - 显示系统时钟
- `display boot-loader` - 显示引导加载程序信息

#### 接口状态
- `display interface brief` - 显示接口简要信息
- `display interface` - 显示详细接口信息
- `display link-aggregation summary` - 显示链路聚合摘要
- `display port security` - 显示端口安全信息

#### 路由和转发
- `display ip routing-table` - 显示IP路由表
- `display arp all` - 显示ARP表
- `display mac-address` - 显示MAC地址表
- `display fib` - 显示转发信息库

#### 系统资源
- `display cpu-usage` - 显示CPU使用率
- `display memory` - 显示内存使用情况
- `display environment` - 显示环境信息
- `display power` - 显示电源状态

#### 配置和日志
- `display current-configuration` - 显示当前配置
- `display saved-configuration` - 显示保存的配置
- `display logbuffer` - 显示日志缓冲区
- `display diagnostic-information` - 显示诊断信息

## 设备列表配置

### 基本格式
```
设备名|IP地址|设备类型ID|用户名|密码|secret|端口|协议
```

### H3C设备配置示例

#### 1. SSH连接（推荐）
```
H3C交换机1|192.168.1.20|3|admin|admin123||22|ssh
H3C路由器1|192.168.1.21|3|manager|pass123||22|ssh
```

#### 2. Telnet连接
```
H3C核心交换机1|192.168.1.22|3|admin|admin123||23|telnet
```

#### 3. 非标准端口
```
H3C防火墙1|192.168.1.23|3|admin|admin123||2222|ssh
```

## 特殊配置说明

### H3C设备的特殊处理

#### 1. 连接参数
- **延迟因子**: 2（H3C设备响应较快）
- **读取超时**: 60秒
- **连接超时**: 30秒
- **认证超时**: 30秒

#### 2. 命令执行策略
- 标准send_command方式
- 自动分页处理（screen-length disable）
- 支持H3C Comware操作系统命令格式

#### 3. 认证机制
- 支持用户名密码认证
- 通常不需要enable模式
- 支持本地和远程认证

## 使用注意事项

### 1. SSH/Telnet配置
```bash
# H3C设备SSH配置示例
ssh server enable
local-user admin class manage
password simple admin123
service-type ssh
authorization-attribute user-role network-admin
```

### 2. 用户权限要求
- **基本查看权限**: network-operator权限
- **配置查看**: network-admin权限
- **系统信息**: 建议使用管理员账号

### 3. 网络配置
```bash
# 确保管理接口配置正确
interface M-GigabitEthernet0/0/0
 ip address 192.168.1.20 255.255.255.0
 undo shutdown
```

### 4. 性能考虑
- **执行时间**: H3C设备巡检通常需要2-5分钟
- **并发数建议**: 不超过15个并发连接
- **命令间隔**: 通常响应较快，无需额外延迟

## 故障排查

### 1. 连接失败
- 检查SSH服务：`display ssh server status`
- 验证网络连通性：`ping 管理IP`
- 检查用户配置：`display local-user`

### 2. 认证失败
- 验证用户名密码
- 检查用户权限：`display local-user admin`
- 查看认证日志：`display logbuffer | include login`

### 3. 命令执行超时
- 检查设备负载：`display cpu-usage`
- 检查内存使用：`display memory`
- 适当增加超时时间

### 4. 权限不足
- 确认用户角色（user-role）
- 使用具有network-admin权限的账号
- 检查AAA配置

## 常见H3C设备型号

### 交换机系列
- **S5500系列**: S5500-28C-EI, S5500-52C-EI等
- **S6800系列**: S6800-54QF, S6800-32Q等
- **S10500系列**: S10508, S10516等
- **S12500系列**: S12508X-AF, S12516X-AF等

### 路由器系列
- **MSR系列**: MSR2600, MSR3600, MSR4600等
- **CR系列**: CR16000-F, CR19000等
- **CSR系列**: CSR8000P等

### 防火墙系列
- **F100系列**: F100-A-G2, F100-C-G2等
- **F1000系列**: F1000-A-G2, F1000-C-G2等
- **F5000系列**: F5000-A5, F5000-C等

## 配置模板

### 基础巡检命令模板
```bash
# 系统信息
display version
display device
display clock

# 接口状态
display interface brief
display link-aggregation summary

# 路由信息
display ip routing-table
display arp all

# 系统资源
display cpu-usage
display memory

# 配置和日志
display current-configuration
display logbuffer
```

### 详细巡检命令模板
```bash
# 详细系统信息
display version
display device
display device pic-status
display boot-loader
display clock
display license

# 接口详细信息
display interface
display link-aggregation verbose
display port security
display stp brief

# 网络协议状态
display ip routing-table
display arp all
display mac-address
display fib
display bgp peer
display ospf peer brief

# 系统性能和环境
display cpu-usage
display memory
display environment
display power
display fan

# 配置和维护
display current-configuration
display saved-configuration
display patch information
display logbuffer
display diagnostic-information
```

## H3C特有功能

### 1. IRF（智能弹性架构）
```bash
display irf
display irf topology
display irf configuration
```

### 2. 虚拟化技术
```bash
display context
display resource
```

### 3. 安全功能
```bash
display port security
display mac-authentication
display dot1x
```

### 4. QoS配置
```bash
display qos policy
display qos queue-statistics
```

## 安全建议

1. **用户管理**: 创建专用巡检账号，设置network-operator权限
2. **访问控制**: 使用ACL限制管理访问源
3. **协议安全**: 优先使用SSH而非Telnet
4. **日志审计**: 启用操作日志记录
5. **定期维护**: 定期检查和更新设备固件

## 支持的H3C命令集

### Comware系统命令
- display系列命令（查看配置和状态）
- reset命令（重置统计信息）
- debugging命令（调试信息）

### 网络协议命令
- OSPF: `display ospf`系列
- BGP: `display bgp`系列
- ISIS: `display isis`系列
- MPLS: `display mpls`系列

### 交换机特有命令
- VLAN: `display vlan`系列
- STP: `display stp`系列
- 端口安全: `display port security`系列
- 链路聚合: `display link-aggregation`系列

### 路由器特有命令
- NAT: `display nat`系列
- VPN: `display ipsec`系列
- 防火墙: `display firewall`系列