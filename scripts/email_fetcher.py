#!/usr/bin/env python3
"""Fetch approved RCHEP seminar announcements and update their event cards."""

import os
import re
import html
import email
import email.utils
import imaplib
import hashlib
from email.header import decode_header
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_PATH = os.path.join(REPO_ROOT, "events.html")
EVENTS_IMG_DIR = os.path.join(REPO_ROOT, "assets", "images", "events")
os.makedirs(EVENTS_IMG_DIR, exist_ok=True)

APPROVED_SENDERS = ("niloofarvardian@gmail.com", "pouya.si74@gmail.com")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
PERSIAN_MONTHS = "فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند"


def decode_mime(value):
    if not value:
        return ""
    output = []
    for part, encoding in decode_header(value):
        if isinstance(part, bytes):
            output.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            output.append(str(part))
    return "".join(output)


def normalize_text(value):
    value = value or ""
    return (value.replace("\u200c", "").replace("\u200f", "")
            .replace("ي", "ی").replace("ك", "ک").replace("\xa0", " ")
            .strip())


def safe_filename(value):
    value = re.sub(r"[^\w.-]+", "-", value, flags=re.UNICODE).strip("-.")
    return value[:100] or "poster"


def extract_body(message):
    plain_parts = []
    html_parts = []
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if part.get_filename():
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        charset = part.get_content_charset() or "utf-8"
        text = payload.decode(charset, errors="replace")
        if part.get_content_type() == "text/plain":
            plain_parts.append(text)
        elif part.get_content_type() == "text/html":
            html_parts.append(re.sub(r"<[^>]+>", " ", text))
    return "\n".join(plain_parts or html_parts)

ATTACHMENT_LINE = re.compile(
    r"^\[?\s*(?:image|cid|attachment|inline)\s*[:\-]?[^\]]*\]?$"
    r"|^[\w\-. ]+\.(?:jpe?g|png|gif|bmp|webp|tiff?|pdf|docx?|pptx?|xlsx?|zip|rar|mp4)\s*$",
    re.I,
)


def is_noise_line(line):
    """سطرهای شبه‌پیوست/نشانی را نادیده می‌گیرد تا عنوان سمینار ناخوانا نشود."""
    compact = normalize_text(line).strip()
    if not compact:
        return True
    if ATTACHMENT_LINE.match(compact):
        return True
    if re.match(r"^(?:https?://|www\.|mailto:)", compact, re.I):
        return True
    if re.match(r"^<[^>]+>$", compact) or re.match(r"^[^@\s]+@[^@\s]+$", compact):
        return True
    return False


