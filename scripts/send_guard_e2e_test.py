#!/usr/bin/env python3
"""
آزمون سرتاسری گاردریل‌های ارسال، بدون هیچ تماس شبکه‌ای.

سه چیز را روی کد واقعی `newsletter_manager` می‌سنجد:
  ۱. ایمیل خوش‌آمد/تأیید عضویت برای یک شخص فقط یک‌بار می‌رود، حتی اگر صندوق
     پستی و نامه‌ها چند بار پیمایش شوند (ریشهٔ «۷ ایمیل برای یک نفر»).
  ۲. اطلاعیه برای هر شخص یک بار می‌رود و بازفرست همان اطلاعیه مسدود می‌شود.
  ۳. نشانی‌های هم‌هویت (نقطه‌های جیمیل، +tag) پیش از ارسال یکی می‌شوند.

اجرا:  python3 scripts/send_guard_e2e_test.py       (کد خروج ۰ در صورت گذر)
"""
import email
import json
import os
import shutil
import subprocess
import sys
import tempfile

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)

TMP = tempfile.mkdtemp(prefix="rchep-e2e-")
DATA = os.path.join(TMP, "data")
os.makedirs(DATA, exist_ok=True)

# هیچ ارسال واقعی و هیچ همگام‌سازی ابری نباید رخ دهد
os.environ["SHARIF_MAIL_PASSWORD"] = "test-only-not-a-real-password"
os.environ["SHARIF_MAIL_USER"] = "rchep@physics.sharif.ir"
os.environ["SHARIF_MAIL_HOST"] = "localhost"
os.environ["SHARIF_MAIL_PORT"] = "2525"
os.environ["RCHEP_SEND_LEDGER"] = os.path.join(DATA, "send_log.jsonl")
os.environ.pop("RCHEP_DRY_RUN", None)
os.environ.pop("RCHEP_FORCE_SEND", None)
subprocess.run = lambda *a, **k: None  # save_json نباید sync_sharif_cloud را صدا بزند

import newsletter_manager as nm  # noqa: E402

nm.SUBSCRIBERS_FILE = os.path.join(DATA, "subscribers.json")
nm.PROCESSED_EMAILS_FILE = os.path.join(DATA, "processed_emails.json")
nm.NOTICE_QUEUE_FILE = os.path.join(DATA, "notice_queue.json")

failures = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} — {name}" + (f" : {detail}" if detail and not condition else ""))
    if not condition:
        failures.append(name)


TOKEN = "1111aaaa-2222-bbbb-3333-cccc4444dddd"
MEMBER = "member.one@example.org"

with open(nm.SUBSCRIBERS_FILE, "w", encoding="utf-8") as handle:
    json.dump({"list": [{"email": MEMBER, "name": "", "token": TOKEN, "status": "pending",
                         "created_at": "2026-11-01T00:00:00+00:00", "confirmed_at": None}]},
              handle, ensure_ascii=False, indent=2)

# نامهٔ تأییدی که یک مشتری واقعی می‌فرستد؛ سرصفحهٔ CONFIRM_<token> بدون کدگذاری
# می‌آید (در q-encoding زیرخط به فاصله تبدیل می‌شود و آزمون را بی‌اعتبار می‌کند).
CONFIRM_RAW = (
    f"From: Member One <{MEMBER}>\r\n"
    f"To: rchep@physics.sharif.ir\r\n"
    f"Subject: CONFIRM_{TOKEN}\r\n"
    "Message-ID: <confirm-1@example.org>\r\n"
    "MIME-Version: 1.0\r\n"
    "Content-Type: text/plain; charset=utf-8\r\n\r\n"
    "confirmed\r\n"
).encode("utf-8")

SENT = []


class FakeSMTP:
    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        SENT.append({"to": msg["To"], "subject": msg["Subject"], "at": len(SENT)})


class FakeIMAP:
    def __init__(self, host, port, timeout=None):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        pass

    def select(self, mailbox):
        return ("OK", [b"1"])

    def search(self, charset, criteria):
        return ("OK", [b"1"])

    def fetch(self, mid, what):
        return ("OK", [(b"1 (RFC822 {10}", CONFIRM_RAW)])

    def store(self, *args):
        return ("OK", [b"1"])

    def logout(self):
        pass


