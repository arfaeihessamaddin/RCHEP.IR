#!/usr/bin/env python3
"""
RCHEP Subscription & Newsletter Manager
Manages double opt-in subscriptions and seminar email broadcasts via Sharif Physics mail server.
"""

import os
import re
import sys
import json
import uuid
import smtplib
import imaplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")
SUBSCRIBERS_FILE = os.path.join(DATA_DIR, "subscribers.json")
SENT_SEMINARS_FILE = os.path.join(DATA_DIR, "sent_seminars.json")
NOTICE_QUEUE_FILE = os.path.join(DATA_DIR, "notice_queue.json")
PROCESSED_EMAILS_FILE = os.path.join(DATA_DIR, "processed_emails.json")
EVENTS_IMG_DIR = os.path.join(REPO_ROOT, "assets", "images", "events")
NOTICE_POSTER_CID = "rchep-notice-poster"
DEFAULT_LOCATION = "\u0627\u062a\u0627\u0642 \u0633\u0645\u06cc\u0646\u0627\u0631 RCHEP (\u062f\u0627\u0646\u0634\u06a9\u062f\u0647 \u0641\u06cc\u0632\u06cc\u06a9) + \u0645\u062c\u0627\u0632\u06cc (vc.sharif.edu/ch/physics-high-energy)"

MAIL_HOST = os.environ.get("SHARIF_MAIL_HOST", "physics.sharif.ir")
MAIL_PORT = int(os.environ.get("SHARIF_MAIL_PORT", "587"))
MAIL_USER = os.environ.get("SHARIF_MAIL_USER", "rchep@physics.sharif.ir")
MAIL_PASSWORD = os.environ.get("SHARIF_MAIL_PASSWORD", "")

# نشانی‌هایی که هرگز نباید به فهرست مشترکان افزوده شوند
INTERNAL_ADDRESSES = {
    MAIL_USER.lower(),
    "rchep@physics.sharif.ir",
    "rchep@sharif.edu",
    "rchep.ir@gmail.com",
}

os.makedirs(DATA_DIR, exist_ok=True)

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    # Automatically recompile Excel sheet and sync if subscribers changed
    if "subscribers.json" in filepath:
        try:
            import subprocess
            sync_script = os.path.join(os.path.dirname(__file__), "sync_sharif_cloud.py")
            if os.path.exists(sync_script):
                subprocess.run([sys.executable, sync_script], capture_output=True)
        except Exception as e:
            print(f"Auto-sync trigger warning: {e}")

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

def build_email_message(to_email, subject, html_content, text_content=None, inline_images=None):
    """\u067e\u06cc\u0627\u0645 \u0631\u0627 \u0645\u06cc\u200c\u0633\u0627\u0632\u062f \u062c\u062f\u0627 \u0627\u0632 \u0627\u0631\u0633\u0627\u0644\u060c \u062a\u0627 \u0628\u062a\u0648\u0627\u0646 \u0628\u062f\u0648\u0646 SMTP \u0622\u0632\u0645\u0648\u062f."""
    inline_images = inline_images or []
    root = MIMEMultipart("related") if inline_images else MIMEMultipart("alternative")
    body = MIMEMultipart("alternative") if inline_images else root
    if text_content:
        body.attach(MIMEText(text_content, "plain", "utf-8"))
    body.attach(MIMEText(html_content, "html", "utf-8"))
    if body is not root:
        root.attach(body)

    subtype_map = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}
    for cid, path in inline_images:
        try:
            with open(path, "rb") as handle:
                payload = handle.read()
        except OSError as exc:
            print(f"Inline image skipped ({path}): {exc}")
            continue
        extension = os.path.splitext(path)[1].lower().lstrip(".")
        image = MIMEImage(payload, _subtype=subtype_map.get(extension, "jpeg"))
        image.add_header("Content-ID", f"<{cid}>")
        image.add_header("Content-Disposition", "inline", filename=os.path.basename(path))
        root.attach(image)

    root["Subject"] = subject
    root["From"] = f"RCHEP Center <{MAIL_USER}>"
    root["To"] = to_email
    return root


def send_smtp_email(to_email, subject, html_content, text_content=None, inline_images=None):
    if not MAIL_PASSWORD:
        raise RuntimeError("SHARIF_MAIL_PASSWORD is not set.")

    msg = build_email_message(to_email, subject, html_content, text_content, inline_images)

    with smtplib.SMTP(MAIL_HOST, MAIL_PORT, timeout=15) as server:
        server.starttls()
        server.login(MAIL_USER, MAIL_PASSWORD)
        server.send_message(msg)