def parse_seminar_text(body, subject):
    raw_lines = [line.strip() for line in body.splitlines() if line.strip()]
    lines = [normalize_text(line).strip("*• \t") for line in raw_lines]
    normalized_body = normalize_text(body)
    details = {
        "title": "",
        "speaker": "",
        "affiliation": "",
        "abstract": "",
        "day": "",
        "month": "",
        "year": "1405",
        "time": "۱۳:۳۰",
        "location": "اتاق سمینار RCHEP (دانشکده فیزیک) + مجازی",
    }

    # Date may be in the subject or body. Accept Persian and Arabic numerals.
    date_source = normalize_text(subject + "\n" + body)
    digit_map = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
    date_source = date_source.translate(digit_map)
    date_match = re.search(rf"(\d{{1,2}})\s*({PERSIAN_MONTHS})", date_source)
    if date_match:
        details["day"] = date_match.group(1).zfill(2)
        details["month"] = date_match.group(2)
        year_match = re.search(r"(14\d{2})", date_source)
        if year_match:
            details["year"] = year_match.group(1)

    # Explicit title labels take precedence.
    for line in lines:
        match = re.match(r"^(?:عنوان|موضوع|title)\s*[:：]\s*(.+)$", line, re.I)
        if match:
            candidate = match.group(1).strip()
            if candidate and not is_noise_line(candidate):
                details["title"] = candidate
                break

    # Otherwise, the title is normally the first substantive line after the seminar header.
    if not details["title"]:
        for index, line in enumerate(lines):
            compact = normalize_text(line)
            if "سمینار" in compact and ("مرکز" in compact or "دانشگاه" in compact):
                for candidate in lines[index + 1:index + 7]:
                    if candidate and not is_noise_line(candidate) and not re.search(
                        r"ارائهدهنده|سخنران|زمان|تاریخ|مکان|چکیده|دانشگاه صنعتی شریف",
                        normalize_text(candidate), re.I
                    ):
                        details["title"] = candidate
                        break
                break

    # Speaker labels tolerate joined, spaced, and half-spaced Persian forms.
    for index, line in enumerate(lines):
        compact = normalize_text(line)
        if re.search(r"(?:ارائهدهنده|سخنران|ارائهکننده)", compact):
            value = re.split(r"[:：]", line, maxsplit=1)
            if len(value) > 1 and value[1].strip():
                details["speaker"] = value[1].strip()
            elif index + 1 < len(lines):
                details["speaker"] = lines[index + 1]
            break

    # Affiliation, when explicitly present.
    for index, line in enumerate(lines):
        if re.search(r"وابستگی|دانشگاه|پژوهشگاه|affiliation", normalize_text(line), re.I):
            if ":" in line or "：" in line:
                details["affiliation"] = re.split(r"[:：]", line, maxsplit=1)[-1].strip()
            elif index + 1 < len(lines) and not any(k in lines[index + 1] for k in ["چکیده", "ساعت", "مکان"]):
                details["affiliation"] = lines[index + 1].strip()
            break

    for index, line in enumerate(lines):
        if "چکیده" in normalize_text(line):
            abstract_lines = []
            for candidate in lines[index + 1:index + 16]:
                if re.search(r"مکان|لینک|ساعت|زمان|تاریخ", normalize_text(candidate)):
                    break
                abstract_lines.append(candidate)
            details["abstract"] = " ".join(abstract_lines).strip()
            break

    # Location, when explicitly present
    for line in lines:
        match = re.match(r"^(?:مکان|محل برگزاری|محل|venue|location)\s*[:：]\s*(.+)$", line, re.I)
        if match:
            loc_val = match.group(1).strip()
            if loc_val and "جناب" not in loc_val:
                details["location"] = loc_val
            break

    # Time, when explicitly present
    for line in lines:
        match = re.match(r"^(?:ساعت|زمان برگزاری|time)\s*[:：]\s*(.+)$", line, re.I)
        if match:
            time_val = match.group(1).strip()
            if time_val:
                details["time"] = time_val
            break

    if details["title"] and details["speaker"] and details["day"] and details["month"]:
        return details
    return None


def save_posters(message, day, month):
    saved = {}
    for part in message.walk():
        filename = decode_mime(part.get_filename())
        if not filename or not filename.lower().endswith(IMAGE_EXTENSIONS):
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue

        lower_name = normalize_text(filename).lower()
        if re.search(r"(^|[^a-z])fa([^a-z]|$)|فارسی|persian", lower_name):
            language = "fa"
        elif re.search(r"(^|[^a-z])en([^a-z]|$)|english|انگلیسی", lower_name):
            language = "en"
        else:
            # Do not guess a language when the attachment name gives no clue.
            language = "unclassified"

        extension = os.path.splitext(filename)[1].lower()
        if extension not in IMAGE_EXTENSIONS:
            continue
        month_slug = {"فروردین": "farvardin", "اردیبهشت": "ordibehesht", "خرداد": "khordad", "تیر": "tir", "مرداد": "mordad", "شهریور": "shahrivar", "مهر": "mehr", "آبان": "aban", "آذر": "azar", "دی": "dey", "بهمن": "bahman", "اسفند": "esfand"}.get(month, safe_filename(month))
        stem = f"{day}-{month_slug}-{language}"
        target_name = f"{stem}{extension}"
        target_path = os.path.join(EVENTS_IMG_DIR, target_name)
        with open(target_path, "wb") as output:
            output.write(payload)
        saved[language] = target_name
        print(f"Poster saved: {target_name} ({len(payload)} bytes)")
    return saved


