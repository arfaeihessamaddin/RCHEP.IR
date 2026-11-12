#!/usr/bin/env python3
"""
آزمون خودکار گاردریل‌های ارسال (scripts/send_guard.py).
اجرا:  python3 scripts/send_guard_selftest.py     (بدون هیچ تماس شبکه‌ای)
با کد خروج ۰ در صورت گذر همهٔ آزمون‌ها.
"""

import os
import sys
import json
import tempfile
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

tmpdir = tempfile.mkdtemp(prefix="rchep-guard-")
os.environ["RCHEP_SEND_LEDGER"] = os.path.join(tmpdir, "send_log.jsonl")
os.environ.pop("RCHEP_FORCE_SEND", None)
os.environ.pop("RCHEP_DRY_RUN", None)

import send_guard as guard  # noqa: E402

failures = []


def check(name, condition, detail=""):
    print(f"{'PASS' if condition else 'FAIL'} — {name}{(' : ' + detail) if detail and not condition else ''}")
    if not condition:
        failures.append(name)


# ۱) یکسان‌سازی هویت
check("canonical: lowercase/trim", guard.canonical_identity("  H.Arfaei@Physics.Sharif.IR ") == "h.arfaei@physics.sharif.ir")
check("canonical: gmail dots+tag", guard.canonical_identity("hessam.a+news@gmail.com") == "hessama@gmail.com")
check("canonical: googlemail↔gmail", guard.canonical_identity("a.b@googlemail.com") == guard.canonical_identity("ab@gmail.com"))
check("canonical: icloud untouched", guard.canonical_identity("h.arfaei@icloud.com") == "h.arfaei@icloud.com")

kept, removed, groups = guard.collapse([
    "a.b@gmail.com", "ab+news@gmail.com", "c@example.org", "AB@GMAIL.COM", "c@example.org",
])
check("collapse: unique list", kept == ["a.b@gmail.com", "c@example.org"], str(kept))
check("collapse: removed count", removed == 3, str(removed))
check("collapse: group map", sorted(groups["ab@gmail.com"]) == sorted(["a.b@gmail.com", "ab+news@gmail.com", "AB@GMAIL.COM"]))
check("collapse: shared group detected", guard.describe_duplicates(["a.b@gmail.com", "ab@gmail.com"]) == {"ab@gmail.com": ["a.b@gmail.com", "ab@gmail.com"]})

# ۲) ادعا پیش از ارسال و جلوگیری از تکرار
check("reserve: first send allowed", guard.reserve("a.b@gmail.com", "welcome", "welcome") is True)
check("reserve: repeat blocked", guard.reserve("ab@gmail.com", "welcome", "welcome") is False)
check("reserve: other notice allowed", guard.reserve("a.b@gmail.com", "notice", "1405_آبان_25_x") is True)
check("reserve: other person allowed", guard.reserve("other@example.org", "welcome", "welcome") is True)

# ۳) آزادسازی پس از شکست ارسال
guard.reserve("fail@example.org", "verify", "verify")
guard.release("fail@example.org", "verify", "verify", reason="SMTP timeout")
check("release: retry allowed after failure", guard.reserve("fail@example.org", "verify", "verify") is True)

# ۴) بازهٔ خنک‌شدن
old = datetime.now(timezone.utc) - timedelta(hours=48)
with open(guard.ledger_path(), "a", encoding="utf-8") as handle:
    handle.write(json.dumps({"ts": old.isoformat(), "to": guard.fingerprint("stale@example.org"),
                             "kind": "welcome:", "status": "reserved"}) + "\n")
check("cooldown: expired reservation is retryable", guard.reserve("stale@example.org", "welcome", None) is True)

# ۵) بازفرست عمدی
os.environ["RCHEP_FORCE_SEND"] = "1"
check("force: bypasses ledger", guard.reserve("ab@gmail.com", "welcome", "welcome") is True)
os.environ.pop("RCHEP_FORCE_SEND", None)

# ۶) حالت dry-run هیچ چیزی ثبت یا مسدود نمی‌کند
os.environ["RCHEP_DRY_RUN"] = "1"
before = len(guard._load_ledger())
guard.reserve("ab@gmail.com", "welcome", "welcome")
check("dry-run: no ledger writes", len(guard._load_ledger()) == before)
check("dry-run: never blocks", guard.reserve("ab@gmail.com", "welcome", "welcome") is True)
os.environ.pop("RCHEP_DRY_RUN", None)

# ۷) سقف ارسال در هر اجرا
os.environ["RCHEP_MAX_SENDS_PER_RUN"] = "3"
guard._run_sends = 0
cap_ok = False
try:
    for i in range(5):
        guard.reserve(f"cap{i}@example.org", "notice", f"n{i}")
except guard.SendCapExceeded:
    cap_ok = True
check("cap: aborts runaway loop", cap_ok)
os.environ.pop("RCHEP_MAX_SENDS_PER_RUN", None)

# ۸) حریم خصوصی دفتر: هیچ نشانی خامی در دفتر نیست
raw = open(guard.ledger_path(), encoding="utf-8").read()
check("privacy: no raw address in ledger", "@example.org" not in raw and "ab@gmail.com" not in raw)

# ۹) سیم‌کشی: گاردریل باید واقعاً در newsletter_manager بار شود (نه fail-open)
import newsletter_manager as nm  # noqa: E402
check("wiring: guard loaded inside newsletter_manager", nm._load_send_guard() is not None)
check("wiring: send_smtp_email accepts guard args",
      "kind" in nm.send_smtp_email.__code__.co_varnames and "force" in nm.send_smtp_email.__code__.co_varnames)
check("wiring: broadcast_notice accepts notice_key",
      "notice_key" in nm.broadcast_notice.__code__.co_varnames)

print()
if failures:
    print(f"{len(failures)} check(s) FAILED: {', '.join(failures)}")
    sys.exit(1)
print("All guardrail checks passed.")
sys.exit(0)