nm.smtplib.SMTP = FakeSMTP
nm.imaplib.IMAP4_SSL = FakeIMAP

# ۱) هفت پیمایش پیاپی صندوق پستی (همان وضعیتی که ایمیل تکراری می‌ساخت)
for run in range(1, 8):
    nm.process_mailbox()
    if run == 1:
        with open(nm.SUBSCRIBERS_FILE, encoding="utf-8") as handle:
            entry = json.load(handle)["list"][0]
        check("process: welcome_sent claimed in subscribers.json after run 1", entry.get("welcome_sent") is True)
    # بدترین حالت: دفترچهٔ پردازش نامه‌ها پاک شود تا همان نامه دوباره پردازش شود
    with open(nm.PROCESSED_EMAILS_FILE, "w", encoding="utf-8") as handle:
        json.dump({"processed": []}, handle)

welcome_sends = [m for m in SENT if "تأیید شد" in m["subject"]]
check("welcome: exactly one welcome email across 7 mailbox passes", len(welcome_sends) == 1, str(len(welcome_sends)))
check("welcome: sent to the member only", all(m["to"].lower() == MEMBER for m in welcome_sends), str(welcome_sends))

# ۲) اطلاعیه‌های هوشواره: اطلاعیه هم‌روز و هم‌عنوان
SENT.clear()
EVENT = {"title": "نشست هوشواره", "speaker": "سخنران نمونه", "day": "23", "month": "آبان",
         "year": "1405", "time": "۱۵:۰۰", "location": "اتاق سمینار RCHEP"}
MIXED = ["a.b@gmail.com", "AB+news@gmail.com", "c@example.org"]
first = nm.broadcast_notice("seminar", EVENT, recipients=list(MIXED), notice_key="هوشواره_1405_آبان_23")
check("notice: first pass sends one copy per person", first == 2 and len(SENT) == 2, f"sent={first} smtp={len(SENT)}")
check("notice: gmail dots/tags collapsed before sending",
      sorted(m["to"].lower() for m in SENT) == ["a.b@gmail.com", "c@example.org"], str(SENT))

SENT.clear()
second = nm.broadcast_notice("seminar", EVENT, recipients=list(MIXED), notice_key="هوشواره_1405_آبان_23")
check("notice: repeat of the same event is blocked", second == 0 and SENT == [], f"sent={second}")

SENT.clear()
forced = nm.broadcast_notice("seminar", EVENT, recipients=list(MIXED), notice_key="هوشواره_1405_آبان_23", force=True)
check("notice: deliberate resend (force) goes out again", forced == 2 and len(SENT) == 2, f"sent={forced}")

# ۳) شکست SMTP باید ادعا را آزاد کند تا تلاش دوباره ممکن باشد
SENT.clear()
original_send_message = FakeSMTP.send_message
calls = {"n": 0}


def flaky_send_message(self, msg):
    calls["n"] += 1
    if calls["n"] == 1:
        raise RuntimeError("simulated SMTP failure")
    SENT.append({"to": msg["To"], "subject": msg["Subject"], "at": len(SENT)})


FakeSMTP.send_message = flaky_send_message
try:
    nm.send_smtp_email("retry@example.org", "s", "<p>x</p>", kind="notice", key="retry-key")
except RuntimeError:
    pass
retried = nm.send_smtp_email("retry@example.org", "s", "<p>x</p>", kind="notice", key="retry-key")
FakeSMTP.send_message = original_send_message
check("failure: failed send is retried, not lost", retried is True and len(SENT) == 1, f"retried={retried}")

blocked_retry = nm.send_smtp_email("retry@example.org", "s", "<p>x</p>", kind="notice", key="retry-key")
check("failure: successful retry is then not repeated", blocked_retry is False)

# ۴) حریم خصوصی: دفتر ارسال نباید نشانی خام داشته باشد
raw_ledger = open(os.environ["RCHEP_SEND_LEDGER"], encoding="utf-8").read()
check("privacy: ledger holds no raw address", "@" not in raw_ledger.replace("rchep@physics.sharif.ir", ""))

print()
shutil.rmtree(TMP, ignore_errors=True)
if failures:
    print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
    sys.exit(1)
print("All end-to-end guardrail checks passed.")
sys.exit(0)