def send_verification_email(name, to_email, token):
    verify_email_addr = MAIL_USER
    subject = f"تأیید عضویت در فهرست سمینارهای مرکز فیزیک انرژی بالا (کد: {token[:8]})"
    
    html = f"""
    <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, Arial, sans-serif; line-height: 1.8; color: #1e293b; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
      <div style="border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px;">
        <h2 style="color: #0369a1; margin: 0; font-size: 1.25rem;">مرکز پژوهشی فیزیک انرژی بالا (RCHEP)</h2>
        <span style="font-size: 0.85rem; color: #64748b;">دانشگاه صنعتی شریف</span>
      </div>
      <p>درود {name if name else 'گرامی'}،</p>
      <p>درخواست شما برای دریافت آگهی سمینارها و رویدادهای هفتگی مرکز دریافت گردید.</p>
      <div style="background: #f0fdf4; border-right: 4px solid #16a34a; padding: 14px 18px; border-radius: 6px; margin: 20px 0;">
        <strong style="color: #15803d; font-size: 1rem;">نحوه نهایی‌سازی عضویت (تضمین صحت نشانی):</strong>
        <p style="margin: 8px 0 0 0; color: #166534; font-size: 0.95rem;">
          روی دکمه آبی زیر بزنید تا پنجره پاسخ (Reply) باز شود، سپس فقط دکمه <b>ارسال (Send)</b> را بزنید.
          <br>
          <span style="font-size: 0.85rem; color: #4b5563;">(نیازی به نوشتن متنی در پاسخ نیست؛ عنوان ایمیل حاوی کد یکتای تأیید است و ارسال آن هویت و دریافت نشانی شما را قطعی می‌کند).</span>
        </p>
      </div>
      <div style="text-align: center; margin: 25px 0;">
        <a href="mailto:{verify_email_addr}?subject=CONFIRM_{token}" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">باز کردن پاسخ و ارسال تأییدیه ✉️</a>
      </div>
      <p style="font-size: 0.85rem; color: #64748b; background: #f8fafc; padding: 10px 14px; border-radius: 6px;">
        همچنین می‌توانید بدون زدن دکمه فوق، مستقیماً همین ایمیل را با نرم‌افزار ایمیل خود <b>Reply</b> کنید.<br>
        شناسه اختصاصی شما: <code>{token}</code><br>
        در صورتی که شما این درخواست را ثبت نکرده‌اید، این پیام را نادیده بگیرید.
      </p>
    </div>
    """
    send_smtp_email(to_email, subject, html)

PLACEHOLDER_PATTERN = re.compile(
    r"\[\s*(?:image|cid|attachment|inline)\s*:[^\]]*\]"
    r"|(?:i?mage|cid|attachment|inline)\s*:\s*\S*"
    r"|\b[\w\-]{6,}\.(?:jpe?g|png|gif|bmp|webp|tiff?|svg|heic|pdf)\b",
    re.IGNORECASE,
)


def has_placeholder(*values):
    """\u0622\u06cc\u0627 \u0645\u062a\u0646 \u0627\u0631\u062c\u0627\u0639 \u062e\u0627\u0645 \u062a\u0635\u0648\u06cc\u0631 \u06cc\u0627 \u0646\u0627\u0645 \u067e\u0631\u0648\u0646\u062f\u0647 \u062f\u0627\u0631\u062f\u061f (\u0647\u0645\u0627\u0646 \u0627\u0634\u062a\u0628\u0627\u0647\u06cc \u06a9\u0647 \u062f\u0631 \u0627\u0637\u0644\u0627\u0639\u06cc\u0647\u0654 25 \u0622\u0628\u0627\u0646 \u0631\u062e \u062f\u0627\u062f)"""
    return any(value and PLACEHOLDER_PATTERN.search(str(value)) for value in values)


def clean_field(value):
    """\u062d\u0630\u0641 \u0627\u0631\u062c\u0627\u0639\u200c\u0647\u0627\u06cc \u062a\u0635\u0648\u06cc\u0631\u06cc \u0648 \u0646\u0627\u0645 \u067e\u0631\u0648\u0646\u062f\u0647\u200c\u0647\u0627 \u0627\u0632 \u06cc\u06a9 \u0641\u06cc\u0644\u062f."""
    return PLACEHOLDER_PATTERN.sub(" ", str(value or "")).strip(" -\u2014:\u060c,")


def resolve_poster_path(poster):
    """\u0646\u0634\u0627\u0646\u06cc \u06a9\u0627\u0645\u0644 \u067e\u0648\u0633\u062a\u0631 \u062f\u0631 \u0645\u062e\u0632\u0646 \u0631\u0627 \u0628\u0631\u0645\u06cc\u200c\u06af\u0631\u062f\u0627\u0646\u062f (\u0627\u06af\u0631 \u0648\u062c\u0648\u062f \u062f\u0627\u0634\u062a\u0647 \u0628\u0627\u0634\u062f)."""
    if not poster:
        return None
    candidate = poster if os.path.isabs(poster) else os.path.join(EVENTS_IMG_DIR, os.path.basename(poster))
    return candidate if os.path.exists(candidate) else None


