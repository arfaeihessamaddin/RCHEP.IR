#!/usr/bin/env python3
"""
Generates a styled, RTL-enabled Excel (.xlsx) file of RCHEP seminar subscribers
and uploads it to Sharif Cloud via WebDAV.
Zero external pip dependencies (built with standard library zipfile + XML).
"""

import os
import sys
import json
import zipfile
import urllib.request
import urllib.error
import xml.sax.saxutils as saxutils
from datetime import datetime

SUBSCRIBERS_JSON = os.path.join(os.path.dirname(__file__), "..", "data", "subscribers.json")

def gregorian_to_jalali(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy if gm > 2 else gy - 1
    days = 365 * gy + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400 - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + days % 31
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + (days - 186) % 30
    return jy, jm, jd

def format_iso_to_jalali(iso_str):
    if not iso_str:
        return "-"
    try:
        clean = iso_str.replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d} {dt.strftime('%H:%M')}"
    except Exception:
        return iso_str[:10] if len(iso_str) >= 10 else iso_str

def build_subscribers_xlsx(output_path, subscribers_data):
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

    rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

    wb_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""

    workbook = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="مشترکین خبرنامه" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>"""

    styles = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="3">
    <font><name val="Vazirmatn"/><sz val="11"/><color rgb="FF0F172A"/></font>
    <font><b/><name val="Vazirmatn"/><sz val="11"/><color rgb="FFFFFFFF"/></font>
    <font><b/><name val="Vazirmatn"/><sz val="14"/><color rgb="FF0369A1"/></font>
  </fonts>
  <fills count="5">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FF0284C7"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFDCFCE7"/></patternFill></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFFEF3C7"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/></border>
    <border>
      <left style="thin"><color rgb="FFE2E8F0"/></left>
      <right style="thin"><color rgb="FFE2E8F0"/></right>
      <top style="thin"><color rgb="FFE2E8F0"/></top>
      <bottom style="thin"><color rgb="FFE2E8F0"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="6">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
    <xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment horizontal="right" vertical="center"/></xf>
  </cellXfs>
</styleSheet>"""

    rows_xml = []
    # Title Row
    title_text = "فهرست مشترکین خبرنامه مرکز پژوهشی فیزیک انرژی بالا (RCHEP) — دانشگاه صنعتی شریف"
    rows_xml.append(f'<row r="1" ht="32" customHeight="1"><c r="A1" t="inlineStr" s="5"><is><t>{saxutils.escape(title_text)}</t></is></c></row>')

    # Header row at row 3
    headers = ["ردیف", "نام و نام خانوادگی", "نشانی رایانامه (ایمیل)", "وضعیت عضویت", "تاریخ ثبت درخواست", "تاریخ تأیید نهایی"]
    cols = ["A", "B", "C", "D", "E", "F"]
    h_cells = "".join([f'<c r="{cols[i]}3" t="inlineStr" s="1"><is><t>{saxutils.escape(h)}</t></is></c>' for i, h in enumerate(headers)])
    rows_xml.append(f'<row r="3" ht="26" customHeight="1">{h_cells}</row>')

    status_map = {
        "confirmed": ("تأییدشده (فعال)", 3),
        "pending": ("در انتظار تأیید ایمیل", 4),
        "unsubscribed": ("لغو عضویت", 0)
    }

    current_row = 4
    for idx, item in enumerate(subscribers_data, start=1):
        st_raw = item.get("status", "pending")
        st_label, st_style = status_map.get(st_raw, (st_raw, 0))
        name = item.get("name", "").strip() or "—"
        email = item.get("email", "").strip()
        created = format_iso_to_jalali(item.get("created_at", ""))
        confirmed = format_iso_to_jalali(item.get("confirmed_at", ""))

        row_cells = [
            f'<c r="A{current_row}" s="0"><v>{idx}</v></c>',
            f'<c r="B{current_row}" t="inlineStr" s="2"><is><t>{saxutils.escape(name)}</t></is></c>',
            f'<c r="C{current_row}" t="inlineStr" s="0"><is><t>{saxutils.escape(email)}</t></is></c>',
            f'<c r="D{current_row}" t="inlineStr" s="{st_style}"><is><t>{saxutils.escape(st_label)}</t></is></c>',
            f'<c r="E{current_row}" t="inlineStr" s="0"><is><t>{saxutils.escape(created)}</t></is></c>',
            f'<c r="F{current_row}" t="inlineStr" s="0"><is><t>{saxutils.escape(confirmed)}</t></is></c>'
        ]
        rows_xml.append(f'<row r="{current_row}" ht="22" customHeight="1">{"".join(row_cells)}</row>')
        current_row += 1

    sheet = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews>
    <sheetView tabSelected="1" workbookViewId="0" rightToLeft="1"/>
  </sheetViews>
  <sheetFormatPr defaultRowHeight="20"/>
  <cols>
    <col min="1" max="1" width="8" customWidth="1"/>
    <col min="2" max="2" width="28" customWidth="1"/>
    <col min="3" max="3" width="34" customWidth="1"/>
    <col min="4" max="4" width="22" customWidth="1"/>
    <col min="5" max="5" width="22" customWidth="1"/>
    <col min="6" max="6" width="22" customWidth="1"/>
  </cols>
  <sheetData>
    {''.join(rows_xml)}
  </sheetData>