def update_seminar_in_site(details, posters):
    with open(EVENTS_PATH, "r", encoding="utf-8") as source:
        page = source.read()

    month_comments = {"فروردین": "Farvardin", "اردیبهشت": "Ordibehesht", "خرداد": "Khordad", "تیر": "Tir", "مرداد": "Mordad", "شهریور": "Shahrivar", "مهر": "Mehr", "آبان": "Aban", "آذر": "Azar", "دی": "Dey", "بهمن": "Bahman", "اسفند": "Esfand"}
    marker_month = month_comments.get(details["month"], details["month"])
    marker = f"<!-- {details['day']} {marker_month} {details['year']} -->"
    start = page.find(marker)
    if start < 0:
        print(f"Review required: event marker not found for {marker}")
        return False

    next_marker = re.search(r"\n\s*<!--\s*\d{1,2}\s+[A-Za-zآ-ی]+\s+14\d{2}\s*-->", page[start + len(marker):])
    if not next_marker:
        print("Review required: following event marker was not found; page left unchanged.")
        return False
    end = start + len(marker) + next_marker.start()
    if end < start:
        print("Review required: could not isolate the dated event card.")
        return False

    block = page[start:end]
    escaped_title = html.escape(details["title"], quote=True)
    title_pattern = re.compile(r'(<h5\b[^>]*>).*?(</h5>)', re.S)
    if title_pattern.search(block):
        block = title_pattern.sub(
            lambda match: re.sub(r">\s*$", ">", match.group(1)) +
                          escaped_title + match.group(2),
            block, count=1
        )

    if details.get("speaker"):
        speaker_pattern = re.compile(r'(<span\b[^>]*data-fa=")[^"]*(".*?data-en=")[^"]*(".*?>).*?(</span>)', re.S)
        if speaker_pattern.search(block):
            block = speaker_pattern.sub(
                lambda m: m.group(1) + "👤 " + html.escape(details["speaker"], quote=True) +
                          m.group(2) + "👤 " + html.escape(details["speaker"], quote=True) +
                          m.group(3) + "👤 " + html.escape(details["speaker"]) + m.group(4),
                block, count=1
            )

    poster_links = []
    labels = {
        "fa": ('پوستر فارسی', 'Persian poster'),
        "en": ('پوستر انگلیسی', 'English poster'),
    }
    for language in ("fa", "en"):
        filename = posters.get(language)
        if filename:
            href = "assets/images/events/" + filename
            fa_label, en_label = labels[language]
            poster_links.append(
                f'<a class="seminar-poster-link" href="{href}" target="_blank" rel="noopener" '
                f'download data-fa="{fa_label}" data-en="{en_label}">{fa_label} / {en_label}</a>'
            )
    if posters.get("unclassified"):
        filename = posters["unclassified"]
        href = "assets/images/events/" + filename
        poster_links.append(
            f'<a class="seminar-poster-link" href="{href}" target="_blank" rel="noopener" download '
            f'data-fa="پوستر" data-en="Poster">پوستر / Poster</a>'
        )

    # If event already has interactive poster-btn elements, do not insert duplicate plain links
    if 'class="poster-btn"' in block:
        print("Interactive poster buttons already present, skipping duplicate links.")
        return False

    # Replace the poster links on repeat runs instead of duplicating them.
    block = re.sub(r'\s*<div class="seminar-posters"[^>]*>.*?</div>', "", block, flags=re.S)
    if poster_links:
        links_html = '<div class="seminar-posters" style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;">' + \
                     "".join(poster_links) + '</div>'
        insertion = block.find("</div>", block.find('<div class="event-meta"'))
        if insertion >= 0:
            insertion += len("</div>")
            block = block[:insertion] + "\n                " + links_html + block[insertion:]
        else:
            print("Review required: could not find event metadata container for poster links.")
            return False

    updated_page = page[:start] + block + page[end:]
    if updated_page != page:
        with open(EVENTS_PATH, "w", encoding="utf-8") as output:
            output.write(updated_page)
        print(f"Updated event card: {details['day']} {details['month']} {details['year']}")
        return True
    print("No changes needed for this event.")
    return False


