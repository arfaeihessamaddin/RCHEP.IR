#!/usr/bin/env python3
"""
گاردریل‌های ارسال ایمیل مرکز (RCHEP Send Guardrails)
────────────────────────────────────────────────────
هدف: هیچ پیامی دو بار به یک شخص نرود و هیچ اجرایی نتواند حلقهٔ ارسال بسازد.

قواعد:
  ۱) ادعا پیش از ارسال (claim-before-send): پیش از تماس با SMTP یک «ادعا» در
     دفتر ارسال ثبت می‌شود؛ اگر ارسال شکست خورد، ادعا «آزاد» می‌شود تا اجرای
     بعدی بتواند دوباره تلاش کند.
  ۲) یک پیام، یک بار، برای یک شخص: کلید هر ارسال (نشانی + گونهٔ پیام + نشانهٔ
     رویداد) در بازهٔ خنک‌شدن (پیش‌فرض ۲۴ ساعت) فقط یک‌بار پذیرفته می‌شود.
  ۳) یک رونوشت برای هر شخص: نشانی‌های هم‌هویت (مثلاً نقطه‌های جیمیل و برچسب
     +tag) پیش از ارسال یکسان‌سازی و یکی می‌شوند.
  ۴) سقف ارسال در هر اجرا: اگر شمار ارسال‌ها از سقف بگذرد، اجرا متوقف می‌شود
     (محافظ در برابر حلقهٔ ناخواسته).
  ۵) حریم خصوصی: دفتر ارسال در مخزن عمومی نوشته می‌شود، پس فقط «اثر انگشت»
     نشانی (sha1 کوتاه‌شدهٔ هویت یکسان‌سازی‌شده) ثبت می‌گردد، نه خود نشانی.

متغیرهای محیطی:
  RCHEP_SEND_COOLDOWN_HOURS  بازهٔ خنک‌شدن بر حسب ساعت (پیش‌فرض 24)
  RCHEP_MAX_SENDS_PER_RUN    سقف ارسال در هر اجرا (پیش‌فرض 500)
  RCHEP_SEND_LEDGER          مسیر دفتر ارسال (پیش‌فرض data/send_log.jsonl)
  RCHEP_GUARD_STRICT         =1 یعنی نبودِ گاردریل، ارسال را متوقف کند
  RCHEP_FORCE_SEND           =1 یعنی بازفرست عمدی، دفتر ارسال نادیده گرفته شود
"""

import os
import re
import json
import hashlib
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")

GMAIL_DOMAINS = {"gmail.com", "googlemail.com"}

DEFAULT_COOLDOWN_HOURS = 24.0
DEFAULT_MAX_SENDS_PER_RUN = 500

_run_sends = 0  # شمار ارسال‌های همین اجرا


class DuplicateSendBlocked(RuntimeError):
    """ارسال تکراری: همین پیام پیش‌تر برای همین شخص ثبت شده است."""


class SendCapExceeded(RuntimeError):
    """سقف ارسال در این اجرا پر شده است (احتمال حلقهٔ ناخواسته)."""


def is_dry_run():
    return os.environ.get("RCHEP_DRY_RUN") == "1"


def is_forced():
    return os.environ.get("RCHEP_FORCE_SEND") == "1"


def ledger_path():
    return os.environ.get("RCHEP_SEND_LEDGER") or os.path.join(DATA_DIR, "send_log.jsonl")