</worksheet>"""

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet)

def _webdav_curl(user, password, *args):
    import subprocess
    cmd = ["curl", "--silent", "--show-error", "--user", f"{user}:{password}"] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _remote_exists(remote_file_url, user, password):
    """با درخواست PROPFIND بررسی می‌کند که فایل واقعاً روی ابر شریف ذخیره شده است."""
    res = _webdav_curl(user, password, "--request", "PROPFIND", "--header", "Depth: 0", remote_file_url)
    body = (res.stdout or "")
    if "207" in body or "subscribers.xlsx" in body or "<d:response" in body:
        return True
    head = _webdav_curl(user, password, "--head", remote_file_url)
    return "200" in head.stdout or "207" in head.stdout


def upload_to_sharif_cloud(local_file):
    url = os.environ.get("SHARIF_WEBDAV_URL", "").strip().strip("<>\"'").rstrip("/")
    user = os.environ.get("SHARIF_WEBDAV_USER", "").strip()
    password = os.environ.get("SHARIF_WEBDAV_PASSWORD", "").strip()

    if not url or not user or not password:
        print("Sharif Cloud WebDAV credentials not fully configured in environment. Skipping cloud upload.")
        return False

    # هم در پوشه اختصاصی تارنما و هم در ریشه ابر شریف بارگذاری می‌شود
    targets = [
        f"{url}/rchep-website/subscribers.xlsx",
        f"{url}/subscribers.xlsx",
    ]

    all_ok = True
    for remote_file_url in targets:
        print(f"Uploading {local_file} -> {remote_file_url} ...")
        res = _webdav_curl(user, password, "--fail", "--upload-file", local_file, remote_file_url)
        if res.returncode != 0:
            print(f"Failed to upload to Sharif Cloud ({remote_file_url}): {res.stderr}")
            all_ok = False
            continue

        if _remote_exists(remote_file_url, user, password):
            print(f"Successfully uploaded and verified subscribers.xlsx at {remote_file_url}")
        else:
            print(f"Uploaded but could not verify subscribers.xlsx at {remote_file_url}")
            all_ok = False

    return all_ok

def sync():
    if not os.path.exists(SUBSCRIBERS_JSON):
        print(f"File not found: {SUBSCRIBERS_JSON}")
        return

    with open(SUBSCRIBERS_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    subscribers_list = data.get("list", [])
    output_xlsx = os.path.join(os.path.dirname(__file__), "..", "data", "subscribers.xlsx")

    build_subscribers_xlsx(output_xlsx, subscribers_list)
    print(f"Built subscribers table: {output_xlsx} ({len(subscribers_list)} subscribers)")

    upload_to_sharif_cloud(output_xlsx)

if __name__ == "__main__":
    sync()
