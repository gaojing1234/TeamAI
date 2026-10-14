from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = SKILL_DIR / "config" / "analysis_config.json"
DEFAULT_OUTPUT = Path.cwd() / "requirement-analysis.xlsx"

TEMPLATE_FIELDS = [
    "REQ_ID",
    "需求名称",
    "开发方向",
    "需求类型",
    "需求描述",
    "关键参数",
    "单位/量纲",
    "适用条件",
    "输入/触发",
    "输出/动作",
    "接口对象",
    "时序/响应",
    "数据格式",
    "精度/定点策略",
    "资源限制",
    "失败/降级策略",
    "验收标准",
    "依据标准",
    "来源",
    "优先级",
    "状态",
    "依赖REQ",
    "待确认问题",
    "责任人",
    "更新时间",
]


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r"[ \t]+", " ", text).strip()


def load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def find_keyword_hits(text: str, keywords: list[str]) -> list[str]:
    lowered = text.lower()
    return sorted({keyword for keyword in keywords if keyword.lower() in lowered})


def classify_requirement(text: str, config: dict) -> dict:
    text = normalize_text(text)
    directions = config["directions"]
    direction_hits = {}

    for direction, spec in directions.items():
        matched = find_keyword_hits(text, spec.get("keywords", []))
        if matched:
            direction_hits[direction] = {
                "score": len(matched),
                "keywords": matched,
            }

    if not direction_hits:
        return {
            "primary_direction": "待确认",
            "all_directions": [],
            "direction_hits": {},
            "confidence": 0.25,
            "scenes": [],
        }

    primary_direction = max(
        direction_hits,
        key=lambda name: (
            direction_hits[name]["score"],
            directions[name].get("label", name),
        ),
    )
    confidence = min(0.95, 0.45 + 0.05 * min(10, direction_hits[primary_direction]["score"]))

    scenes = []
    for direction in direction_hits:
        spec = directions[direction]
        matched_scenes = []
        for scene in spec.get("scenes", []):
            scene_hits = find_keyword_hits(text, scene.get("keywords", []))
            if scene_hits:
                matched_scenes.append((scene, scene_hits))

        if not matched_scenes and spec.get("scenes"):
            matched_scenes = [(spec["scenes"][0], [])]

        for scene, scene_hits in matched_scenes:
            scenes.append(
                {
                    "direction": direction,
                    "direction_label": spec.get("label", direction),
                    "scene": scene,
                    "scene_hits": scene_hits,
                }
            )

    return {
        "primary_direction": primary_direction,
        "all_directions": list(direction_hits),
        "direction_hits": direction_hits,
        "confidence": confidence,
        "scenes": scenes,
    }


def extract_numeric_parameters(text: str, config: dict) -> list[str]:
    values = []
    for pattern in config.get("numeric_patterns", []):
        try:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                value = re.sub(r"\s+", " ", match.group(0)).strip()
                if value:
                    values.append(value)
        except re.error:
            continue
    return sorted(set(values))


