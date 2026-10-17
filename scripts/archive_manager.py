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

    # Find the upcoming events list in Column 1
    col1_marker = '<!-- Column 1: High Energy Physics Seminars -->'
    c1_pos = html.find(col1_marker)
    if c1_pos == -1:
        print("Column 1 not found!")
        return False

    list_start = html.find('<div class="events-list">', c1_pos)
    if list_start == -1:
        return False
    list_start += len('<div class="events-list">')

    # Find the first event-item in upcoming
    item_start = html.find('<div class="event-item"', list_start)
    if item_start == -1:
        print("No upcoming seminar to archive!")
        return False

    # Find end of this event-item
    item_end = html.find('</div>\n              </div>', item_start)
    if item_end == -1:
        item_end = html.find('</div>\n            </div>', item_start)
    item_end += len('</div>\n              </div>')

    event_block = html[item_start:item_end].strip()

    # Extract date, speaker, title
    day_m = re.search(r'<div class="day"[^>]*>(\d+)</div>', event_block)
    month_m = re.search(r'<div class="month"[^>]*>(.*?)</div>', event_block)
    title_m = re.search(r'<h5[^>]*>(.*?)</h5>', event_block)

    day = day_m.group(1) if day_m else ""
    month = month_m.group(1) if month_m else ""
    title = title_m.group(1) if title_m else ""

    print(f"Archiving HEP seminar: {day} {month} — {title}")

    # Remove from upcoming
    new_html = html[:item_start] + html[item_end:]

    # Clean up styling for archive display (remove highlighted border/bg)
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

    # Update index.html preview
    update_index_hep()
    return True

def update_index_hep():
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        ev_html = f.read()

    # Read the new top upcoming seminar
    col1_marker = '<!-- Column 1: High Energy Physics Seminars -->'
    c1 = ev_html.find(col1_marker)
    item_s = ev_html.find('<div class="event-item"', c1)
    item_e = ev_html.find('</div>\n              </div>', item_s) + len('</div>\n              </div>')
    top_item = ev_html[item_s:item_e]

    day_m = re.search(r'<div class="day"[^>]*>(\d+)</div>', top_item)
    month_m = re.search(r'<div class="month"[^>]*>(.*?)</div>', top_item)
    title_m = re.search(r'<h5[^>]*>(.*?)</h5>', top_item)
    spk_m = re.search(r'<span data-fa=\"👤 ([^\"]+)\"', top_item)
    aff_m = re.search(r'<span data-fa=\"🏛️ ([^\"]+)\"', top_item)

    if not (day_m and title_m and spk_m):
        return

    day = day_m.group(1)
    month = month_m.group(1) if month_m else "مهر 1405"
    title = title_m.group(1)
    spk = spk_m.group(1)
    aff = aff_m.group(1) if aff_m else "دانشگاه صنعتی شریف (SUT)"

    with open(INDEX_PATH, "r", encoding="utf-8") as f:
        idx_html = f.read()

    # Update calendar Monday event
    idx_html = re.sub(r'<div class="cal-shamsi-date"[^>]*>\d+</div>(\s*<!-- Mon)', f'<div class="cal-shamsi-date" data-fa="{day}" data-en="{day}">{day}</div>\\1', idx_html)
    idx_html = re.sub(r'<div class="cal-tip-title"[^>]*>.*?</div>(\s*<div class="cal-tip-speaker")', f'<div class="cal-tip-title" data-fa="{title}" data-en="{title}">{title}</div>\\1', idx_html)
    idx_html = re.sub(r'<div class="cal-tip-speaker"[^>]*>.*?</div>(\s*<div class="cal-tip-venue")', f'<div class="cal-tip-speaker" data-fa="👤 {spk}" data-en="👤 {spk}">👤 {spk}</div>\\1', idx_html)

    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write(idx_html)

def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "--auto"
    today = datetime.now()
    weekday = today.weekday() # Monday is 0, Saturday is 5

    if arg == "--hep" or (arg == "--auto" and weekday == 0):
        print("Running HEP seminar archive...")
        archive_hep_seminar()
    elif arg == "--ai" or (arg == "--auto" and weekday == 5):
        print("Running AI session archive...")
        # Handled in events.html
    else:
        print(f"No scheduled action for weekday {weekday} with arg {arg}")

if __name__ == "__main__":
    main()
