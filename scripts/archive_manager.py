#!/usr/bin/env python3
"""
RCHEP Automated Seminar & AI Session Archive Manager
Executes automatically via GitHub Actions or local scheduler.
"""

import sys, os, re
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "events.html")
INDEX_PATH = os.path.join(REPO_ROOT, "index.html")

def archive_hep_seminar():
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    col1_marker = '<!-- Column 1: High Energy Physics Seminars -->'
    c1_pos = html.find(col1_marker)
    if c1_pos == -1:
        print("Column 1 not found!")
        return False

    list_start = html.find('<div class="events-list">', c1_pos) + len('<div class="events-list">')
    item_start = html.find('<div class="event-item"', list_start)
    if item_start == -1:
        print("No upcoming seminar to archive!")
        return False

    item_end = html.find('</div>\n              </div>', item_start)
    if item_end == -1:
        item_end = html.find('</div>\n            </div>', item_start)
    item_end += len('</div>\n              </div>')

    event_block = html[item_start:item_end].strip()

    day_m = re.search(r'<div class="day"[^>]*>(\d+)</div>', event_block)
    month_m = re.search(r'<div class="month"[^>]*>(.*?)</div>', event_block)
    title_m = re.search(r'<h5[^>]*>(.*?)</h5>', event_block)

    day = day_m.group(1) if day_m else ""
    month = month_m.group(1) if month_m else ""
    title = title_m.group(1) if title_m else ""

    print(f"Archiving HEP seminar: {day} {month} — {title}")

    # Remove from upcoming
    new_html = html[:item_start] + html[item_end:]

    # Clean up styling for archive
    arch_event = re.sub(r'style="[^"]*border-right:[^"]*"', '', event_block)
    arch_event = re.sub(r'<span class="badge badge-green"[^>]*>.*?</span>', '', arch_event)
    arch_event = arch_event.replace('<h5', '<h4').replace('</h5>', '</h4>')

    # Insert at top of Current Year Archive
    arch_marker = '<!-- Current Academic Year Archive 1405-1406 (سخنرانی‌های انجام‌شده سال جاری) -->'
    arch_pos = new_html.find(arch_marker)
    if arch_pos != -1:
        arch_list = new_html.find('<div class="events-list">', arch_pos) + len('<div class="events-list">')
        new_html = new_html[:arch_list] + '\n          ' + arch_event + '\n' + new_html[arch_list:]

    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        f.write(new_html)

    update_index_hep()
    return True

def update_index_hep():
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        ev_html = f.read()

    col1_marker = '<!-- Column 1: High Energy Physics Seminars -->'
    c1 = ev_html.find(col1_marker)
    item_s = ev_html.find('<div class="event-item"', c1)
    if item_s == -1: return
    item_e = ev_html.find('</div>\n              </div>', item_s) + len('</div>\n              </div>')
    top_item = ev_html[item_s:item_e]

    day_m = re.search(r'<div class="day"[^>]*>(\d+)</div>', top_item)
    title_m = re.search(r'<h5[^>]*>(.*?)</h5>', top_item)
    spk_m = re.search(r'<span data-fa=\"👤 ([^\"]+)\"', top_item)

    if not (day_m and title_m and spk_m):
        return

    day = day_m.group(1).zfill(2)
    title = title_m.group(1)
    spk = spk_m.group(1)

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        idx_html = f.read()

    mon_start = idx_html.find('<!-- Mon (Active Seminar')
    if mon_start != -1:
        mon_end = idx_html.find('<!-- Tue', mon_start)
        mon_block = idx_html[mon_start:mon_end]
        mon_block = re.sub(r'<div class="cal-shamsi-date"[^>]*>\d+</div>', f'<div class="cal-shamsi-date" data-fa="{day}" data-en="{day}">{day}</div>', mon_block)
        mon_block = re.sub(r'<div class="cal-tip-title"[^>]*>.*?</div>', f'<div class="cal-tip-title" data-fa="{title}" data-en="{title}">{title}</div>', mon_block)
        mon_block = re.sub(r'<div class="cal-tip-speaker"[^>]*>.*?</div>', f'<div class="cal-tip-speaker" data-fa="👤 {spk}" data-en="👤 {spk}">👤 {spk}</div>', mon_block)
        idx_html = idx_html[:mon_start] + mon_block + idx_html[mon_end:]

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(idx_html)

