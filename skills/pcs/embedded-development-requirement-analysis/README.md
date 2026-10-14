# 嵌入式开发需求分析技能

这是一个面向业务需求澄清的本地技能包。输入一段自然语言描述后，技能会：

- 识别需求属于 DSP、FPGA、MCU、Linux 的哪些开发方向
- 识别具体场景和关键词
- 提取可见的数值参数
- 找出缺失的工况、接口、时序、存储、验收信息
- 按 `docs/inverter-requirement-analysis-template.xlsx` 的主表字段生成 Excel 分析结果

## 目录

```text
skills/embedded-development-requirement-analysis/
├── SKILL.md
├── README.md
├── config/
│   └── analysis_config.json
├── scripts/
│   └── analyze_requirement.py
└── examples/
    └── sample_input.txt
```

## 快速使用

### 直接传入需求描述

```powershell
python skills\embedded-development-requirement-analysis\scripts\analyze_requirement.py --text "逆变器需要支持 THD<=3% 和 LVRT" -o requirement-analysis.xlsx
```

### 从文本文件读取

```powershell
python skills\embedded-development-requirement-analysis\scripts\analyze_requirement.py --text-file skills\embedded-development-requirement-analysis\examples\sample_input.txt -o sample-analysis.xlsx
```

## 输出文件结构

生成的 Excel 包含以下工作表：

1. `00-原始需求`
2. `01-分析摘要`
3. `02-需求总表`
4. `03-方向分析`
5. `04-待确认问题`
6. `05-生成说明`

`02-需求总表` 使用模板中的 25 个字段，字段名称和 `docs/inverter-requirement-analysis-template.xlsx` 保持一致。

## 维护说明

方向和场景规则位于 `config/analysis_config.json`。

如果团队新增了：

- 新开发方向
- 新协议
- 新场景
- 新验收指标

建议先修改配置文件，再运行脚本验证输出，避免把业务规则散落在 SKILL.md 中。

## 边界

这是需求分析草稿工具，不是正式需求契约生成器，也不负责代码生成。正式需求签发、设计和代码开发应继续走团队规定的需求与研发流程。