def weekday_name(day, month):
    """\u0646\u0627\u0645 \u0631\u0648\u0632 \u0647\u0641\u062a\u0647 \u0627\u0632 \u062a\u0627\u0631\u06cc\u062e \u0634\u0645\u0633\u06cc."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from archive_manager import to_gregorian
        gregorian = to_gregorian(int(day), str(month))
        if gregorian:
            names = ["\u062f\u0648\u0634\u0646\u0628\u0647", "\u0633\u0647\u200c\u0634\u0646\u0628\u0647", "\u0686\u0647\u0627\u0631\u0634\u0646\u0628\u0647", "\u067e\u0646\u062c\u0634\u0646\u0628\u0647", "\u062c\u0645\u0639\u0647", "\u0634\u0646\u0628\u0647", "\u06cc\u06a9\u0634\u0646\u0628\u0647"]
            return names[gregorian.weekday()]
    except Exception:
        pass
    return ""


def message_ledger_key(msg):
    """\u0634\u0646\u0627\u0633\u0647\u0654 \u06cc\u06a9\u062a\u0627\u06cc \u067e\u06cc\u0627\u0645 \u0628\u0631\u0627\u06cc \u062f\u0641\u062a\u0631 \u067e\u06cc\u0627\u0645\u200c\u0647\u0627\u06cc \u067e\u0631\u062f\u0627\u0632\u0634\u200c\u0634\u062f\u0647."""
    message_id = (msg.get("Message-ID") or "").strip()
    if message_id:
        return message_id
    return "|".join([
        decode_mime(msg.get("From", "")).strip().lower(),
        decode_mime(msg.get("Subject", "")).strip(),
        (msg.get("Date") or "").strip(),
    ])


def load_processed_emails():
    state = load_json(PROCESSED_EMAILS_FILE, {"processed": []})
    state.setdefault("processed", [])
    return state, list(state["processed"])


def mark_email_processed(state, key):
    if not key:
        return
    processed = state.setdefault("processed", [])
    if key in processed:
        return
    processed.append(key)
    state["processed"] = processed[-500:]
    save_json(PROCESSED_EMAILS_FILE, state)


def process_mailbox():
    """
    Checks incoming emails in rchep@physics.sharif.ir for subscription requests or confirmations.
    """
    if not MAIL_PASSWORD:
        print("Mail password missing; skipping inbox processing.")
        return

    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    # \u0645\u0647\u0627\u062c\u0631\u062a \u06cc\u06a9\u200c\u0628\u0627\u0631\u0647: \u0647\u0631 \u0639\u0636\u0648 \u062a\u0623\u06cc\u06cc\u062f\u0634\u062f\u0647\u0654 \u06a9\u0646\u0648\u0646\u06cc \u0627\u06cc\u0645\u06cc\u0644 \u062e\u0648\u0634\u200c\u0622\u0645\u062f\u0634 \u0631\u0627 \u06af\u0631\u0641\u062a\u0647 \u0627\u0633\u062a.
    migrated = False
    for entry in subscribers.get("list", []):
        if entry.get("status") == "confirmed" and "welcome_sent" not in entry:
            entry["welcome_sent"] = True
            migrated = True
    if migrated:
        save_json(SUBSCRIBERS_FILE, subscribers)
        print("Marked existing confirmed subscribers: welcome email never repeats.")
    email_map = {s["email"].lower(): s for s in subscribers["list"]}
    processed_state, processed_keys = load_processed_emails()
    processed_set = set(processed_keys)

    with imaplib.IMAP4_SSL(MAIL_HOST, 993, timeout=15) as mail:
        mail.login(MAIL_USER, MAIL_PASSWORD)
        mail.select("INBOX")
        
        # Check both UNSEEN and recent messages to avoid missing messages already marked read
        status, data = mail.search(None, "UNSEEN")
        unread_ids = data[0].split() if (status == "OK" and data[0]) else []
        
        # Also grab the latest 20 messages in case an email client or webmail marked it read
        status_all, data_all = mail.search(None, "ALL")
        all_ids = data_all[0].split()[-25:] if (status_all == "OK" and data_all[0]) else []
        
        # Combine preserving order and uniqueness
        combined_ids = []
        for mid in unread_ids + all_ids:
            if mid not in combined_ids:
                combined_ids.append(mid)

        if not combined_ids:
            print("No messages found to process.")
            return

        print(f"Examining {len(combined_ids)} messages for subscription actions...")

        for mid in combined_ids:
            status, res = mail.fetch(mid, "(RFC822)")
            if status != "OK" or not res:
                continue

            if not isinstance(res[0], tuple) or len(res[0]) < 2 or not isinstance(res[0][1], bytes):
                continue

            raw_msg = res[0][1]
            msg = email.message_from_bytes(raw_msg)
            from_hdr = decode_mime(msg.get("From", ""))
            subject = decode_mime(msg.get("Subject", "")).strip()

            from_addr_match = re.search(r"[\w\.-]+@[\w\.-]+", from_hdr)
            if not from_addr_match:
                continue
            sender_email = from_addr_match.group(0).lower()

            ledger_key = message_ledger_key(msg)
            if ledger_key in processed_set:
                print(f"Message already processed earlier; skipping ({mask_email(sender_email)}).")
                continue

            # Case 1: Confirmation
            confirm_match = re.search(r"CONFIRM_([0-9a-fA-F-]+)", subject)
            if not confirm_match:
                # also check in body
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                            confirm_match = re.search(r"CONFIRM_([0-9a-fA-F-]+)", body_text)
                            if confirm_match:
                                break

            if confirm_match:
                token = confirm_match.group(1).lower()
                for s in subscribers["list"]:
                    if s.get("token", "").lower() == token:
                        s["status"] = "confirmed"
                        s["confirmed_at"] = datetime.now(timezone.utc).isoformat()
                        print(f"Confirmed subscription: {mask_email(s['email'])}")
                        # \u0627\u06cc\u0645\u06cc\u0644 \u062e\u0648\u0634\u200c\u0622\u0645\u062f \u0641\u0642\u0637 \u06cc\u06a9\u200c\u0628\u0627\u0631 \u0628\u0631\u0627\u06cc \u0647\u0631 \u0639\u0636\u0648 \u0641\u0631\u0633\u062a\u0627\u062f\u0647 \u0645\u06cc\u200c\u0634\u0648\u062f (\u062c\u0644\u0648\u06af\u06cc\u0631\u06cc \u0627\u0632 \u0627\u06cc\u0645\u06cc\u0644 \u062a\u06a9\u0631\u0627\u0631\u06cc).
                        welcome_subject = "عضویت شما در فهرست سمینارهای RCHEP تأیید شد"
                        welcome_html = f"""
                        <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, Tahoma, sans-serif; line-height: 1.8; color: #1e293b; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
                          <h3 style="color: #0369a1;">مرکز پژوهشی فیزیک انرژی بالا (دانشگاه صنعتی شریف)</h3>
                          <p>عضویت شما با موفقیت قطعی گردید. از این پس آگهی سمینارها و رویدادهای علمی مرکز برای شما ارسال خواهد شد.</p>
                          <p style="font-size: 0.85rem; color: #64748b;">هر زمان مایل باشید، با زدن دکمه «لغو دریافت پیام‌ها» در پای ایمیل‌ها یا از طریق تارنمای rchep.ir می‌توانید عضویت خود را لغو فرمایید.</p>
                        </div>
                        """
                        if s.get("welcome_sent"):
                            print(f"Welcome email already sent earlier; not repeating for {mask_email(s['email'])}")
                        else:
                            try:
                                send_smtp_email(s["email"], welcome_subject, welcome_html)
                                s["welcome_sent"] = True
                                print(f"Welcome email sent once to {mask_email(s['email'])}")
                            except Exception as e:
                                print(f"Error sending welcome email: {e}")
                        break
                save_json(SUBSCRIBERS_FILE, subscribers)
                mark_email_processed(processed_state, ledger_key)
                continue

            # Case 1.5: Unsubscribe request
            is_unsub = any(k in subject.lower() for k in ["unsubscribe", "لغو عضویت", "لغو اشتراک", "انصراف", "unsub"])
            if not is_unsub:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace").lower()
                            if any(k in body_text for k in ["unsubscribe", "لغو عضویت", "لغو اشتراک"]):
                                is_unsub = True
                                break

            if is_unsub:
                unsub_found = False
                for s in subscribers["list"]:
                    if s.get("email", "").lower() == sender_email:
                        s["status"] = "unsubscribed"
                        s["unsubscribed_at"] = datetime.now(timezone.utc).isoformat()
                        unsub_found = True
                        print(f"Unsubscribed: {mask_email(sender_email)}")
                        break
                mark_email_processed(processed_state, ledger_key)
                if unsub_found:
                    save_json(SUBSCRIBERS_FILE, subscribers)
                    unsub_subject = "لغو دریافت آگهی سمینارهای RCHEP"
                    unsub_html = f"""
                    <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, Tahoma, sans-serif; line-height: 1.8; color: #1e293b; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
                      <h3 style="color: #0369a1;">مرکز پژوهشی فیزیک انرژی بالا (دانشگاه صنعتی شریف)</h3>
                      <p>درخواست شما انجام شد و دریافت آگهی سمینارها برای نشانی <b>{sender_email}</b> لغو گردید. دیگر پیامی برای شما ارسال نخواهد شد.</p>
                      <p style="font-size: 0.85rem; color: #64748b;">در صورت تمایل، هر زمان می‌توانید مجدداً از طریق تارنمای rchep.ir عضویت خود را فعال نمایید.</p>
                    </div>
                    """
                    try:
                        send_smtp_email(sender_email, unsub_subject, unsub_html)
                    except Exception as e:
                        print(f"Error sending unsub email to {mask_email(sender_email)}: {e}")
                else:
                    print(f"Unsubscribe requested for {mask_email(sender_email)}, but address not found in subscribers.")
                continue

            # Case 2: New subscription request via email (subject contains subscribe or عضویت, or body contains it)
            is_sub_req = any(k in subject.lower() for k in ["subscribe", "عضویت", "ثبت نام", "اشتراک"])
            if not is_sub_req:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            body_text = payload.decode(part.get_content_charset() or "utf-8", errors="replace").lower()
                            if any(k in body_text for k in ["subscribe", "عضویت", "ثبت نام", "اشتراک"]):
                                is_sub_req = True
                                break

            if is_sub_req:
                if sender_email in email_map:
                    if email_map[sender_email].get("status") == "confirmed":
                        print(f"Already confirmed: {mask_email(sender_email)}")
                        continue
                    if email_map[sender_email].get("status") == "pending":
                        print(f"Already pending verification: {mask_email(sender_email)}")
                        continue
                token = str(uuid.uuid4())
                entry = {
                    "email": sender_email,
                    "name": from_hdr.split("<")[0].replace('"', '').strip() if "<" in from_hdr else "",
                    "token": token,
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "confirmed_at": None
                }
                subscribers["list"] = [s for s in subscribers["list"] if s["email"].lower() != sender_email]
                subscribers["list"].append(entry)
                email_map[sender_email] = entry
                save_json(SUBSCRIBERS_FILE, subscribers)
                mark_email_processed(processed_state, ledger_key)
                print(f"Registered pending subscription for: {mask_email(sender_email)}")
                try:
                    send_verification_email(entry["name"], sender_email, token)
                except Exception as e:
                    print(f"Failed to send verification to {mask_email(sender_email)}: {e}")

        mail.logout()

def add_confirmed_contacts(addresses, source="seminar-contact-list"):
    """
    فهرست مخاطبین ارسالی از سوی برگزارکنندگان سمینار (استادان وردیان و سیری) را
    بدون تکرار و با وضعیت «تأییدشده» به فهرست مشترکان تارنما می‌افزاید.
    بازگشت: (افزوده‌شده‌ها، ارتقایافته‌ها)
    """
    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    entries = subscribers.setdefault("list", [])
    index = {}
    for item in entries:
        addr = (item.get("email") or "").strip().lower()
        if addr:
            index[addr] = item

    added, promoted = [], []
    for raw in addresses:
        addr = (raw or "").strip().lower().strip(".,;<>")
        if "@" not in addr or addr in INTERNAL_ADDRESSES:
            continue
        existing = index.get(addr)
        if existing is not None:
            # عضویت لغوشده هرگز بازگردانده نمی‌شود (احترام به انتخاب کاربر)
            if existing.get("status") == "pending":
                existing["status"] = "confirmed"
                existing["confirmed_at"] = datetime.now(timezone.utc).isoformat()
                promoted.append(addr)
            continue
        now = datetime.now(timezone.utc).isoformat()
        entry = {
            "email": addr,
            "name": "",
            "token": str(uuid.uuid4()),
            "status": "confirmed",
            "created_at": now,
            "confirmed_at": now,
            "source": source,
        }
        entries.append(entry)
        index[addr] = entry
        added.append(addr)

    if added or promoted:
        save_json(SUBSCRIBERS_FILE, subscribers)

    return added, promoted


def mask_email(address):
    """نشانی ایمیل را برای لاگ‌های عمومی گیت‌هاب پوشیده می‌کند (مخزن مرکز عمومی است)."""
    address = (address or "").strip()
    if "@" not in address:
        return "***"
    local, _, domain = address.partition("@")
    return f"{(local[:1] if len(local) > 1 else '')}***@{domain}"


def build_notice_html(kind, details, inline_poster=False):
    """\u0642\u0627\u0644\u0628 \u0622\u0631\u0627\u0633\u062a\u0647\u060c \u0631\u0627\u0633\u062a\u200c\u0686\u06cc\u0646 \u0648 \u0628\u06cc\u200c\u062d\u0627\u0634\u06cc\u0647\u0654 \u0627\u0637\u0644\u0627\u0639\u06cc\u0647 (\u0633\u0645\u06cc\u0646\u0627\u0631 \u06cc\u0627 \u0646\u0634\u0633\u062a)."""
    title = clean_field(details.get("title", ""))
    speaker = clean_field(details.get("speaker", ""))
    affiliation = clean_field(details.get("affiliation", ""))
    day = str(details.get("day", "") or "").strip()
    month = clean_field(details.get("month", ""))
    year = clean_field(details.get("year", ""))
    time_text = clean_field(details.get("time", ""))
    location = clean_field(details.get("location", ""))
    if not location or "\u062c\u0646\u0627\u0628" in location:
        location = DEFAULT_LOCATION

    date_display = clean_field(details.get("date_display", "")) or " ".join(
        part for part in [clean_field(details.get("weekday", "")) or weekday_name(day, month), day, month, year] if part
    )

    if kind == "seminar":
        pill = "\u0633\u0645\u06cc\u0646\u0627\u0631 \u0641\u06cc\u0632\u06cc\u06a9 \u0627\u0646\u0631\u0698\u06cc \u0628\u0627\u0644\u0627"
    else:
        pill = "\u0646\u0634\u0633\u062a \u0639\u0644\u0645\u06cc \u0645\u0631\u06a9\u0632"

    rows = []
    if speaker:
        rows.append(("\u0633\u062e\u0646\u0631\u0627\u0646", f"{speaker} ({affiliation})" if affiliation else speaker))
    if date_display:
        rows.append(("\u0632\u0645\u0627\u0646", f"{date_display}" + (f" \u2014 \u0633\u0627\u0639\u062a {time_text}" if time_text else "")))
    if location:
        rows.append(("\u0645\u06a9\u0627\u0646", location))

    rows_html = "".join(
        '<tr><td style="padding:7px 0;color:#64748b;width:90px;vertical-align:top;">' + label + ":"
        + '</td><td style="padding:7px 0;color:#0f172a;font-weight:600;">' + value + "</td></tr>"
        for label, value in rows
    )

    poster_html = ""
    if inline_poster:
        poster_html = (
            '<img src="cid:' + NOTICE_POSTER_CID + '" alt="\u067e\u0648\u0633\u062a\u0631" '
            'style="width:100%;max-width:640px;border:1px solid #e2e8f0;border-radius:10px;margin:20px 0 2px;display:block;">'
        )

    return f"""
    <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, Arial, sans-serif; line-height: 1.9; color: #1e293b; max-width: 640px; margin: auto; padding: 26px; border: 1px solid #e2e8f0; border-radius: 14px; background: #ffffff;">
      <div style="border-bottom: 2px solid #0284c7; padding-bottom: 10px; margin-bottom: 18px;">
        <h2 style="color: #0369a1; margin: 0; font-size: 1.25rem;">\u0645\u0631\u06a9\u0632 \u067e\u0698\u0648\u0647\u0634\u06cc \u0641\u06cc\u0632\u06cc\u06a9 \u0627\u0646\u0631\u0698\u06cc \u0628\u0627\u0644\u0627 (RCHEP)</h2>
        <span style="font-size: 0.85rem; color: #64748b;">\u062f\u0627\u0646\u0634\u06af\u0627\u0647 \u0635\u0646\u0639\u062a\u06cc \u0634\u0631\u06cc\u0641</span>
      </div>
      <span style="display: inline-block; background: #e0f2fe; color: #0369a1; font-size: 0.78rem; padding: 3px 12px; border-radius: 999px; margin-bottom: 12px;">{pill}</span>
      <h3 style="color: #0f172a; margin: 6px 0 0; font-size: 1.15rem; line-height: 1.7;">{title}</h3>
      <table style="width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 0.95rem;">{rows_html}</table>
      {poster_html}
      <div style="text-align: center; margin: 24px 0 6px;">
        <a href="https://rchep.ir/events.html" style="background-color: #0284c7; color: #ffffff; padding: 11px 26px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">\u0645\u0634\u0627\u0647\u062f\u0647 \u062f\u0631 \u062a\u0627\u0631\u0646\u0645\u0627</a>
      </div>
      <div style="border-top: 1px solid #e2e8f0; padding-top: 14px; margin-top: 26px; font-size: 0.8rem; color: #94a3b8;">
        <div>\u0627\u06cc\u0646 \u067e\u06cc\u0627\u0645 \u0628\u0631\u0627\u06cc \u0627\u0639\u0636\u0627\u06cc \u062a\u0623\u06cc\u06cc\u062f\u0634\u062f\u0647\u0654 \u0645\u0631\u06a9\u0632 \u0641\u06cc\u0632\u06cc\u06a9 \u0627\u0646\u0631\u0698\u06cc \u0628\u0627\u0644\u0627 \u0627\u0631\u0633\u0627\u0644 \u0634\u062f\u0647 \u0627\u0633\u062a.</div>
        <a href="mailto:{MAIL_USER}?subject=UNSUBSCRIBE" style="color: #94a3b8; text-decoration: underline;">\u0644\u063a\u0648 \u062f\u0631\u06cc\u0627\u0641\u062a \u067e\u06cc\u0627\u0645\u200c\u0647\u0627 (Unsubscribe)</a>
      </div>
    </div>
    """


def broadcast_notice(kind, details, poster_name=None, recipients=None):
    """\u06cc\u06a9 \u0627\u0637\u0644\u0627\u0639\u06cc\u0647 \u0631\u0627 \u0628\u0631\u0627\u06cc \u0647\u0645\u0647\u0654 \u0645\u0634\u062a\u0631\u06a9\u0627\u0646 \u062a\u0623\u06cc\u06cc\u062f\u0634\u062f\u0647 \u0645\u06cc\u200c\u0641\u0631\u0633\u062a\u062f. \u0628\u0627\u0632\u06af\u0634\u062a: \u0634\u0645\u0627\u0631 \u06af\u06cc\u0631\u0646\u062f\u06af\u0627\u0646."""
    details = dict(details or {})
    for field in ("title", "speaker", "affiliation", "time", "month", "location"):
        if details.get(field):
            details[field] = clean_field(details[field])

    if not details.get("title"):
        print("Notice aborted: title is empty.")
        return 0
    if has_placeholder(details.get("title", ""), details.get("speaker", "")):
        print("Notice aborted: image reference or file name left in title/speaker.")
        return 0

    poster_path = resolve_poster_path(poster_name or details.get("poster"))
    inline_images = [(NOTICE_POSTER_CID, poster_path)] if poster_path else []
    html_content = build_notice_html(kind, details, inline_poster=bool(poster_path))

    if recipients is None:
        subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
        recipients = [s["email"] for s in subscribers.get("list", []) if s.get("status") == "confirmed"]
    recipients = [r for r in recipients if r]
    if not recipients:
        print("No confirmed subscribers to notify.")
        return 0

    speaker = details.get("speaker", "")
    if kind == "seminar":
        subject = f"[\u0633\u0645\u06cc\u0646\u0627\u0631 RCHEP] {details['title']}" + (f" \u2014 {speaker}" if speaker else "")
    else:
        subject = f"[\u0646\u0634\u0633\u062a RCHEP] {details['title']}" + (f" \u2014 {speaker}" if speaker else "")
    date_display = clean_field(details.get("date_display", "")) or " ".join(
        part for part in [clean_field(details.get("weekday", "")) or weekday_name(str(details.get("day", "")), details.get("month", "")),
                          str(details.get("day", "") or "").strip(), details.get("month", "")] if part
    )
    if date_display:
        subject += f" ({date_display})"
    subject = " ".join(clean_field(subject).split())

    dry_run = os.environ.get("RCHEP_DRY_RUN") == "1"
    print(f"Sending notice ({kind}) to {len(recipients)} confirmed subscriber(s)...")
    if poster_path:
        print(f"Inline poster: {os.path.basename(poster_path)} (cid:{NOTICE_POSTER_CID})")
    else:
        print("No poster found for this notice; sending without image.")
    print(f"Subject: {subject}")

    sent = 0
    for recipient in recipients:
        if dry_run:
            sent += 1
            continue
        try:
            send_smtp_email(recipient, subject, html_content, inline_images=inline_images)
            print(f"Sent notice to: {mask_email(recipient)}")
            sent += 1
        except Exception as e:
            print(f"Failed to send to {mask_email(recipient)}: {e}")

    if dry_run:
        preview_path = os.path.join(DATA_DIR, "notice_preview.html")
        with open(preview_path, "w", encoding="utf-8") as handle:
            handle.write(html_content)
        print(f"[dry-run] nothing sent; preview written to {preview_path}")
    return sent


def broadcast_seminar(seminar_details, poster_filename=None):
    """
    Broadcasts newly added seminar announcement to all confirmed subscribers.
    \u067e\u0648\u0633\u062a\u0631 \u062f\u0631 \u062e\u0648\u062f \u0627\u06cc\u0645\u06cc\u0644 (inline) \u062f\u0631\u062c \u0645\u06cc\u200c\u0634\u0648\u062f \u0648 \u062f\u0631 \u0645\u062a\u0646 \u0647\u06cc\u0686 \u0627\u0631\u062c\u0627\u0639 \u062e\u0627\u0645 \u062a\u0635\u0648\u06cc\u0631\u06cc \u0646\u0645\u06cc\u200c\u0622\u06cc\u062f.
    """
    if not MAIL_PASSWORD:
        print("Mail password missing; cannot broadcast.")
        return False

    day = seminar_details.get("day", "")
    month = seminar_details.get("month", "")
    year = seminar_details.get("year", "1405")
    title = seminar_details.get("title", "")
    date_key = f"{year}_{month}_{day}"
    # \u0646\u0634\u0627\u0646\u0647 \u06cc\u06a9\u062a\u0627\u06cc \u0647\u0631 \u0633\u0645\u06cc\u0646\u0627\u0631: \u062a\u0627\u0631\u06cc\u062e + \u0639\u0646\u0648\u0627\u0646\u060c \u062a\u0627 \u062f\u0648 \u0633\u0645\u06cc\u0646\u0627\u0631 \u0647\u0645\u200c\u0631\u0648\u0632 \u0647\u0645 \u0647\u0631 \u06a9\u062f\u0627\u0645 \u0627\u06cc\u0645\u06cc\u0644 \u062c\u062f\u0627 \u06af\u06cc\u0631\u0646\u062f
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", title, flags=re.UNICODE).strip("-")[:40]
    seminar_id = f"{date_key}_{slug}" if slug else date_key

    sent_data = load_json(SENT_SEMINARS_FILE, {"broadcasted": []})
    broadcasted = sent_data.get("broadcasted", [])
    # \u0627\u0645\u06a9\u0627\u0646 \u0641\u0631\u0633\u062a\u0627\u062f\u0646 \u062f\u0648\u0628\u0627\u0631\u0647\u0654 \u0627\u0637\u0644\u0627\u0639\u06cc\u0647\u0654 \u06cc\u06a9 \u062a\u0627\u0631\u06cc\u062e \u0627\u0632 \u0631\u0627\u0647 \u0645\u062a\u063a\u06cc\u0631 \u0645\u062d\u06cc\u0637\u06cc RCHEP_RESEND_DATES
    resend_dates = {d.strip() for d in os.environ.get("RCHEP_RESEND_DATES", "").split(",") if d.strip()}
    force_resend = date_key in resend_dates
    if force_resend:
        print(f"Resend requested for {date_key}; previous send marker will be ignored.")
        broadcasted = [k for k in broadcasted if k != date_key and not str(k).startswith(date_key + "_")]
        sent_data["broadcasted"] = broadcasted
    # \u0646\u06af\u0647\u0628\u0627\u0646 \u0645\u0647\u0627\u062c\u0631\u062a: \u0646\u0634\u0627\u0646\u0647\u200c\u0647\u0627\u06cc \u0642\u062f\u06cc\u0645\u06cc \u06a9\u0647 \u0639\u0646\u0648\u0627\u0646\u0634\u0627\u0646 \u0646\u0627\u062e\u0648\u0627\u0646\u0627 (\u0646\u0627\u0645 \u067e\u06cc\u0648\u0633\u062a) \u062b\u0628\u062a \u0634\u062f\u0647 \u0628\u0648\u062f\u060c
    # \u06a9\u0644 \u0622\u0646 \u062a\u0627\u0631\u06cc\u062e \u0631\u0627 \u0627\u0631\u0633\u0627\u0644\u200c\u0634\u062f\u0647 \u062a\u0644\u0642\u06cc \u0645\u06cc\u200c\u06a9\u0646\u0646\u062f \u062a\u0627 \u0627\u0635\u0644\u0627\u062d \u0639\u0646\u0648\u0627\u0646 \u0628\u0627\u0639\u062b \u0627\u06cc\u0645\u06cc\u0644 \u062a\u06a9\u0631\u0627\u0631\u06cc \u0646\u0634\u0648\u062f.
    legacy_covered_dates = set()
    for key in broadcasted:
        match = re.match(r"^(\d{4}_[^_]+_\d{1,2})_(.+)$", key or "")
        if match and re.match(r"^(?:image|attachment|cid)[-_]", match.group(2)):
            legacy_covered_dates.add(match.group(1))
    if force_resend:
        legacy_covered_dates.discard(date_key)
    if not force_resend and (seminar_id and (seminar_id in broadcasted or date_key in broadcasted or date_key in legacy_covered_dates)):
        print(f"Seminar {seminar_id} already broadcasted. Skipping.")
        return False

    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    confirmed_emails = [s["email"] for s in subscribers.get("list", []) if s.get("status") == "confirmed"]
    if not confirmed_emails:
        print("No confirmed subscribers to notify.")
        return False

    sent = broadcast_notice("seminar", seminar_details, poster_name=poster_filename, recipients=confirmed_emails)
    if not sent:
        return False

    if seminar_id:
        sent_data.setdefault("broadcasted", []).append(seminar_id)
        save_json(SENT_SEMINARS_FILE, sent_data)

    return True


def send_queued_notices():
    """\u0627\u0637\u0644\u0627\u0639\u06cc\u0647\u200c\u0647\u0627\u06cc \u0622\u0645\u0627\u062f\u0647\u0654 \u0628\u06cc\u0631\u0648\u0646 \u0627\u0632 \u0645\u0633\u06cc\u0631 \u0633\u0645\u06cc\u0646\u0627\u0631 (\u0645\u0627\u0646\u0646\u062f \u0646\u0634\u0633\u062a \u0647\u0648\u0634\u200c\u0648\u0627\u0631\u0647) \u0631\u0627 \u0627\u0632 data/notice_queue.json \u0645\u06cc\u200c\u0641\u0631\u0633\u062a\u062f."""
    queue = load_json(NOTICE_QUEUE_FILE, {"notices": []})
    notices = queue.get("notices", [])
    if not notices:
        print("Notice queue is empty.")
        return False

    sent_any = False
    for notice in notices:
        if notice.get("sent_at"):
            continue
        details = notice.get("details", {})
        kinds = notice.get("kind") or "meeting"
        label = notice.get("key") or details.get("title", "")
        print(f"Queued notice: {label}")
        count = broadcast_notice(kinds, details, poster_name=notice.get("poster"))
        if count and os.environ.get("RCHEP_DRY_RUN") == "1":
            print(f"[dry-run] notice stays queued, not marked as sent: {label}")
        elif count:
            notice["sent_at"] = datetime.now(timezone.utc).isoformat()
            notice["recipients"] = count
            sent_any = True
        else:
            print(f"Notice not sent (no recipients or unreadable fields): {label}")
    if sent_any:
        save_json(NOTICE_QUEUE_FILE, queue)
    return sent_any


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "process"
    if action == "process":
        process_mailbox()
    elif action in ("send-notices", "notices"):
        send_queued_notices()
    elif action == "dry-run-notices":
        os.environ["RCHEP_DRY_RUN"] = "1"
        send_queued_notices()
    elif action == "broadcast":
        # test / sample broadcast call
        pass
