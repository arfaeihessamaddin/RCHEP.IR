#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe the RCHEP mailboxes (read-only) and write a masked digest.

Purpose: locate an announcement (for example the "هوشواره" session email
sent by dr. Siri) whose poster has to be embedded in the outgoing notice,
and copy the image attachments of keyword-matched messages into
assets/images/events/.

Nothing is sent, no message is modified or marked read.  Only image
attachments of keyword-matched messages are copied into the repository and
a masked digest (data/inbox_probe.json) is written for the operator.  All
e-mail addresses are masked so that a public workflow log / repository
never carries personal contact data.
"""

import email
import email.utils
import hashlib
import imaplib
import json
import os
import re
from email.header import decode_header

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
EVENTS_IMG_DIR = os.path.join(REPO_ROOT, "assets", "images", "events")
DIGEST_FILE = os.path.join(DATA_DIR, "inbox_probe.json")
os.makedirs(EVENTS_IMG_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

SCAN_LIMIT = int(os.environ.get("RCHEP_PROBE_LIMIT", "40"))
BODY_LIMIT = int(os.environ.get("RCHEP_PROBE_BODY_LIMIT", "1800"))
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf")

# \u06a9\u0644\u0645\u0627\u062a\u06cc \u06a9\u0647 \u0628\u0627\u06cc\u062f \u0628\u0631\u0627\u06cc \u062c\u0633\u062a\u200c\u0648\u062c\u0648 \u062f\u0631 \u0635\u0646\u062f\u0648\u0642 \u067e\u0633\u062a\u06cc \u0645\u0648\u0631\u062f \u062a\u0648\u062c\u0647 \u0642\u0631\u0627\u0631 \u0628\u06af\u06cc\u0631\u0646\u062f.
KEYWORDS = (
    "\u0647\u0648\u0634\u0648\u0627\u0631\u0647",   # ه و ش و ا ر ه
    "\u0646\u0634\u0633\u062a",                    # ن ش س ت
    "\u0633\u0645\u06cc\u0646\u0627\u0631",        # س م ی ن ا ر
    "\u06a9\u0644\u0627\u0628",                    # ک ل ا ب
    "seminar",
    "session",
    "journal club",
    "colloquium",
    "workshop",
)

MONTH_SLUG = {
    "\u0641\u0631\u0648\u0631\u062f\u06cc\u0646": "farvardin",
    "\u0627\u0631\u062f\u06cc\u0628\u0647\u0634\u062a": "ordibehesht",
    "\u062e\u0631\u062f\u0627\u062f": "khordad",
    "\u062a\u06cc\u0631": "tir",
    "\u0645\u0631\u062f\u0627\u062f": "mordad",
    "\u0634\u0647\u0631\u06cc\u0648\u0631": "shahrivar",
    "\u0645\u0647\u0631": "mehr",
    "\u0622\u0628\u0627\u0646": "aban",
    "\u0622\u0630\u0631": "azar",
    "\u062f\u06cc": "dey",
    "\u0628\u0647\u0645\u0646": "bahman",
    "\u0627\u0633\u0641\u0646\u062f": "esfand",
}


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
    return (
        value.replace("\u200c", "")
        .replace("\u200f", "")
        .replace("\u064a", "\u06cc")
        .replace("\u0643", "\u06a9")
        .replace("\xa0", " ")
        .strip()
    )


ADDRESS_PATTERN = re.compile(r"([\w.+-]+)@([\w.-]+\.[A-Za-z]{2,})")


def mask_text(value):
    """\u0647\u0631 \u0646\u0634\u0627\u0646\u06cc \u0631\u0627 \u0646\u0627\u0645\u0647\u200c\u0633\u0631\u062f\u0647 \u0645\u06cc\u200c\u06a9\u0646\u062f \u062a\u0627 \u062f\u0631 \u0645\u062e\u0632\u0646 \u0639\u0645\u0648\u0645\u06cc \u062b\u0628\u062a \u0646\u0634\u0648\u062f."""
    def _hide(match):
        return f"{match.group(1)[:1]}***@{match.group(2)}"

    return ADDRESS_PATTERN.sub(_hide, value or "")


def mask_address(value):
    return mask_text(decode_mime(value))


def message_date(message):
    raw = message.get("Date")
    try:
        return email.utils.parsedate_to_datetime(raw)
    except Exception:
        return None


def extract_body(message):
    plain_parts, html_parts = [], []
    for part in message.walk():
        if part.get_content_maintype() == "multipart" or part.get_filename():
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
    body = "\n".join(plain_parts or html_parts)
    lines = [normalize_text(line) for line in body.splitlines()]
    return "\n".join(line for line in lines if line)


def collect_attachments(message):
    attachments = []
    for part in message.walk():
        filename = decode_mime(part.get_filename())
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "name": filename,
                "size": len(payload),
                "extension": os.path.splitext(filename)[1].lower(),
                "sha1": hashlib.sha1(payload).hexdigest()[:12] if payload else "",
                "_payload": payload,
            }
        )
    return attachments


def save_attachment(payload, extension, subject, stamp, index):
    if extension not in IMAGE_EXTENSIONS or not payload:
        return None
    flat = normalize_text(subject)
    if "\u0647\u0648\u0634\u0648\u0627\u0631\u0647" in flat:
        slug = "houshvareh"
    elif "\u0633\u0645\u06cc\u0646\u0627\u0631" in flat:
        slug = "seminar"
    else:
        slug = "session"
    target_name = f"{slug}-{stamp}-{index}{extension}"
    target_path = os.path.join(EVENTS_IMG_DIR, target_name)
    with open(target_path, "wb") as output:
        output.write(payload)
    print(f"Probe attachment saved: {target_name} ({len(payload)} bytes)")
    return target_name


def digest_account(label, host, port, user, password):
    entries = []
    mail = None
    try:
        mail = imaplib.IMAP4_SSL(host, port)
        mail.login(user, password)
        mail.select("inbox", readonly=True)
        status, search_data = mail.search(None, "ALL")
        if status != "OK":
            print(f"{label} search failed.")
            return entries
        message_ids = search_data[0].split()[-SCAN_LIMIT:]
        print(f"{label}: examining {len(message_ids)} recent message(s).")
        for index, message_id in enumerate(reversed(message_ids), start=1):
            status, data = mail.fetch(message_id, "(RFC822)")
            if status != "OK" or not data or not isinstance(data[0], tuple):
                continue
            message = email.message_from_bytes(data[0][1])
            when = message_date(message)
            subject = decode_mime(message.get("Subject"))
            flat_subject = normalize_text(subject)
            body = extract_body(message)
            haystack = (flat_subject + "\n" + body).lower()
            hit = any(keyword.lower() in haystack for keyword in KEYWORDS)
            entry = {
                "account": label,
                "index": index,
                "date": when.isoformat() if when else "",
                "from": mask_address(message.get("From", "")),
                "to": mask_address(message.get("To", ""))[:200],
                "subject": mask_text(subject)[:300],
                "keyword_hit": hit,
                "attachments": [
                    {k: v for k, v in item.items() if k != "_payload"}
                    for item in collect_attachments(message)
                ],
            }
            if hit:
                stamp = when.strftime("%Y%m%d") if when else "unknown"
                saved = []
                for position, item in enumerate(collect_attachments(message), start=1):
                    name = save_attachment(
                        item["_payload"], item["extension"], subject, stamp or "unknown", position
                    )
                    if name:
                        saved.append(name)
                entry["saved_files"] = saved
                entry["body"] = mask_text(body)[:BODY_LIMIT]
            entries.append(entry)
    except Exception as ex:
        print(f"{label} probe failed: {ex}")
    finally:
        if mail is not None:
            for closer in ("close", "logout"):
                try:
                    getattr(mail, closer)()
                except Exception:
                    pass
    return entries


def main():
    accounts = []
    sharif_host = os.environ.get("SHARIF_MAIL_HOST", "physics.sharif.ir")
    sharif_user = os.environ.get("SHARIF_MAIL_USER")
    sharif_pass = os.environ.get("SHARIF_MAIL_PASSWORD")
    gmail_user = os.environ.get("GMAIL_USER")
    gmail_pass = os.environ.get("GMAIL_APP_PASSWORD")
    if sharif_user and sharif_pass:
        accounts.append(("Sharif", sharif_host, 993, sharif_user, sharif_pass))
    if gmail_user and gmail_pass:
        accounts.append(("Gmail", "imap.gmail.com", 993, gmail_user, gmail_pass))
    if not accounts:
        print("Missing mail credentials; probe skipped.")
        return False

    digest = {"scan_limit": SCAN_LIMIT, "messages": []}
    for label, host, port, user, password in accounts:
        digest["messages"].extend(digest_account(label, host, port, user, password))

    with open(DIGEST_FILE, "w", encoding="utf-8") as output:
        json.dump(digest, output, ensure_ascii=False, indent=2)
    hits = sum(1 for item in digest["messages"] if item.get("keyword_hit"))
    print(f"Probe digest written: {DIGEST_FILE} ({len(digest['messages'])} messages, {hits} keyword hit(s))")
    return True


if __name__ == "__main__":
    main()
