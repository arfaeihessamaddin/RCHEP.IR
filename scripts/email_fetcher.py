#!/usr/bin/env python3
"""
RCHEP Automated Email Listener & Website Synchronizer
Connects to Gmail via IMAP, inspects emails from official seminar coordinators
(Niloofar Vardian & Pouya / Ebrahim Siri), extracts poster attachments, titles,
and abstracts, and updates events.html & index.html automatically.
"""

import os, sys, re, email, imaplib
from email.header import decode_header
from datetime import datetime

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "events.html")
INDEX_PATH = os.path.join(REPO_ROOT, "index.html")
EVENTS_IMG_DIR = os.path.join(REPO_ROOT, "assets", "images", "events")

os.makedirs(EVENTS_IMG_DIR, exist_ok=True)

def decode_mime(h):
    if not h: return ""
    parts = decode_header(h)
    res = ""
    for p, enc in parts:
        if isinstance(p, bytes):
            res += p.decode(enc or "utf-8", errors="ignore")
        else:
            res += str(p)
    return res

def fetch_and_update():
    user = os.environ.get("GMAIL_USER")
    pwd = os.environ.get("GMAIL_APP_PASSWORD")

    if not user or not pwd:
        print("Missing GMAIL_USER or GMAIL_APP_PASSWORD environment variables.")
        return False

    print(f"Connecting to Gmail for {user}...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(user, pwd)
        mail.select("inbox")
    except Exception as e:
        print(f"Failed to login to Gmail: {e}")
        return False

    # Check for seminar announcement emails from Niloofar Vardian
    _, vardian_msgs = mail.search(None, '(FROM "niloofarvardian@gmail.com")')
    v_ids = vardian_msgs[0].split()

    updated = False
    if v_ids:
        # Check last 5 messages
        for mid in v_ids[-5:]:
            _, data = mail.fetch(mid, "(RFC822)")
            msg = email.message_from_bytes(data[0][1])
            subject = decode_mime(msg.get("Subject"))
            
            if "سمینار" not in subject:
                continue

            # Extract body and attachments
            body_text = ""
            poster_filename = None

            for part in msg.walk():
                ctype = part.get_content_type()
                cdisp = str(part.get("Content-Disposition"))
                fn = decode_mime(part.get_filename())

                if fn and any(fn.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png"]):
                    save_name = re.sub(r"[^\w\.-]", "_", fn)
                    poster_path = os.path.join(EVENTS_IMG_DIR, save_name)
                    with open(poster_path, "wb") as f:
                        f.write(part.get_payload(decode=True))
                    poster_filename = save_name
                    print(f"Saved attached poster: {poster_filename}")

                elif ctype == "text/plain" and not body_text:
                    body_text = part.get_payload(decode=True).decode("utf-8", errors="ignore")

            # Parse details from body
            if body_text and "ارائه‌دهنده" in body_text or "ارائه دهنده" in body_text:
                res = parse_seminar_text(body_text, subject)
                if res:
                    print(f"Found parsed seminar details: {res['title']} by {res['speaker']}")
                    if update_seminar_in_site(res, poster_filename):
                        updated = True

    mail.logout()
    return updated

def parse_seminar_text(body, subject):
    lines = [l.strip() for l in body.splitlines() if l.strip()]
    details = {
        "title": "",
        "speaker": "",
        "affiliation": "دانشگاه صنعتی شریف (SUT)",
        "time": "۱۳:۳۰",
        "date_str": "",
        "day": "",
        "month": "",
        "abstract": "",
        "venue": "اتاق سمینار مرکز پژوهشی فیزیک انرژی بالا"
    }

    # Find speaker
    for i, line in enumerate(lines):
        clean = line.replace("*", "").strip()
        if "ارائه‌دهنده" in clean or "ارائه دهنده" in clean or "سخنران" in clean:
            parts = clean.split(":")
            if len(parts) > 1 and parts[1].strip():
                details["speaker"] = parts[1].strip()
            elif i + 1 < len(lines):
                details["speaker"] = lines[i+1].replace("*", "").strip()

        if "چکیده" in clean:
            # Next paragraph is abstract
            abs_lines = []
            for j in range(i+1, min(len(lines), i+15)):
                if "مکان" in lines[j] or "لینک" in lines[j] or "ساعت" in lines[j]:
                    break
                abs_lines.append(lines[j].replace("*", "").strip())
            details["abstract"] = " ".join(abs_lines).strip()

        if "تاریخ" in clean:
            for j in range(i, min(len(lines), i+3)):
                dm = re.search(r"(\d{1,2})\s*(مهر|آبان|آذر|دی|بهمن|اسفند|فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور)", lines[j])
                if dm:
                    details["day"] = dm.group(1).zfill(2)
                    details["month"] = dm.group(2) + " 1405"
                    break

    # Title is usually right below header line
    for i, line in enumerate(lines):
        if "سمینار" in line and ("مرکز" in line or "دانشکده" in line):
            for k in range(i+1, min(len(lines), i+5)):
                candidate = lines[k].replace("*", "").strip()
                if candidate and not any(w in candidate for w in ["دانشگاه", "ارائه‌دهنده", "زمان", "تاریخ"]):
                    details["title"] = candidate
                    break
            break

    if details["title"] and details["speaker"]:
        return details
    return None

def update_seminar_in_site(details, poster_filename):
    with open(EVENTS_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # Check if title already present
    if details["title"] in html:
        print("Seminar title already updated on events.html.")
        return False

    day = details["day"]
    if not day:
        return False

    # Find the upcoming event item for this day
    pattern = rf'(<div class="day"[^>]*>{day}</div>[\s\S]*?<div class="event-info">[\s\S]*?<h5[^>]*>)(.*?)(</h5>)'
    m = re.search(pattern, html)
    if m:
        html = html[:m.start(2)] + details["title"] + html[m.end(2):]
        # Also update data-fa and data-en on h5
        html = re.sub(rf'<h5([^>]*)>{re.escape(details["title"])}</h5>', f'<h5\\1 data-fa="{details["title"]}" data-en="{details["title"]}">{details["title"]}</h5>', html)
        with open(EVENTS_PATH, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Successfully updated seminar for day {day} in events.html!")
        return True

    return False

if __name__ == "__main__":
    changed = fetch_and_update()
    print("Done. Changes made:", changed)