def build_open_issues(
    text: str,
    classification: dict,
    numeric_parameters: list[str],
    config: dict,
) -> list[dict]:
    issues = []
    seen = set()

    def add_issue(direction: str, question: str, impact: str, owner: str) -> None:
        key = (direction, question)
        if key in seen:
            return
        seen.add(key)
        issues.append(
            {
                "issue_id": f"ISSUE-{len(issues) + 1:03d}",
                "direction": direction,
                "question": question,
                "impact": impact,
                "owner": owner,
                "status": "待确认",
            }
        )

    if classification["primary_direction"] == "待确认":
        add_issue(
            "通用",
            "业务描述中未识别到明确的 DSP/FPGA/MCU/Linux 方向，请补充目标芯片、功能边界或系统架构。",
            "无法确定责任模块和交付范围。",
            "系统架构",
        )

    if not numeric_parameters:
        add_issue(
            classification["primary_direction"],
            "关键参数、数值范围和单位没有被识别到，请补充指标或性能约束。",
            "验收标准不可测。",
            "系统/算法",
        )
    else:
        add_issue(
            classification["primary_direction"],
            f"已识别到数值信息：{', '.join(numeric_parameters)}。请确认适用工况、测量方法和通过判据。",
            "数值脱离工况后无法作为验收依据。",
            "测试/系统",
        )

    if not re.search(r"(时序|响应|周期|延迟|超时|ms|us|ns|Hz|kHz|采样率|刷新|上送|重传)", text, re.IGNORECASE):
        add_issue(
            classification["primary_direction"],
            "响应时间、采样周期、通信周期或超时策略未明确。",
            "实时性和接口联调无法验收。",
            "系统/软件",
        )

    if not re.search(r"(接口|协议|RS485|CAN|Modbus|MQTT|TCP|IEC|DL/T|GOOSE|EtherCAT|EtherCAN|寄存器|点表)", text, re.IGNORECASE):
        add_issue(
            classification["primary_direction"],
            "接口对象、数据格式、寄存器/点表、超时和错误处理未明确。",
            "跨模块实现和联调会产生歧义。",
            "软件/协议",
        )

    if re.search(r"(THD|谐波|功率因数|cos\s*φ|LVRT|HVRT|MPPT|并网|电网)", text, re.IGNORECASE):
        add_issue(
            "DSP",
            "请确认电网指标的标准版本、测试工况、测量点、统计窗口和恢复策略。",
            "并网性能和保护验收无法闭环。",
            "系统/测试/标准",
        )

    if re.search(r"(ADC|采样率|SNR|抖动|同步采样|硬件保护|跳闸|GOOSE|EtherCAT|EtherCAN)", text, re.IGNORECASE):
        add_issue(
            "FPGA",
            "请确认采样链路指标、硬件保护响应时间、协议名称和时钟/同步约束。",
            "高速采样和保护时序可能与DSP控制不匹配。",
            "硬件/算法",
        )

    if re.search(r"(Flash|历史数据|事件记录|故障录波|录波|存储|本地曲线|30天)", text, re.IGNORECASE):
        add_issue(
            "MCU",
            "请确认存储变量、采样周期、容量、保留时长、分区、寿命和掉电保护策略。",
            "存储空间或Flash寿命可能不足，故障数据可能丢失。",
            "软件/存储",
        )

    if re.search(r"(HMI|云|云端|MQTT上送|IEC\s*104|DL/T\s*695|数据库|网关|OTA|历史曲线)", text, re.IGNORECASE):
        add_issue(
            "Linux",
            "请确认HMI/云协议的数据模型、上送周期、QoS、断线续传、查询性能、安全和升级策略。",
            "HMI、云端接入和长期数据服务无法验收。",
            "软件/系统",
        )

    for question in config.get("global_open_questions", []):
        add_issue(classification["primary_direction"], question, "影响需求范围和验收闭环。", "产品/系统")

    return issues


def build_requirement_rows(
    text: str,
    classification: dict,
    numeric_parameters: list[str],
    config: dict,
    prefix: str,
    generated_date: str,
) -> list[list[str]]:
    rows = []
    issue_counter = 0

    for scene_item in classification["scenes"]:
        direction = scene_item["direction"]
        scene = scene_item["scene"]
        issue_counter += 1
        issue_id = f"ISSUE-{issue_counter:03d}"
        key_parameters = "；".join(scene.get("key_parameters", []))
        if numeric_parameters:
            key_parameters = f"{key_parameters}；已识别数值：{', '.join(numeric_parameters)}"

        requirement_type = scene.get("requirement_type", "功能")
        priority = config.get("default_priority_by_type", {}).get(requirement_type, "P1")
        source_text = re.sub(r"\s+", " ", text)
        if len(source_text) > 240:
            source_text = source_text[:240] + "…"

        requirement_description = (
            f"业务输入：{source_text}\n"
            f"场景分析：{scene.get('analysis_focus', '')}"
        )

        rows.append(
            [
                f"{prefix}-{direction}-{len(rows) + 1:03d}",
                f"{direction}：{scene.get('name', '需求分析')}",
                direction,
                requirement_type,
                requirement_description,
                key_parameters or "待确认",
                "待确认：参数单位、量纲、缩放或协议编码",
                "待确认：适用工况、环境、产品边界和运行模式",
                "待确认：输入信号、触发事件、外部请求或异常条件",
                scene.get("analysis_focus", "待补充"),
                "待确认：内部或外部接口对象",
                "待确认：控制周期、采样周期、响应时间或超时",
                "待确认：数据类型、字长、端序、协议或文件格式",
                "待确认：定点/浮点策略、字长、溢出和饱和策略",
                "待确认：CPU、RAM、Flash、FPGA资源或带宽预算",
                "待确认：异常处理、保护动作、降级和数据保全策略",
                f"{scene.get('analysis_focus', '')}；补充量化判据、测试工况和证据格式。",
                "待确认：标准版本、客户规格或内部规范",
                "业务描述（自动分析）",
                priority,
                "草稿",
                "",
                issue_id,
                "",
                generated_date,
            ]
        )

    if not rows:
        rows.append(
            [
                f"{prefix}-TBD-001",
                "待确认方向",
                "待确认",
                "功能",
                f"业务输入：{source_text}\n场景分析：原始描述未命中明确开发方向，请补充目标芯片、功能边界或系统架构。",
                "待确认",
                "待确认",
                "待确认",
                "待确认",
                "待补充",
                "待确认",
                "待确认",
                "待确认",
                "待确认",
                "待确认",
                "待确认",
                "补充可测验收标准。",
                "待确认",
                "业务描述（自动分析）",
                "P2",
                "草稿",
                "",
                "ISSUE-001",
                "",
                generated_date,
            ]
        )

    return rows


