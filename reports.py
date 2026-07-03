from __future__ import annotations

import html
import textwrap
import zipfile
from pathlib import Path
from typing import Any

from .config import EXPORT_DIR
from .db import connect


def ensure_report_exports(report_id: str) -> dict[str, str]:
    from .engine import get_report

    report = get_report(report_id)
    if not report:
        raise ValueError("Report not found")

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = EXPORT_DIR / f"{report_id}.pdf"
    excel_path = EXPORT_DIR / f"{report_id}.xlsx"

    write_pdf_report(pdf_path, report)
    write_xlsx_report(excel_path, report)

    with connect() as conn:
        conn.execute(
            "UPDATE reports SET pdf_path = ?, excel_path = ? WHERE id = ?",
            (str(pdf_path), str(excel_path), report_id),
        )

    return {"pdf": str(pdf_path), "excel": str(excel_path)}


def report_text_lines(report: dict[str, Any]) -> list[str]:
    lines = [
        f"{report['title_cn']} / {report['title_en']}",
        f"日期 Date: {report['as_of']}    风险 Risk: {report['risk_level']}    置信度 Confidence: {report['confidence']}%",
        "",
        "主线 Main Thesis",
        report["thesis_cn"],
        report["thesis_en"],
        "",
        "因果链 Causal Chain",
    ]
    for block in [report["chain_cn"], report["chain_en"]]:
        for line in str(block).splitlines():
            lines.extend(wrap_text(line, 54))
    lines.extend(["", "具体决策 Specific Decisions"])
    for decision in report.get("decisions", []):
        lines.extend(
            wrap_text(
                (
                    f"[{decision['action_cn']} {decision['action']}] {decision['symbol']} "
                    f"{decision['name_cn']} / {decision['name_en']} | "
                    f"目标 Target {float(decision['target_weight']) * 100:.1f}% | "
                    f"金额 Amount {float(decision['amount_cny']):,.0f} CNY | "
                    f"建议价 Price {float(decision['price']):.4f} | "
                    f"止损 Stop {float(decision['stop_loss']):.4f} | "
                    f"止盈 Take {float(decision['take_profit']):.4f} | "
                    f"持有 {decision['holding_days']} days | 置信度 {decision['confidence']}%"
                ),
                76,
            )
        )
        lines.extend(wrap_text(f"触发 Trigger: {decision['trigger_cn']} / {decision['trigger_en']}", 76))
        lines.extend(wrap_text(f"失效 Invalidation: {decision['invalidation_cn']} / {decision['invalidation_en']}", 76))
        lines.append("")
    lines.extend(
        [
            "边界 Boundary",
            "本报告仅用于模拟投资研究；系统不会发送真实券商订单。",
            "This report is for simulated investment research only; no real broker order is sent.",
        ]
    )
    return lines


def wrap_text(text: str, width: int) -> list[str]:
    if len(text) <= width:
        return [text]
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return [text[i : i + width] for i in range(0, len(text), width)]
    return textwrap.wrap(text, width=width) or [text]


