#!/usr/bin/env python3
"""
آزمون گاردریل «پوستر در برابر آرم» در scripts/email_fetcher.py

ریشهٔ خطا: تصویر کوچک و مربعشکل آرم دانشگاه که در پیکرهٔ ایمیل اعلام سمینار
هست، بهجای پوستر ذخیره میشد؛ در نتیجه خرامش پیشنمایش بیربط میداد و
زنش تنها آرم را میآورد. این آزمون تضمین میکند آرمها رد و پوسترها پذیرفته شوند.

دومین ریشهٔ همان خطا: پوستر سمینار بیشتر وقتها PDF است و پیوست PDF یکسره
نادیده گرفته میشد؛ پس تنها تصویرِ باقیمانده در ایمیل (آرم مرکز) پوستر میشد.
بخش «مسیر PDF» همین آزمون، تبدیل نخستین صفحهٔ PDF به تصویر را میسنجد.

اجرا: python3 scripts/poster_guard_selftest.py
"""
import os
import shutil
import struct
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from email_fetcher import image_dimensions, is_poster_like, pdf_first_page_image  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    # (توضیح، نام پرونده، بایتها، انتظار)
    ("آرم مربع کوچک دانشگاه", "25-aban-unclassified.jpg", make_jpeg(397, 406), False),
    ("آرم با نام صریح", "sharif-logo.png", make_png(1200, 1200), False),
    ("امضای فارسی", "امضا.png", make_png(900, 1200), False),
    ("نوار بنر پهن", "header-banner.jpg", make_png(1600, 400), False),
    ("پوستر فارسی", "25-aban-fa.jpg", make_jpeg(2164, 2800), True),
    ("پوستر انگلیسی", "25-aban-en.jpg", make_png(2164, 2800), True),
    ("پوستر بینشانه در نام", "unclassified.png", make_png(1208, 1514), True),
    # همین نوار ۱۰۸۰×۶۷۵ در واقع نشان مرکز بود و پیشتر بهاشتباه پوستر شمرده میشد
    ("نشان افقی ۱۰۸۰×۶۷۵ (آرم مرکز)", "image001.jpg", make_jpeg(1080, 675), False),
    ("پوستر افقی بزرگ", "unclassified.png", make_png(2400, 1600), True),
    ("ابعاد نامعلوم", "poster.dat", b"\x00\x01\x02", True),
]

# نشان واقعی روی دیسک (اگر باشد) باید با هر نامی رد شود — چون بایتهایش شناختهشده است.
BRAND_LOGO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "assets", "images", "rchep-logo.jpg")
if os.path.isfile(BRAND_LOGO):
    with open(BRAND_LOGO, "rb") as brand_file:
        CASES.append(("نشان واقعی مرکز با نام بیربط", "image001.jpg", brand_file.read(), False))


def make_pdf_with_jpeg(jpeg_bytes, width, height, page_width=595, page_height=842):
    """یک PDF تکصفحهای با تصویر JPEG درونش میسازد (برای آزمون مسیر PDF)."""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /XObject << /Im0 4 0 R >> >>"
         " /Contents 5 0 R >>" % (page_width, page_height)).encode(),
        (b"<< /Type /XObject /Subtype /Image /Width %d /Height %d /ColorSpace /DeviceRGB"
         b" /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n" % (width, height, len(jpeg_bytes))
         + jpeg_bytes + b"\nendstream"),
    ]
    content = f"q {page_width} 0 0 {page_height} 0 0 cm /Im0 Do Q".encode()
    objects.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n" % (len(objects) + 1) + b"0000000000 65535 f \n"
    for offset in offsets:
        out += b"%010d 00000 n \n" % offset
    out += (b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref))
    return bytes(out)


def real_poster_jpeg():
    """بایتهای یک پوستر واقعی روی دیسک (برای آزمون PDF با تصویر واقعی)."""
    for name in ("25-aban-fa.jpg", "25-aban-en.jpg", "02-azar-unclassified.jpg"):
        path = os.path.join(REPO, "assets", "images", "events", name)
        if os.path.isfile(path):
            with open(path, "rb") as poster_file:
                return poster_file.read()
    return None


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
    print("[PASS] image_dimensions برای JPEG و PNG درست کار میکند")

    # مسیر PDF: پوستر سمینار غالباً PDF میرسد و نخستین صفحهٔ آن باید پوستر شود.
    renderer = shutil.which("pdftoppm") or shutil.which("sips")
    poster_jpeg = real_poster_jpeg()
    if not renderer:
        print("[SKIP] رندرکنندهٔ PDF (pdftoppm/sips) روی این ماشین نصب نیست")
    elif not poster_jpeg:
        print("[SKIP] پوستر واقعی روی دیسک پیدا نشد (آزمون مسیر PDF انجام نشد)")
    else:
        poster_dims = image_dimensions(poster_jpeg)
        rendered = pdf_first_page_image(make_pdf_with_jpeg(poster_jpeg, poster_dims[0], poster_dims[1])) if poster_dims else None
        if rendered and image_dimensions(rendered):
            if is_poster_like("25aban-fa.pdf", rendered):
                print(f"[PASS] پوستر PDF رندر شد {image_dimensions(rendered)} و پوستر شمرده شد")
            else:
                failures.append("پوستر PDF")
                print("[FAIL] تصویرِ ساختهشده از پوستر PDF پوستر شمرده نشد")
        else:
            failures.append("رندر پوستر PDF")
            print("[FAIL] نخستین صفحهٔ پوستر PDF به تصویر تبدیل نشد")

    # PDF بیاعتبار نباید اجرا را با استثنا بیندازد.
    assert pdf_first_page_image(b"not a pdf at all") is None
    print("[PASS] PDF بیاعتبار None برمیگرداند (بدون استثنا)")

    if failures:
        print("آزمون ناکام: " + ", ".join(failures))
        return 1
    print("همهٔ آزمون‌های گاردریل پوستر گذشت.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