def build_direction_rows(classification: dict) -> list[list[str]]:
    rows = []
    for direction in classification["all_directions"]:
        hits = classification["direction_hits"][direction]
        scenes = [
            item["scene"].get("name", "")
            for item in classification["scenes"]
            if item["direction"] == direction
        ]
        scene_text = "；".join(dict.fromkeys(scenes))
        rows.append(
            [
                direction,
                scene_text or "待确认",
                f"{hits['score']} 个关键词",
                ", ".join(hits["keywords"]),
                "已命中方向关键词，需结合业务上下文确认责任边界。",
                "见 02-需求总表",
                "关键参数、工况、接口、时序、异常策略和验收标准仍需补齐。",
            ]
        )
    return rows


def build_issue_rows(issues: list[dict], classification: dict) -> list[list[str]]:
    rows = []
    for issue in issues:
        rows.append(
            [
                issue["issue_id"],
                classification["primary_direction"],
                issue["direction"],
                issue["question"],
                issue["impact"],
                issue["owner"],
                issue["status"],
            ]
        )
    return rows


def build_summary_rows(
    text: str,
    classification: dict,
    numeric_parameters: list[str],
    output_path: Path,
) -> list[list[str]]:
    all_directions = "、".join(classification["all_directions"]) or "待确认"
    scenes = [
        f"{item['direction']} / {item['scene'].get('name', '')}"
        for item in classification["scenes"]
    ]
    return [
        ["项目", "内容"],
        ["技能名称", "嵌入式开发需求分析技能"],
        ["原始需求", re.sub(r"\s+", " ", text)],
        ["主开发方向", classification["primary_direction"]],
        ["次级开发方向", all_directions],
        ["识别置信度", f"{classification['confidence'] * 100:.0f}%"],
        ["具体场景", "；".join(scenes) or "待确认"],
        ["已识别数值参数", "；".join(numeric_parameters) or "未识别"],
        ["输出文件", str(output_path)],
        ["分析性质", "需求分析草稿，不等同于正式需求契约或代码生成结果。"],
    ]


def build_generation_rows(
    classification: dict,
    numeric_parameters: list[str],
    issues: list[dict],
    generated_at: str,
) -> list[list[str]]:
    keyword_lines = []
    for direction, hit in classification["direction_hits"].items():
        keyword_lines.append(f"{direction}: {', '.join(hit['keywords'])}")
    return [
        ["项目", "内容"],
        ["生成时间", generated_at],
        ["分析方法", "关键词命中 + 场景分类 + 模板字段补全"],
        ["方向命中", "；".join(keyword_lines) or "未命中明确方向"],
        ["数值参数", "；".join(numeric_parameters) or "未识别"],
        ["待确认问题数", str(len(issues))],
        ["脚本版本", "1.0.0"],
        ["模板来源", "docs/inverter-requirement-analysis-template.xlsx 的 02-需求总表字段"],
        ["使用提醒", "输出用于需求澄清和分析，不替代正式签发、设计或代码生成流程。"],
    ]


