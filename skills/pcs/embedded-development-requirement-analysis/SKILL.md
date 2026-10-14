---
name: embedded-development-requirement-analysis
description: "嵌入式开发需求分析技能：当业务人员用自然语言描述逆变器、PCS、MCU、DSP、FPGA、Linux 或嵌入式软件需求时，自动识别所属开发方向、细分场景、关键指标、接口和验收缺口，并输出 Excel 版需求分析结果。"
---

# 嵌入式开发需求分析技能

## 技能定位

当业务人员描述一段自然语言需求后，本技能负责把描述转换成结构化的需求分析草稿：

1. 判断需求主要属于 `DSP`、`FPGA`、`MCU`、`Linux` 中的哪些方向。
2. 进一步识别具体场景，例如：
   - DSP：电网并网指标、MPPT 与效率、LVRT/HVRT、控制环与运行模式
   - FPGA：ADC 采样链路、硬件保护、通信加速、时钟域与资源
   - MCU：外部通信协议、Flash 本地存储、事件与故障追溯
   - Linux：HMI、云端接入、历史数据与系统服务
3. 按现有模板 `docs/inverter-requirement-analysis-template.xlsx` 的 `02-需求总表` 25 个字段生成分析结果。
4. 输出 Excel 文件，包含：
   - `00-原始需求`
   - `01-分析摘要`
   - `02-需求总表`
   - `03-方向分析`
   - `04-待确认问题`
   - `05-生成说明`

## 什么时候触发

以下情况使用本技能：

- “帮我分析一下这个逆变器需求”
- “这是并网控制需求，应该归到哪个开发方向？”
- “根据这段业务描述生成需求分析 Excel”
- “帮我把 MCU/DSP/FPGA/Linux 的需求拆开”
- “这条需求属于 DSP、FPGA、MCU 还是 Linux？”

## 禁止事项

本技能只做需求分析草稿和 Excel 整理，不替代：

- 正式需求契约签发
- 需求映射表定版
- 嵌入式源码生成
- 编译、烧写、仿真或 HIL 测试
- 正式架构设计和实现决策

如果用户明确要求进入正式研发流程，应转交团队规定的需求/代码生成总控流程。

## 执行流程

### 1. 读取业务描述

优先使用业务人员原始描述，不要擅自增加产品假设。若输入较短，可以从以下信息补齐：

- 目标芯片或平台
- 功能目标
- 性能指标
- 通信协议
- 存储要求
- 保护要求
- HMI/云端要求
- 时序和资源约束

### 2. 判断开发方向

按以下关键词和职责边界判断：

| 方向 | 典型职责 |
|---|---|
| DSP | 并网、功率控制、THD、功率因数、LVRT/HVRT、MPPT、控制环、锁相、软件保护 |
| FPGA | ADC 采样、SNR、抖动、同步采样、硬件保护、跳闸、GOOSE/EtherCAT、通信加速、时钟域 |
| MCU | RS485、CAN、Modbus、MQTT、TCP/IP、Flash、事件记录、历史数据、故障录波 |
| Linux | HMI、云端、MQTT 上送、IEC 104、DL/T 695、数据库、本地曲线、OTA、系统服务 |

一条业务描述通常可能同时属于多个方向。例如：

> 需要 FPGA 采样和硬件保护，DSP 做并网控制，MCU 做 Modbus 和历史存储，Linux 做 HMI 和云端上送。

这种情况应该分别生成 DSP、FPGA、MCU、Linux 的需求分析行，而不是强行归为单一方向。

### 3. 判断具体场景

对于每个方向，继续识别场景标签：

- DSP：
  - 电网并网指标
  - MPPT 与效率
  - LVRT/HVRT 与故障穿越
  - 控制环与运行模式
- FPGA：
  - ADC 采样链路
  - 硬件保护与跳闸
  - 通信加速与实时网络
  - 时钟域与资源约束
- MCU：
  - 外部通信协议
  - Flash 与本地存储
  - 事件与故障追溯
- Linux：
  - HMI 与本地监控
  - 云端通信与协议网关
  - 历史数据与系统服务

如果无法明确场景，应生成“待确认”场景，并将问题登记到 `04-待确认问题`。

### 4. 提取参数和缺口

尝试从描述中识别：

- 数值指标：如 `THD≤3%`、`30天`、`SNR`、采样率、响应时间
- 单位：`%`、`p.u.`、`ms`、`Hz`、`V`、`A`、`MB` 等
- 协议：Modbus、CAN、MQTT、IEC 104、DL/T 695、GOOSE
- 时序：采样周期、控制周期、超时、响应时间
- 数据：Flash、历史数据、故障录波、本地曲线
- 保护：过流、过压、跳闸、LVRT、HVRT

同时主动发现缺失项，尤其是：

- 适用工况和测量条件
- 接口对象、数据格式、寄存器或点表
- 时序和响应时间
- 异常处理、降级和掉电策略
- 验收方法和判据
- 标准版本或客户来源

### 5. 生成需求总表行

每条需求按模板字段填写。没有明确信息时，不要编造数值，统一写为：

```text
待确认
```

或：

```text
待确认：xxx
```

每条需求至少生成：

- `REQ_ID`
- `需求名称`
- `开发方向`
- `需求类型`
- `需求描述`
- `关键参数`
- `适用条件`
- `输出/动作`
- `验收标准`
- `优先级`
- `状态`
- `待确认问题`

### 6. 输出 Excel

使用技能脚本执行分析：

```powershell
python skills\embedded-development-requirement-analysis\scripts\analyze_requirement.py --text "业务需求描述" -o requirement-analysis.xlsx
```

也可以从文件读取需求：

```powershell
python skills\embedded-development-requirement-analysis\scripts\analyze_requirement.py --text-file requirement.txt -o requirement-analysis.xlsx
```

脚本返回的 JSON 摘要包含：

- `primary_direction`
- `all_directions`
- `confidence`
- `scene_count`
- `requirement_count`
- `issue_count`
- `numeric_parameters`

### 7. 汇报给用户

向用户汇报以下内容：

- 识别到的主开发方向和次级方向
- 识别到的具体场景
- 生成的需求数量
- 识别到的数值参数
- 待确认问题数量
- Excel 文件路径

不要把 Excel 正文或全部需求行原样贴到对话里，只摘录关键结论和文件路径。

## 示例输入

```text
我们正在开发一款光伏并网逆变器，要求输出电流 THD 不超过 3%，功率因数支持 0.8 领先到 0.8 滞后，并满足 LVRT/HVRT。前端由 FPGA 完成电压电流采样、SNR 和硬件过流保护；DSP 负责并网控制和 MPPT；MCU 通过 Modbus RTU 和 MQTT 采集并存储历史数据和故障录波；Linux 侧提供 HMI，向云端上送运行数据，并在本地保存 30 天曲线。
```

预期分析结果：

- 主方向：DSP
- 次级方向：FPGA、MCU、Linux
- 场景：
  - DSP：电网并网指标、MPPT 与效率、LVRT/HVRT、控制环
  - FPGA：ADC 采样链路、硬件保护
  - MCU：外部通信协议、Flash 与本地存储、事件与故障追溯
  - Linux：HMI 与本地监控、云端通信、历史数据与系统服务
- Excel 输出：`requirement-analysis.xlsx`

## 输出约束

- 不把自动分析结果称为“正式需求契约”。
- 不把未确认的指标写成已确认指标。
- 不为多个方向强行选择唯一方向。
- 不把 Excel 分析结果当成代码开发输入的最终版本。
- 不代替用户决定优先级、签发或验收结论。