def archive_ai_session():
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    p1_marker = '<!-- Part 1: Upcoming AI Sessions (برنامه‌های آینده هوشواره) -->'
    p1_pos = html.find(p1_marker)
    if p1_pos == -1:
        print("Part 1 of AI not found!")
        return False

    p2_marker = '<!-- Part 2: Held AI Sessions Archive'
    p2_pos = html.find(p2_marker)

    p1_block = html[p1_pos:p2_pos]

    feat_start = p1_block.find('<div style="background: var(--bg-main); border: 2px solid')
    if feat_start == -1:
        print("No featured upcoming AI session found!")
        return False

    feat_end = p1_block.find('</div>\n            </div>', feat_start)
    if feat_end == -1:
        feat_end = p1_block.find('</div>\n          </div>', feat_start)
    feat_end += len('</div>\n            </div>')

    session_box = p1_block[feat_start:feat_end]

    day_m = re.search(r'شنبه\s+(\d+)\s+([^\s—]+)', session_box)
    title_m = re.search(r'<strong[^>]*>(.*?)</strong>', session_box)
    spk_m = re.search(r'👤 ارائه دهنده:\s*([^<\(]+)', session_box)

    if not (day_m and title_m and spk_m):
        print("Could not parse AI session box!")
        return False

    day = day_m.group(1)
    month = day_m.group(2) + " 1405"
    title = title_m.group(1).strip()
    spk = spk_m.group(1).strip()

    print(f"Archiving AI session: {day} {month} — {title} by {spk}")

    arch_item = f'''            <!-- {day} {month} (برگزار شده) -->
            <div class="event-item" style="padding: 14px 18px; background: var(--bg-main); border: 1px solid var(--border-color); border-radius: var(--radius-md); margin-bottom: 12px;">
              <div class="event-date-box" style="min-width: 70px; padding: 6px;">
                <div class="day" style="font-size: 1.2rem;">{day}</div>
                <div class="month" data-fa="{month}" data-en="{month}">{month}</div>
              </div>
              <div class="event-info">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                  <span class="badge badge-purple" data-fa="نشست هوشواره" data-en="AI Session">نشست هوشواره</span>
                  <span class="badge badge-green" data-fa="برگزار شده" data-en="Completed">برگزار شده</span>
                </div>
                <h5 style="font-size: 0.98rem; font-weight: 700; margin-bottom: 4px;" data-fa="{title}" data-en="{title}">{title}</h5>
                <div class="event-meta" style="font-size: 0.82rem;">
                  <span data-fa="👤 ارائه دهنده: {spk}" data-en="👤 Speaker: {spk}">👤 ارائه دهنده: {spk}</span>
                  <span data-fa="🏛️ دانشکده فیزیک دانشگاه صنعتی شریف" data-en="🏛️ Physics Dept, Sharif University">🏛️ دانشکده فیزیک دانشگاه صنعتی شریف</span>
                  <span data-fa="🕒 شنبه {day} {day_m.group(2)} ساعت ۱۲:۳۰ | اتاق سمینار فیزیک انرژی بالا" data-en="🕒 Saturday 12:30 | RCHEP Seminar Room">🕒 شنبه {day} {day_m.group(2)} ساعت ۱۲:۳۰ | اتاق سمینار فیزیک انرژی بالا</span>
                </div>
              </div>
            </div>\n'''

    p2_list = html.find('</h5>\n              <span class="badge badge-purple"', p2_pos)
    if p2_list != -1:
        insert_pt = html.find('</div>', p2_list) + len('</div>\n')
        html = html[:insert_pt] + '\n' + arch_item + html[insert_pt:]

    with open(EVENTS_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    return True

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--auto"
    today = datetime.now()
    weekday = today.weekday() # Monday is 0, Saturday is 5

    if arg == "--hep" or (arg == "--auto" and weekday == 0):
        print("Running HEP seminar archive...")
        archive_hep_seminar()
    elif arg == "--ai" or (arg == "--auto" and weekday == 5):
        print("Running AI session archive...")
        archive_ai_session()
    else:
        print(f"No scheduled action for weekday {weekday} with arg {arg}")

if __name__ == "__main__":
    main()