def col_letter(index: int) -> str:
    letters = ""
    while index:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def cell_ref(row: int, col: int) -> str:
    return f"{col_letter(col)}{row}"


def xml_text(value: object) -> str:
    return escape(str(value))


def build_sheet_xml(sheet: dict) -> str:
    rows = sheet["rows"]
    widths = sheet.get("widths", [])
    max_col = max((len(row) for row in rows), default=1)
    max_row = len(rows)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        f'<dimension ref="A1:{col_letter(max_col)}{max_row}"/>',
        '<sheetViews><sheetView workbookViewId="0">',
        '<pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/>',
        '<selection pane="bottomLeft" activeCell="A2" sqref="A2"/>',
        "</sheetView></sheetViews>",
        '<sheetFormatPr defaultRowHeight="15"/>',
    ]
    if widths:
        parts.append("<cols>")
        for index, width in enumerate(widths, start=1):
            parts.append(f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>')
        parts.append("</cols>")
    parts.append("<sheetData>")
    for row_index, row in enumerate(rows, start=1):
        height = 30 if row_index == 1 else 46
        parts.append(f'<row r="{row_index}" ht="{height}" customHeight="1">')
        for col_index, value in enumerate(row, start=1):
            ref = cell_ref(row_index, col_index)
            if row_index == 1:
                style = 1
            elif isinstance(value, str) and value.startswith("#"):
                style = 3
            else:
                style = 2
            parts.append(
                f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">'
                f"{xml_text(value)}</t></is></c>"
            )
        parts.append("</row>")
    parts.append("</sheetData>")
    parts.extend(
        [
            '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>',
            "</worksheet>",
        ]
    )
    return "".join(parts)


def build_styles_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><sz val="10"/><color theme="1"/><name val="Calibri"/><family val="2"/></font>
    <font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Calibri"/><family val="2"/></font>
    <font><i/><sz val="10"/><color rgb="FF595959"/><name val="Calibri"/><family val="2"/></font>
  </fonts>
  <fills count="4">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/><bgColor indexed="64"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F2"/><bgColor indexed="64"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/><diagonal/></border>
    <border>
      <left style="thin"><color rgb="FFB7B7B7"/></left>
      <right style="thin"><color rgb="FFB7B7B7"/></right>
      <top style="thin"><color rgb="FFB7B7B7"/></top>
      <bottom style="thin"><color rgb="FFB7B7B7"/></bottom>
      <diagonal/>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="4">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
    <xf numFmtId="0" fontId="2" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="left" vertical="top" wrapText="1"/></xf>
  </cellXfs>
  <cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>"""


def build_content_types(sheet_count: int) -> str:
    overrides = [
        f'<Override PartName="/xl/worksheets/sheet{idx}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for idx in range(1, sheet_count + 1)
    ]
    overrides.extend(
        [
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>',
        ]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + "".join(overrides)
        + "</Types>"
    )


def build_root_rels() -> str:
    return """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def build_workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{xml_text(name)}" sheetId="{idx}" r:id="rId{idx}"/>'
        for idx, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets>"
        '<calcPr calcId="191029" fullCalcOnLoad="1"/>'
        "</workbook>"
    )


def build_workbook_rels(sheet_count: int) -> str:
    rels = []
    for idx in range(1, sheet_count + 1):
        rels.append(
            f'<Relationship Id="rId{idx}" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            f'Target="worksheets/sheet{idx}.xml"/>'
        )
    rels.append(
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + "".join(rels)
        + "</Relationships>"
    )