def cooldown_hours():
    try:
        return float(os.environ.get("RCHEP_SEND_COOLDOWN_HOURS", DEFAULT_COOLDOWN_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_COOLDOWN_HOURS


def max_sends_per_run():
    try:
        return int(os.environ.get("RCHEP_MAX_SENDS_PER_RUN", DEFAULT_MAX_SENDS_PER_RUN))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SENDS_PER_RUN


def canonical_identity(address):
    """
    هویت یکسان‌شدهٔ یک نشانی:
      * حروف کوچک، حذف فاصله و نویسه‌های چسبیده
      * googlemail.com ↔ gmail.com
      * در جیمیل: حذف نقطه‌ها و برچسب +tag از بخش محلی
    """
    address = (address or "").strip().lower().strip(".,;<>()[]\"'")
    address = re.sub(r"\s+", "", address)
    if "@" not in address:
        return address
    local, _, domain = address.rpartition("@")
    if domain in GMAIL_DOMAINS:
        local = local.split("+", 1)[0].replace(".", "")
        domain = "gmail.com"
    return f"{local}@{domain}"


def fingerprint(address):
    """اثر انگشت کوتاه برای ثبت در دفتر ارسال (مخزن عمومی است)."""
    return hashlib.sha1(canonical_identity(address).encode("utf-8")).hexdigest()[:16]


def collapse(addresses):
    """
    نشانی‌های هم‌هویت را یکی می‌کند و ترتیب نخستین ظهور را نگه می‌دارد.
    بازگشت: (فهرست یکتاشده، شمار حذف‌شده‌ها، نقشهٔ هویت → نشانی‌های اصلی)
    """
    kept, seen, groups = [], set(), {}
    for raw in addresses or []:
        if not raw:
            continue
        key = canonical_identity(raw)
        if not key:
            continue
        groups.setdefault(key, []).append(raw)
        if key in seen:
            continue
        seen.add(key)
        kept.append(raw)
    removed = sum(len(v) - 1 for v in groups.values())
    return kept, removed, groups


def _load_ledger():
    records = []
    path = ledger_path()
    if not os.path.exists(path):
        return records
    try:
        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return records
    return records


def _append(record):
    path = ledger_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _slot(kind, key=None):
    return f"{kind}:{key or ''}"


def last_record(address, kind, key=None):
    """واپسین ثبت دفتر برای همین شخص و همین پیام (یا None)."""
    fp = fingerprint(address)
    slot = _slot(kind, key)
    found = None
    for record in _load_ledger():
        if record.get("to") == fp and record.get("kind") == slot:
            found = record
    return found


def is_duplicate(address, kind, key=None, now=None):
    """آیا همین پیام در بازهٔ خنک‌شدن برای همین شخص ارسال شده است؟"""
    if is_forced():
        return False
    record = last_record(address, kind, key)
    if not record:
        return False
    if record.get("status") == "released":
        return False  # ارسال پیشین شکست خورد: تلاش دوباره آزاد است
    try:
        previous = datetime.fromisoformat(record["ts"])
    except (KeyError, ValueError):
        return True
    if previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    moment = now or datetime.now(timezone.utc)
    age_hours = (moment - previous).total_seconds() / 3600.0
    return age_hours < cooldown_hours()


def count_run_send():
    """شمارندهٔ ارسال‌های همین اجرا را یکی جلو می‌برد و سقف را می‌سنجد."""
    global _run_sends
    _run_sends += 1
    if _run_sends > max_sends_per_run():
        raise SendCapExceeded(
            f"send cap reached for this run ({max_sends_per_run()}); aborting to avoid a mail loop"
        )
    return _run_sends


def reserve(address, kind, key=None, force=False):
    """
    ادعا پیش از ارسال. True = مجاز، False = تکراری (باید رد شود).
    در حالت dry-run هیچ چیزی ثبت یا مسدود نمی‌شود.
    """
    if is_dry_run():
        return True
    if not force and is_duplicate(address, kind, key):
        return False
    count_run_send()
    _append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "to": fingerprint(address),
            "kind": _slot(kind, key),
            "status": "reserved",
        }
    )
    return True


def release(address, kind, key=None, reason="send failed"):
    """آزادکردن ادعا پس از شکست ارسال تا تلاش دوباره ممکن شود."""
    if is_dry_run():
        return
    _append(
        {
            "ts": datetime.now(timezone.utc).isoformat(),
            "to": fingerprint(address),
            "kind": _slot(kind, key),
            "status": "released",
            "reason": str(reason)[:160],
        }
    )


def describe_duplicates(addresses):
    """نشانی‌هایی که به یک شخص می‌رسند (برای گزارش) — بدون حذف داده."""
    _, _, groups = collapse(addresses)
    return {identity: members for identity, members in groups.items() if len(members) > 1}
