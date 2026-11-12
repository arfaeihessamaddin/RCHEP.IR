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

def send_smtp_email(to_email, subject, html_content, text_content=None):
    if not MAIL_PASSWORD:
        raise RuntimeError("SHARIF_MAIL_PASSWORD is not set.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"RCHEP Center <{MAIL_USER}>"
    msg["To"] = to_email

    if text_content:
        msg.attach(MIMEText(text_content, "plain", "utf-8"))
    msg.attach(MIMEText(html_content, "html", "utf-8"))

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

def process_mailbox():
    """
    Checks incoming emails in rchep@physics.sharif.ir for subscription requests or confirmations.
    """
    if not MAIL_PASSWORD:
        print("Mail password missing; skipping inbox processing.")
        return

    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    email_map = {s["email"].lower(): s for s in subscribers["list"]}

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
                        # Send welcome confirmation
                        welcome_subject = "عضویت شما در فهرست سمینارهای RCHEP تأیید شد"
                        welcome_html = f"""
                        <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, Tahoma, sans-serif; line-height: 1.8; color: #1e293b; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
                          <h3 style="color: #0369a1;">مرکز پژوهشی فیزیک انرژی بالا (دانشگاه صنعتی شریف)</h3>
                          <p>عضویت شما با موفقیت قطعی گردید. از این پس آگهی سمینارها و رویدادهای علمی مرکز برای شما ارسال خواهد شد.</p>
                          <p style="font-size: 0.85rem; color: #64748b;">هر زمان مایل باشید، با زدن دکمه «لغو دریافت پیام‌ها» در پای ایمیل‌ها یا از طریق تارنمای rchep.ir می‌توانید عضویت خود را لغو فرمایید.</p>
                        </div>
                        """
                        try:
                            send_smtp_email(s["email"], welcome_subject, welcome_html)
                        except Exception as e:
                            print(f"Error sending welcome email: {e}")
                        break
                save_json(SUBSCRIBERS_FILE, subscribers)
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


def broadcast_seminar(seminar_details, poster_filename=None):
    """
    Broadcasts newly added seminar announcement to all confirmed subscribers.
    """
    if not MAIL_PASSWORD:
        print("Mail password missing; cannot broadcast.")
        return False

    day = seminar_details.get("day", "")
    month = seminar_details.get("month", "")
    year = seminar_details.get("year", "1405")
    title = seminar_details.get("title", "")
    date_key = f"{year}_{month}_{day}"
    # نشانه یکتای هر سمینار: تاریخ + عنوان، تا دو سمینار هم‌روز هم هر کدام ایمیل جدا بگیرند
    slug = re.sub(r"[^\w\u0600-\u06FF]+", "-", title, flags=re.UNICODE).strip("-")[:40]
    seminar_id = f"{date_key}_{slug}" if slug else date_key

    sent_data = load_json(SENT_SEMINARS_FILE, {"broadcasted": []})
    broadcasted = sent_data.get("broadcasted", [])
    # نگهبان مهاجرت: نشانه‌های قدیمی که عنوانشان ناخوانا (نام پیوست) ثبت شده بود،
    # کل آن تاریخ را ارسال‌شده تلقی می‌کنند تا اصلاح عنوان باعث ایمیل تکراری نشود.
    legacy_covered_dates = set()
    for key in broadcasted:
        match = re.match(r"^(\d{4}_[^_]+_\d{1,2})_(.+)$", key or "")
        if match and re.match(r"^(?:image|attachment|cid)[-_]", match.group(2)):
            legacy_covered_dates.add(match.group(1))
    if seminar_id and (seminar_id in broadcasted or date_key in broadcasted or date_key in legacy_covered_dates):
        print(f"Seminar {seminar_id} already broadcasted. Skipping.")
        return False

    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    confirmed_emails = [s["email"] for s in subscribers.get("list", []) if s.get("status") == "confirmed"]

    if not confirmed_emails:
        print("No confirmed subscribers to notify.")
        return False
    speaker = seminar_details.get("speaker", "")
    affiliation = seminar_details.get("affiliation", "")
    time_str = seminar_details.get("time", "۱۳:۳۰")
    location = seminar_details.get("location")
    if not location or "جناب" in location:
        location = "اتاق سمینار RCHEP (دانشکده فیزیک) + مجازی (vc.sharif.edu/ch/physics-high-energy)"

    subject = f"[سمینار RCHEP] {title} — {speaker} ({day} {month})"

    html_content = f"""
    <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Tahoma, Arial, sans-serif; line-height: 1.8; color: #1e293b; max-width: 650px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
      <div style="border-bottom: 2px solid #0284c7; padding-bottom: 12px; margin-bottom: 20px;">
        <h2 style="color: #0369a1; margin: 0; font-size: 1.3rem;">مرکز پژوهشی فیزیک انرژی بالا (RCHEP)</h2>
        <span style="font-size: 0.85rem; color: #64748b;">دانشگاه صنعتی شریف</span>
      </div>
      <h3 style="color: #0f172a; margin-top: 0; font-size: 1.2rem;">{title}</h3>
      <table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 0.95rem;">
        <tr><td style="padding: 6px 0; color: #64748b; width: 100px;">سخنران:</td><td style="font-weight: bold; color: #0f172a;">{speaker} {f'({affiliation})' if affiliation else ''}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">زمان:</td><td style="color: #0f172a;">دوشنبه {day} {month}، ساعت {time_str}</td></tr>
        <tr><td style="padding: 6px 0; color: #64748b;">مکان:</td><td style="color: #0f172a;">{location}</td></tr>
      </table>
      <div style="margin: 25px 0; text-align: center;">
        <a href="https://rchep.ir/events.html" style="background-color: #0284c7; color: #ffffff; padding: 10px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">مشاهده جزئیات و پوستر در تارنما</a>
      </div>
      <div style="border-top: 1px solid #e2e8f0; padding-top: 15px; margin-top: 30px; display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: #94a3b8;">
        <span>این پیام برای اعضای تأییدشده سمینارهای مرکز فیزیک انرژی بالا ارسال شده است.</span>
        <a href="mailto:{MAIL_USER}?subject=UNSUBSCRIBE" style="color: #94a3b8; text-decoration: underline;">لغو دریافت پیام‌ها (Unsubscribe)</a>
      </div>
    </div>
    """

    print(f"Broadcasting to {len(confirmed_emails)} confirmed subscriber(s)...")
    for recipient in confirmed_emails:
        try:
            send_smtp_email(recipient, subject, html_content)
            print(f"Sent seminar notice to: {mask_email(recipient)}")
        except Exception as e:
            print(f"Failed to send to {mask_email(recipient)}: {e}")

    if seminar_id:
        if "broadcasted" not in sent_data:
            sent_data["broadcasted"] = []
        sent_data["broadcasted"].append(seminar_id)
        save_json(SENT_SEMINARS_FILE, sent_data)

    return True


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "process"
    if action == "process":
        process_mailbox()
    elif action == "broadcast":
        # test / sample broadcast call
        pass