def write_xlsx(path: Path, sheets: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = [sheet["name"] for sheet in sheets]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", build_content_types(len(sheets)))
        archive.writestr("_rels/.rels", build_root_rels())
        archive.writestr("xl/workbook.xml", build_workbook_xml(names))
        archive.writestr("xl/_rels/workbook.xml.rels", build_workbook_rels(len(sheets)))
        archive.writestr("xl/styles.xml", build_styles_xml())
        for idx, sheet in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{idx}.xml", build_sheet_xml(sheet))


def generate_analysis(text: str, config: dict, output_path: Path, prefix: str) -> dict:
    text = normalize_text(text)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    generated_date = datetime.now().strftime("%Y-%m-%d")
    classification = classify_requirement(text, config)
    numeric_parameters = extract_numeric_parameters(text, config)
    issues = build_open_issues(text, classification, numeric_parameters, config)
    requirement_rows = build_requirement_rows(
        text,
        classification,
        numeric_parameters,
        config,
        prefix,
        generated_date,
    )

    sheets = [
        {
            "name": "00-原始需求",
            "rows": [["原始业务描述"], [text]],
            "widths": [120],
            "row_height": 120,
        },
        {
            "name": "01-分析摘要",
            "rows": build_summary_rows(text, classification, numeric_parameters, output_path),
            "widths": [22, 100],
            "row_height": 42,
        },
        {
            "name": "02-需求总表",
            "rows": [TEMPLATE_FIELDS] + requirement_rows,
            "widths": [20, 28, 14, 16, 70, 34, 24, 34, 32, 48, 22, 26, 28, 32, 28, 32, 46, 24, 22, 12, 12, 20, 20, 16, 16],
            "row_height": 60,
        },
        {
            "name": "03-方向分析",
            "rows": [
                ["开发方向", "识别场景", "命中强度", "命中关键词", "分析说明", "关联工作表", "主要风险"],
            ]
            + build_direction_rows(classification),
            "widths": [16, 34, 18, 48, 52, 22, 44],
            "row_height": 46,
        },
        {
            "name": "04-待确认问题",
            "rows": [
                ["问题ID", "主方向", "涉及方向", "问题描述", "影响", "建议责任角色", "状态"],
            ]
            + build_issue_rows(issues, classification),
            "widths": [16, 16, 16, 70, 48, 24, 14],
            "row_height": 46,
        },
        {
            "name": "05-生成说明",
            "rows": build_generation_rows(classification, numeric_parameters, issues, generated_at),
            "widths": [22, 100],
            "row_height": 42,
        },
    ]
    write_xlsx(output_path, sheets)
    return {
        "output_path": output_path,
        "primary_direction": classification["primary_direction"],
        "all_directions": classification["all_directions"],
        "confidence": classification["confidence"],
        "scene_count": len(classification["scenes"]),
        "requirement_count": len(requirement_rows),
        "issue_count": len(issues),
        "numeric_parameters": numeric_parameters,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="嵌入式开发需求分析技能：分析业务描述并生成 Excel 需求分析结果"
    )
    parser.add_argument("text", nargs="?", help="业务需求描述")
    parser.add_argument("--text", dest="text_option", help="业务需求描述")
    parser.add_argument("--text-file", type=Path, help="从 UTF-8 文本文件读取业务需求描述")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUTPUT, help="输出 Excel 文件")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="分析配置文件")
    parser.add_argument("--prefix", default="REQ", help="REQ_ID 前缀")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if args.text_option and args.text:
        print("不能同时指定 --text 和位置参数需求描述。", file=sys.stderr)
        return 2
    if (args.text_option or args.text) and args.text_file:
        print("不能同时指定 --text/位置参数 和 --text-file。", file=sys.stderr)
        return 2
    if args.text_file:
        text = args.text_file.read_text(encoding="utf-8")
    elif args.text_option:
        text = args.text_option
    elif args.text:
        text = args.text
    else:
        print("请提供业务需求描述，例如：--text \"逆变器并网控制需求\"。", file=sys.stderr)
        return 2

    if not args.config.exists():
        print(f"配置文件不存在：{args.config}", file=sys.stderr)
        return 2

    config = load_config(args.config)
    result = generate_analysis(text, config, args.output, args.prefix)
    summary = {
        "output": str(result["output_path"]),
        "primary_direction": result["primary_direction"],
        "all_directions": result["all_directions"],
        "confidence": f"{result['confidence'] * 100:.0f}%",
        "scene_count": result["scene_count"],
        "requirement_count": result["requirement_count"],
        "issue_count": result["issue_count"],
        "numeric_parameters": result["numeric_parameters"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())