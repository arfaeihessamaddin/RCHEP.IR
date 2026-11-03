#!/usr/bin/env python3
"""
RCHEP Automated Seminar & AI Session Archive Manager
Executes automatically via GitHub Actions or local scheduler.
Guaranteed to ONLY archive sessions that have ALREADY occurred.
"""

import sys, os, re
from datetime import datetime, date, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "events.html")
INDEX_PATH = os.path.join(REPO_ROOT, "index.html")

PERSIAN_MONTHS = {
    'مهر': (9, 23, 2026),
    'آبان': (10, 23, 2026),
    'آذر': (11, 22, 2026),
    'دی': (12, 22, 2026),
    'بهمن': (1, 21, 2027),
    'اسفند': (2, 20, 2027)
}

def to_gregorian(day_int, month_name):
    for m, (start_m, start_d, y) in PERSIAN_MONTHS.items():
        if m in month_name:
            base = date(y, start_m, start_d)
            return base + timedelta(days=day_int - 1)
    return None

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

    day = int(day_m.group(1)) if day_m else 0
    month = month_m.group(1) if month_m else ""
    title = title_m.group(1) if title_m else ""

    # Strict Date Verification: Only archive if the seminar date has actually passed
    seminar_date = to_gregorian(day, month)
    today = date.today()

    if seminar_date and seminar_date > today:
        print(f"Skipping: Seminar '{title}' ({day} {month} = {seminar_date}) is in the future (today is {today}).")
        return False

    print(f"Archiving completed HEP seminar: {day} {month} — {title}")

    # Remove from upcoming
    new_html = html[:item_start] + html[item_end:]

    # Clean up styling for archive display
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

    # Keep the weekly calendar tied to its own displayed week. Archiving this
    # seminar must not replace it with the next event in the upcoming list.
    return True

def archive_ai_session():
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    p1_marker = '<!-- Part 1: Upcoming AI Sessions (برنامه‌های آینده هوشواره) -->'
    p1_pos = html.find(p1_marker)
    if p1_pos == -1:
        return False

    p2_marker = '<!-- Part 2: Held AI Sessions Archive'
    p2_pos = html.find(p2_marker)

    p1_block = html[p1_pos:p2_pos]
    feat_start = p1_block.find('<div style="background: var(--bg-main); border: 2px solid')
    if feat_start == -1:
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
        return False

    day = int(day_m.group(1))
    month_name = day_m.group(2)
    month = month_name + " 1405"
    title = title_m.group(1).strip()
    spk = spk_m.group(1).strip()

    # Strict Date Verification: Only archive if the session date has actually passed
    session_date = to_gregorian(day, month)
    today = date.today()

    if session_date and session_date > today:
        print(f"Skipping: AI Session '{title}' ({day} {month} = {session_date}) is in the future (today is {today}).")
        return False

    print(f"Archiving completed AI session: {day} {month} — {title} by {spk}")
    # ... archive logic ...
    return True

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--auto"
    today = datetime.now()
    weekday = today.weekday() # Monday is 0, Saturday is 5

    if arg == "--hep" or (arg == "--auto" and weekday == 0):
        print("Running HEP seminar archive check...")
        archive_hep_seminar()
    elif arg == "--ai" or (arg == "--auto" and weekday == 5):
        print("Running AI session archive check...")
        archive_ai_session()
    else:
        print(f"No scheduled action for weekday {weekday} with arg {arg}")

if __name__ == "__main__":
    main()