def extract_contact_addresses(message):
    """
    نشانی‌های موجود در سرصفحه‌های گیرندگان (To / Cc) یک ایمیل اعلام سمینار را
    استخراج می‌کند؛ بدون تکرار و بدون نشانی‌های داخلی خود مرکز.
    """
    found = []
    for header in ("To", "Cc", "Resent-To", "Resent-Cc"):
        for value in message.get_all(header, []):
            for _name, addr in email.utils.getaddresses([decode_mime(value)]):
                addr = (addr or "").strip().lower()
                if "@" in addr:
                    found.append(addr)

    seen, unique = set(), []
    for addr in found:
        if addr not in seen:
            seen.add(addr)
            unique.append(addr)
    return unique


def fetch_and_update():
    sharif_host = os.environ.get("SHARIF_MAIL_HOST", "physics.sharif.ir")
    sharif_user = os.environ.get("SHARIF_MAIL_USER")
    sharif_pass = os.environ.get("SHARIF_MAIL_PASSWORD")
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")

    accounts = []
    if sharif_user and sharif_pass:
        accounts.append(("Sharif", sharif_host, 993, sharif_user, sharif_pass))
    if gmail_user and gmail_pass:
        accounts.append(("Gmail", "imap.gmail.com", 993, gmail_user, gmail_pass))

    if not accounts:
        print("Missing mail credentials (neither Sharif nor Gmail found).")
        return False

    updated = False
    for label, host, port, user, password in accounts:
        mail = None
        try:
            print(f"Checking {label} inbox for seminar announcements...")
            mail = imaplib.IMAP4_SSL(host, port)
            mail.login(user, password)
            mail.select("inbox")

            status, search_data = mail.search(None, "ALL")
            if status != "OK":
                print(f"{label} search failed.")
                continue

            message_ids = search_data[0].split()[-25:]
            print(f"{label} recent messages examined: {len(message_ids)}")

            for message_id in message_ids:
                status, data = mail.fetch(message_id, "(RFC822)")
                if status != "OK" or not data or not isinstance(data[0], tuple):
                    continue

                message = email.message_from_bytes(data[0][1])
                sender = decode_mime(message.get("From", "")).lower()

                # Accept from approved senders or official rchep email
                is_approved = any(s in sender for s in APPROVED_SENDERS) or "rchep@physics.sharif.ir" in sender
                if not is_approved:
                    continue

                subject = decode_mime(message.get("Subject"))
                if not any(term in normalize_text(subject) for term in ("سمینار", "هوشواره", "seminar")):
                    continue

                body = extract_body(message)
                parsed = parse_seminar_text(body, subject)
                if not parsed:
                    continue

                posters = save_posters(message, parsed["day"], parsed["month"])

                # ۱) فهرست مخاطبین برگزارکنندگان سمینار (استادان وردیان و سیری) را
                #    بدون تکرار و با وضعیت «تأییدشده» به فهرست مشترکان تارنما می‌افزاید.
                try:
                    import newsletter_manager
                    contacts = extract_contact_addresses(message)
                    if contacts:
                        added, promoted = newsletter_manager.add_confirmed_contacts(
                            contacts, source=f"seminar-list:{sender}"
                        )
                        print(
                            f"Contact list of {sender}: {len(contacts)} address(es) seen, "
                            f"{len(added)} added as confirmed, {len(promoted)} promoted to confirmed."
                        )
                except Exception as ex:
                    print(f"Contact list import skipped: {ex}")

                # ۲) تارنما را به‌روزرسانی می‌کند
                if update_seminar_in_site(parsed, posters):
                    updated = True

                # ۳) اطلاعیه هر سمینار را در یک ایمیل جداگانه به همه مخاطبین می‌فرستد
                #    (نشانه یکتا در data/sent_seminars.json از ارسال تکراری جلوگیری می‌کند)
                try:
                    import newsletter_manager
                    newsletter_manager.broadcast_seminar(parsed)
                except Exception as ex:
                    print(f"Newsletter broadcast notice skipped: {ex}")
        except Exception as e:
            print(f"Error checking {label} mail: {e}")
        finally:
            if mail is not None:
                try:
                    mail.close()
                except Exception:
                    pass
                try:
                    mail.logout()
                except Exception:
                    pass

    return updated


if __name__ == "__main__":
    changed = fetch_and_update()
    print("Email synchronization finished. Changes made:", changed)
