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
    r"^(?:\[|\()?\s*(?:image|cid|attachment|inline|پیوست|تصویر)\s*[:\-]",
    re.I,
)
FILE_NAME_LINE = re.compile(
    r"\.(?:jpe?g|png|gif|bmp|webp|tiff?|svg|heic|pdf|docx?|pptx?|xlsx?|zip|rar|mp4|ai|psd|indd)\b",
    re.I,
)
FILE_JUNK_WORDS = re.compile(
    r"photoshop|vector|logo|watermark|freepik|shutterstock|canva|banner|"
    r"unsubscribe|لغو دریافت پیام|لغو اشتراک",
    re.I,
)


def is_noise_line(line):
    """سطرهای شبه‌پیوست/نام پرونده/نشانی را نادیده می‌گیرد تا عنوان سمینار ناخوانا نشود."""
    compact = normalize_text(line).strip().strip("*• \t")
    if not compact:
        return True
    if len(compact) > 200:
        return True
    if ATTACHMENT_LINE.match(compact):
        return True
    if FILE_NAME_LINE.search(compact):
        return True
    if FILE_JUNK_WORDS.search(compact):
        return True
    if re.match(r"^(?:https?://|www\.|mailto:)", compact, re.I):
        return True
    if re.match(r"^<[^>]+>$", compact) or re.match(r"^[^@\s]+@[^@\s]+$", compact):
        return True
    # سطر بی‌فاصلهٔ فنی (نام پرونده/شناسهٔ پیوست) عنوان سمینار نیست.
    if (
        " " not in compact
        and len(compact) >= 12
        and (re.search(r"[A-Za-z]", compact) or "-" in compact or "_" in compact or re.search(r"\d{2,}", compact))
    ):
        return True
    return False


OWN_NOTICE_MARKERS = (
    "\u005b\u0633\u0645\u06cc\u0646\u0627\u0631",              # [س م ی ن ا ر
    "\u005b\u0647\u0648\u0634\u0648\u0627\u0631\u0647",       # [ه و ش و ا ر ه
)


def is_own_notice(subject):
    """آیا این پیام، اطلاعیهٔ خودِ مرکز است که در صندوق پستی دور خورده است؟"""
    cleaned = normalize_text(subject).lower()
    if any(marker.lower() in cleaned for marker in OWN_NOTICE_MARKERS):
        return True
    return any(
        token in cleaned
        for token in ("\u0644\u063a\u0648 \u062f\u0631\u06cc\u0627\u0641\u062a \u067e\u06cc\u0627\u0645", "unsubscribe")
    )


IMAGE_REF_PATTERN = re.compile(
    r"\[\s*(?:image|cid|attachment|inline)\s*:[^\]]*\]",
    re.IGNORECASE,
)
# \u0627\u0631\u062c\u0627\u0639 \u0628\u0631\u0686\u0633\u0628 \u062f\u0627\u062e\u0644 \u0645\u062a\u0646 (\u0645\u0627\u0646\u0646\u062f "Image: ce37534f-....jpg" \u06cc\u0627 "mage: ...jpg]") \u062a\u0627 \u062c\u0644\u0648\u06cc \u0646\u0627\u0645 \u0633\u062e\u0646\u0631\u0627\u0646 \u0631\u0627 \u0628\u06af\u06cc\u0631\u062f.
LABEL_REF_PATTERN = re.compile(r"(?:i?mage|cid|attachment|inline)\s*:\s*\S*", re.IGNORECASE)
STRAY_BRACKET_PATTERN = re.compile(
    r"\[\s*[^\]]{0,120}?\.(?:jpe?g|png|gif|bmp|webp|tiff?|svg|heic|pdf|docx?|pptx?|xlsx?|zip|rar|mp4|ai|psd|indd)\s*\]",
    re.IGNORECASE,
)
BARE_FILENAME_PATTERN = re.compile(r"\b[\w\-]{6,}\.[a-z]{2,4}\b", re.IGNORECASE)


