#!/usr/bin/env python3
"""
آزمون گاردریل «پوستر در برابر آرم» در scripts/email_fetcher.py

ریشهٔ خطا: تصویر کوچک و مربع‌شکل آرم دانشگاه که در پیکرهٔ ایمیل اعلام سمینار
هست، به‌جای پوستر ذخیره می‌شد؛ در نتیجه خرامش پیش‌نمایش بی‌ربط می‌داد و
زنش تنها آرم را می‌آورد. این آزمون تضمین می‌کند آرم‌ها رد و پوسترها پذیرفته شوند.

اجرا: python3 scripts/poster_guard_selftest.py
"""
import os
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_fetcher import image_dimensions, is_poster_like  # noqa: E402


def make_png(width, height):
    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IEND", b"")


def make_jpeg(width, height):
    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x01\x11\x00\x02\x11\x01\x03\x11\x01"
    return b"\xff\xd8" + b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + sof + b"\xff\xd9"


CASES = [
    # (توضیح، نام پرونده، بایت‌ها، انتظار)
    ("آرم مربع کوچک دانشگاه", "25-aban-unclassified.jpg", make_jpeg(397, 406), False),
    ("آرم با نام صریح", "sharif-logo.png", make_png(1200, 1200), False),
    ("امضای فارسی", "امضا.png", make_png(900, 1200), False),
    ("نوار بنر پهن", "header-banner.jpg", make_png(1600, 400), False),
    ("پوستر فارسی", "25-aban-fa.jpg", make_jpeg(2164, 2800), True),
    ("پوستر انگلیسی", "25-aban-en.jpg", make_png(2164, 2800), True),
    ("پوستر بی‌نشانه در نام", "unclassified.png", make_png(1208, 1514), True),
    ("نوار پهن بی‌نشانه", "25-aban-unclassified-f45170.jpg", make_jpeg(1080, 675), True),
    ("ابعاد نامعلوم", "poster.dat", b"\x00\x01\x02", True),
]


def main():
    failures = []
    for label, name, payload, expected in CASES:
        got = is_poster_like(name, payload)
        status = "PASS" if got == expected else "FAIL"
        if status == "FAIL":
            failures.append(label)
        print(f"[{status}] {label}: is_poster_like={got} (expected {expected})")

    # خوانش درست ابعاد
    for width, height in ((2164, 2800), (397, 406), (1080, 675)):
        assert image_dimensions(make_jpeg(width, height)) == (width, height)
        assert image_dimensions(make_png(width, height)) == (width, height)
    print("[PASS] image_dimensions برای JPEG و PNG درست کار می‌کند")

    if failures:
        print("آزمون ناکام: " + ", ".join(failures))
        return 1
    print("همهٔ آزمون‌های گاردریل پوستر گذشت.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