def write_pdf_report(path: Path, report: dict[str, Any]) -> None:
    lines = report_text_lines(report)
    chunks = [lines[i : i + 42] for i in range(0, len(lines), 42)]
    if not chunks:
        chunks = [["No content"]]

    objects: list[bytes | None] = [None]

    def add_object(body: bytes) -> int:
        objects.append(body)
        return len(objects) - 1

    catalog_id = add_object(b"")
    pages_id = add_object(b"")
    cid_font_id = add_object(
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 2 >> "
        b"/DW 1000 >>"
    )
    font_id = add_object(
        f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
        f"/Encoding /UniGB-UCS2-H /DescendantFonts [{cid_font_id} 0 R] >>".encode("ascii")
    )

    page_ids: list[int] = []
    for page_lines in chunks:
        stream = build_pdf_text_stream(page_lines)
        content_id = add_object(
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        page_id = add_object(
            f"<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>".encode("ascii")
        )
        page_ids.append(page_id)

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[pages_id] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")
    objects[catalog_id] = f"<< /Type /Catalog /Pages {pages_id} 0 R >>".encode("ascii")

    write_pdf_objects(path, objects)


def build_pdf_text_stream(lines: list[str]) -> bytes:
    commands = ["BT", "/F1 9 Tf", "42 800 Td"]
    for index, line in enumerate(lines):
        if index == 0:
            commands.append("/F1 12 Tf")
        elif index == 1:
            commands.append("/F1 9 Tf")
        encoded = line.encode("utf-16-be", errors="replace").hex().upper()
        commands.append(f"<{encoded}> Tj")
        commands.append("0 -16 Td")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def write_pdf_objects(path: Path, objects: list[bytes | None]) -> None:
    payload = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    for object_id in range(1, len(objects)):
        body = objects[object_id] or b""
        offsets.append(len(payload))
        payload += f"{object_id} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_pos = len(payload)
    payload += f"xref\n0 {len(objects)}\n".encode("ascii")
    payload += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        payload += f"{offset:010d} 00000 n \n".encode("ascii")
    payload += (
        f"trailer << /Size {len(objects)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
    ).encode("ascii")
    path.write_bytes(payload)


def write_xlsx_report(path: Path, report: dict[str, Any]) -> None:
    summary_rows = [
        ["Field", "Value"],
        ["Report ID", report["id"]],
        ["Date", report["as_of"]],
        ["Risk Level", report["risk_level"]],
        ["Regime", report["regime"]],
        ["Confidence", f"{report['confidence']}%"],
        ["CN Thesis", report["thesis_cn"]],
        ["EN Thesis", report["thesis_en"]],
        ["CN Chain", report["chain_cn"]],
        ["EN Chain", report["chain_en"]],
        ["Boundary", "Simulation only. No real broker order was sent."],
    ]
    decision_rows = [
        [
            "Symbol",
            "Name CN",
            "Name EN",
            "Action",
            "Target Weight",
            "Current Weight",
            "Amount CNY",
            "Price",
            "Stop Loss",
            "Take Profit",
            "Holding Days",
            "Confidence",
            "Status",
            "Trigger CN",
            "Trigger EN",
            "Invalidation CN",
            "Invalidation EN",
        ]
    ]
    for decision in report.get("decisions", []):
        decision_rows.append(
            [
                decision["symbol"],
                decision["name_cn"],
                decision["name_en"],
                decision["action"],
                f"{float(decision['target_weight']) * 100:.2f}%",
                f"{float(decision['current_weight']) * 100:.2f}%",
                f"{float(decision['amount_cny']):.2f}",
                f"{float(decision['price']):.4f}",
                f"{float(decision['stop_loss']):.4f}",
                f"{float(decision['take_profit']):.4f}",
                str(decision["holding_days"]),
                f"{decision['confidence']}%",
                decision["status"],
                decision["trigger_cn"],
                decision["trigger_en"],
                decision["invalidation_cn"],
                decision["invalidation_en"],
            ]
        )

    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types_xml())
        archive.writestr("_rels/.rels", root_rels_xml())
        archive.writestr("xl/workbook.xml", workbook_xml())
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels_xml())
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml(summary_rows))
        archive.writestr("xl/worksheets/sheet2.xml", sheet_xml(decision_rows))


def content_types_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""


def root_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""


def workbook_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Summary" sheetId="1" r:id="rId1"/>
    <sheet name="Decisions" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>"""


def workbook_rels_xml() -> str:
    return """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>"""


def sheet_xml(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_idx, row in enumerate(rows, start=1):
        cells = []
        for col_idx, value in enumerate(row, start=1):
            cell_ref = f"{column_name(col_idx)}{row_idx}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{xml_escape(str(value))}</t></is></c>'
            )
        xml_rows.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData>"
        + "".join(xml_rows)
        + "</sheetData></worksheet>"
    )


def column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def xml_escape(value: str) -> str:
    return html.escape(value, quote=False).replace("\n", "&#10;")
