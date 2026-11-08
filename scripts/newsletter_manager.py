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
      <p>درخواست شما برای دریافت آگهی سمینارها و رویدادهای هفتگی مرکز پژوهشی فیزیک انرژی بالا دریافت گردید.</p>
      <p>برای اطمینان از صحت نشانی رایانامه، لطفاً بر روی پیوند زیر پاسخ (Reply) دهید، یا کافیست همین ایمیل را بدون تغییر ارسال (Reply) فرمایید:</p>
      <div style="text-align: center; margin: 30px 0;">
        <a href="mailto:{verify_email_addr}?subject=CONFIRM_{token}" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">تأیید عضویت با یک زنش (Click)</a>
      </div>
      <p style="font-size: 0.85rem; color: #64748b; background: #f8fafc; padding: 10px 14px; border-radius: 6px;">
        شناسه اختصاصی شما: <code>{token}</code><br>
        در صورتی که شما این درخواست را ثبت نکرده‌اید، این پیام را نادیده بگیرید؛ هیچ پیامی بدون تأیید برای شما فرستاده نخواهد شد.
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
                        print(f"Confirmed subscription: {s['email']}")
                        # Send welcome confirmation
                        welcome_subject = "عضویت شما در فهرست سمینارهای RCHEP تأیید شد"
                        welcome_html = f"""
                        <div dir="rtl" style="font-family: -apple-system, BlinkMacSystemFont, Tahoma, sans-serif; line-height: 1.8; color: #1e293b; max-width: 600px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px;">
                          <h3 style="color: #0369a1;">مرکز پژوهشی فیزیک انرژی بالا (دانشگاه صنعتی شریف)</h3>
                          <p>عضویت شما با موفقیت قطعی گردید. از این پس آگهی سمینارها برای شما ارسال خواهد شد.</p>
                        </div>
                        """
                        try:
                            send_smtp_email(s["email"], welcome_subject, welcome_html)
                        except Exception as e:
                            print(f"Error sending welcome email: {e}")
                        break
                save_json(SUBSCRIBERS_FILE, subscribers)
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
                    if email_map[sender_email]["status"] == "confirmed":
                        print(f"Already confirmed: {sender_email}")
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
                print(f"Registered pending subscription for: {sender_email}")
                try:
                    send_verification_email(entry["name"], sender_email, token)
                except Exception as e:
                    print(f"Failed to send verification to {sender_email}: {e}")

        mail.logout()

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
    seminar_id = f"{year}_{month}_{day}"

    sent_data = load_json(SENT_SEMINARS_FILE, {"broadcasted": []})
    if seminar_id and seminar_id in sent_data.get("broadcasted", []):
        print(f"Seminar {seminar_id} already broadcasted. Skipping.")
        return False

    subscribers = load_json(SUBSCRIBERS_FILE, {"list": []})
    confirmed_emails = [s["email"] for s in subscribers.get("list", []) if s.get("status") == "confirmed"]

    if not confirmed_emails:
        print("No confirmed subscribers to notify.")
        return False
    title = seminar_details.get("title", "")
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
      <p style="font-size: 0.8rem; color: #94a3b8; border-top: 1px solid #e2e8f0; padding-top: 15px; margin-top: 30px;">
        این پیام برای اعضای تأییدشده فهرست سمینارهای مرکز فیزیک انرژی بالا دانشگاه صنعتی شریف ارسال شده است.
      </p>
    </div>
    """

    print(f"Broadcasting to {len(confirmed_emails)} confirmed subscriber(s)...")
    for recipient in confirmed_emails:
        try:
            send_smtp_email(recipient, subject, html_content)
            print(f"Sent seminar notice to: {recipient}")
        except Exception as e:
            print(f"Failed to send to {recipient}: {e}")

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