def sanitize_field(value):
    """پاک‌سازی رشته‌های استخراج‌شده از ارجاع تصویری و نام پرونده."""
    if not value:
        return value
    cleaned = IMAGE_REF_PATTERN.sub(" ", value)
    cleaned = STRAY_BRACKET_PATTERN.sub(" ", cleaned)
    cleaned = LABEL_REF_PATTERN.sub(" ", cleaned)
    cleaned = BARE_FILENAME_PATTERN.sub(" ", cleaned)
    cleaned = re.sub(r"\s*\(\s*\)\s*", " ", cleaned)
    cleaned = re.sub(r"\s*\]\s*", " ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" \u060c,\u061b;|()[]")
    cleaned = cleaned.strip()
    # \u0627\u06af\u0631 \u0628\u0627\u0642\u06cc\u200c\u0645\u0627\u0646\u062f\u0647 \u0641\u0642\u0637 \u0646\u0634\u0627\u0646\u0647\u200c\u06af\u0630\u0627\u0631\u06cc \u06cc\u0627 \u062a\u06a9\u200c\u062a\u0648\u06a9\u0646 \u0628\u06cc\u200c\u0645\u0639\u0646\u0627 \u0628\u0627\u0634\u062f\uff0c \u062e\u0627\u0644\u06cc \u0628\u0631\u0645\u06cc\u200c\u06af\u0631\u062f\u0627\u0646\u06cc\u0645 \u062a\u0627 \u062f\u0631 \u0627\u06cc\u0645\u06cc\u0644 \u0648 \u06a9\u0627\u0631\u062a \u0631\u0648\u06cc\u062f\u0627\u062f \u0646\u062a\u0627\u0628\u062f.
    if not re.search(r"[\w\u0600-\u06FF]", cleaned):
        return ""
    if len(cleaned) <= 3 and not re.search(r"[\u0600-\u06FF]", cleaned):
        return ""
    return cleaned


def plausible_title(text):
    """آیا متن یافته‌شده شایستهٔ نشستن در جایگاه «عنوان سمینار» است؟"""
    if not text:
        return False
    compact = normalize_text(text).strip()
    if is_noise_line(compact):
        return False
    letters = re.findall(r"[^\W\d_]", compact, re.UNICODE)
    if len(letters) < 6:
        return False
    if re.fullmatch(r"[\d\s،,:؛.()\-]+", compact):
        return False
    return True


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
            candidate = sanitize_field(match.group(1).strip())
            if plausible_title(candidate):
                details["title"] = candidate
            break

    # Otherwise, the title is normally the first substantive line after the seminar header.
    if not details["title"]:
        for index, line in enumerate(lines):
            compact = normalize_text(line)
            if "سمینار" in compact and ("مرکز" in compact or "دانشگاه" in compact):
                for raw_candidate in lines[index + 1:index + 9]:
                    candidate = sanitize_field(raw_candidate)
                    if re.search(
                        r"\u0627\u0631\u0627\u0626\u0647\u200c?\u062f\u0647\u200c?\u0646\u062f\u0647|\u0633\u062e\u0646\u0631\u0627\u0646|\u0632\u0645\u0627\u0646|\u062a\u0627\u0631\u06cc\u062e|\u0645\u06a9\u0627\u0646|\u0686\u06a9\u06cc\u062f\u0647|\u062f\u0627\u0646\u0634\u06af\u0627\u0647 \u0635\u0646\u0639\u062a\u06cc \u0634\u0631\u06cc\u0641",
                        normalize_text(candidate), re.I
                    ):
                        continue
                    if plausible_title(candidate):
                        details["title"] = candidate
                        break
                break

    # اگر متن سمینار تنها تصویر پوستر باشد، عنوان از سرصفحهٔ ایمیل برداشته می‌شود.
    if not details["title"]:
        subject_clean = re.sub(
            r"^(?:re|fwd|fw|\u067e\u0627\u0633\u062e|\u0628\u0627\u0632\u0627\u0631\u0633\u0627\u0644|\u0647\u0648\u0634\u0648\u0627\u0631\u0647)\s*[:\uff1a]\s*",
            "", normalize_text(subject), flags=re.I,
        )
        for chunk in re.split(
            r"[:\uff1a\u00bb\-\u2013\u2014]|\u0633\u0645\u06cc\u0646\u0627\u0631|\u0647\u0641\u062a\u06af\u06cc",
            subject_clean,
        ):
            chunk = chunk.strip(" \u060c,\u061b;.|\u060c")
            chunk = re.sub(r"\s*[\(\[]\s*\d{1,2}\s*[^\d\)\]]{2,14}\s*\d{4}\s*[\)\]]\s*$", "", chunk).strip()
            chunk = sanitize_field(chunk)
            if plausible_title(chunk):
                details["title"] = chunk
                break

    # Speaker labels tolerate joined, spaced, and half-spaced Persian forms.
    for index, line in enumerate(lines):
        compact = normalize_text(line)
        if re.search(r"(?:ارائهدهنده|سخنران|ارائهکننده)", compact):
            value = re.split(r"[\u003a\uff1a]", line, maxsplit=1)
            candidate = value[1].strip() if len(value) > 1 and value[1].strip() else ""
            if not candidate and index + 1 < len(lines):
                candidate = lines[index + 1]
            candidate = sanitize_field(candidate)
            if candidate and not is_noise_line(candidate):
                details["speaker"] = candidate
            break

    # Affiliation, when explicitly present.
    for index, line in enumerate(lines):
        if re.search(
            r"\u0648\u0627\u0628\u0633\u062a\u06af\u06cc|\u062f\u0627\u0646\u0634\u06af\u0627\u0647|\u067e\u0698\u0648\u0647\u0634\u06af\u0627\u0647|affiliation",
            normalize_text(line), re.I,
        ):
            keyword_only = re.fullmatch(
                r"(?:\u0648\u0627\u0628\u0633\u062a\u06af\u06cc|\u062f\u0627\u0646\u0634\u06af\u0627\u0647|\u067e\u0698\u0648\u0647\u0634\u06af\u0627\u0647|affiliation)\s*[:\uff1a]?",
                normalize_text(line), re.I,
            )
            if ":" in line or "\uff1a" in line:
                candidate = re.split(r"[\u003a\uff1a]", line, maxsplit=1)[-1].strip()
            elif keyword_only and index + 1 < len(lines):
                candidate = lines[index + 1]
            else:
                candidate = line
            candidate = sanitize_field((candidate or "").strip())
            if candidate and not is_noise_line(candidate) and not re.search(
                r"\u0686\u06a9\u06cc\u062f\u0647|\u0633\u0627\u0639\u062a|\u0645\u06a9\u0627\u0646|\u0627\u0631\u0627\u0626\u0647|\u0633\u062e\u0646\u0631\u0627\u0646",
                candidate,
            ):
                details["affiliation"] = candidate
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

    for key in ("title", "speaker", "affiliation", "abstract", "location"):
        if details.get(key):
            details[key] = sanitize_field(details[key])

    missing = [key for key in ("title", "speaker", "day", "month") if not details.get(key)]
    if missing:
        print("Seminar announcement incomplete; missing: " + ", ".join(missing))
        return None
    return details


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
    title_pattern = re.compile(r'(<h5\b[^>]*>).*?</h5>', re.S)
    if title_pattern.search(block):
        def _rewrite_title(match):
            opening = re.sub(r"\s+data-(?:fa|en)=\"[^\"]*\"", "", match.group(1))
            opening = re.sub(r">\s*$", "", opening)
            return (f'{opening} data-fa="{escaped_title}" data-en="{escaped_title}">'
                    f'{escaped_title}</h5>')

        block = title_pattern.sub(_rewrite_title, block, count=1)

    if details.get("speaker"):
        details["speaker"] = sanitize_field(details["speaker"])
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

                # اطلاعیه‌های خودِ مرکز نباید دوباره به‌عنوان سمینار خوانده شوند
                # (وگرنه کارت رویداد و فهرست مخاطبین آلوده می‌شود).
                if is_own_notice(subject):
                    print("Own seminar notice detected; skipping.")
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

                # پیش از به‌روزرسانی تارنما و ارسال اطلاعیه، از خوانا بودن عنوان مطمئن می‌شویم
                # تا کارت رویداد با نام پرونده یا سطر پیوست خراب نشود.
                if not plausible_title(parsed.get("title", "")):
                    print("Seminar title could not be recognized; site and recipients left untouched.")
                    continue

                print(
                    "Recognized seminar:"
                    f" title={parsed.get('title', '')!r}"
                    f" speaker={parsed.get('speaker', '')!r}"
                    f" date={parsed.get('day', '')} {parsed.get('month', '')}"
                )

                # ۲) تارنما را به‌روزرسانی می‌کند
                if update_seminar_in_site(parsed, posters):
                    updated = True

                # ۳) اطلاعیه هر سمینار را در یک ایمیل جداگانه به همه مخاطبین می‌فرستد
                #    (نشانه یکتا در data/sent_seminars.json از ارسال تکراری جلوگیری می‌کند)
                try:
                    import newsletter_manager
                    chosen_poster = (
                        (posters or {}).get("fa")
                        or (posters or {}).get("en")
                        or (posters or {}).get("unclassified")
                    )
                    newsletter_manager.broadcast_seminar(parsed, chosen_poster)
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
