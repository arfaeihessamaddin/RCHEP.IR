#!/usr/bin/env python3
"""پیش‌نمایش سبک پوسترها را می‌سازد تا هنگام خرامش، پوستر بی‌درنگ ظاهر شود.

هر تصویری که در صفحات HTML با `data-poster="..."` ارجاع شده باشد، یک نسخهٔ
سبک `*-preview.jpg` می‌گیرد که هم در پیش‌نمایش شناور و هم در پنجرهٔ پوستر
به کار می‌رود. فایل اصلی دست‌نخورده می‌ماند و پیوند دانلود همچنان به همان
پوستر کامل می‌رود.

دو شرط بازرس بیرونی (scripts/site_inspector.py) همین‌جا تضمین می‌شود تا هیچ
اجرایی سرخ نشود و کسی مجبور به پیگیری دستی نباشد:
  ۱. پیش‌نمایش از سقف ۱۶۰ کیلوبایت سنگین‌تر نباشد؛
  ۲. پیش‌نمایش دست‌کم ۱٫۵ برابر سبک‌تر از پوستر اصل باشد.
اگر با اندازه/کیفیت نخستین (۹۰۰ پیکسل، کیفیت ۷۲) شرط‌ها برنیاید، همین
اسکریپت پله‌پله کوچک‌تر و کم‌کیفیت‌تر می‌سازد تا شرط‌ها برآورده شود. کف
هرگز کوچک‌تر از ۳۶٪ بلندترین ضلع اصل نمی‌شود، چون بازرس پیش‌نمایش
کوچک‌تر از ۳۰٪ اصل را هم ایراد می‌داند.

اجرا:  python3 scripts/make_poster_previews.py [--force]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_DIM = 900                    # اندازهٔ نخستین پیش‌نمایش
QUALITY = 72                     # کیفیت نخستین پیش‌نمایش
MIN_DIM = 320                    # کوچک‌ترین اندازهٔ مجاز پیش‌نمایش
MIN_QUALITY = 40                 # کم‌ترین کیفیت مجاز
MAX_PREVIEW_BYTES = 160 * 1024   # سقف بازرس
MIN_SHRINK = 1.5                 # بازرس: پیش‌نمایش دست‌کم ۱٫۵ برابر سبک‌تر از اصل
MIN_SCALE = 0.36                 # کف مجاز نسبت به بلندترین ضلع اصل (بازرس: ۳۰٪)
PATTERN = re.compile(r'data-poster="([^"]+)"')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from email_fetcher import image_dimensions   # خواندن ابعاد بدون کتابخانهٔ بیرونی
except Exception:                                # نبود ماژول، ساخت پیش‌نمایش را نمی‌ایستاند
    image_dimensions = None


def poster_paths():
    """همهٔ مسیرهای پوستر ارجاع‌شده در صفحات HTML (یکتا، به ترتیب)."""
    found = []
    for name in sorted(os.listdir(ROOT)):
        if not name.endswith('.html'):
            continue
        with open(os.path.join(ROOT, name), encoding='utf-8') as fh:
            for match in PATTERN.findall(fh.read()):
                if match not in found:
                    found.append(match)
    return found


def preview_path(src):
    base, ext = os.path.splitext(src)
    return f"{base}-preview.jpg"


def render(src_abs, dst_abs, dim, quality):
    """با sips (مک) یا Pillow می‌سازد؛ در نبود هر دو، False برمی‌گرداند."""
    if shutil.which('sips'):
        cmd = ['sips', '-Z', str(dim), '-s', 'format', 'jpeg',
               '-s', 'formatOptions', str(quality), src_abs, '--out', dst_abs]
        done = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
        if done.returncode == 0 and os.path.exists(dst_abs):
            return True
    try:
        from PIL import Image  # noqa: WPS433 (اختیاری)
    except ImportError:
        return False
    with Image.open(src_abs) as img:
        img = img.convert('RGB')
        img.thumbnail((dim, dim))
        img.save(dst_abs, 'JPEG', quality=quality, optimize=True)
    return os.path.exists(dst_abs)


def source_longest_side(src_abs):
    """بلندترین ضلع پوستر اصل (برای تعیین کف کوچک‌شدن) یا None."""
    try:
        from PIL import Image
        with Image.open(src_abs) as img:
            return max(int(img.size[0]), int(img.size[1]))
    except Exception:
        pass
    if image_dimensions is None:
        return None
    try:
        with open(src_abs, 'rb') as fh:
            dims = image_dimensions(fh.read(4 * 1024 * 1024))
    except Exception:
        dims = None
    return max(dims) if dims else None


def build_preview(src_abs, dst_abs):
    """پیش‌نمایش می‌سازد و شرط‌های بازرس را تا جای ممکن برآورده می‌کند.

    برمی‌گرداند: (بایت پیش‌نمایش، اندازه، کیفیت، برآورده‌شدن شرط‌ها)
    یا None اگر هیچ ابزاری برای ساخت تصویر نبود.
    """
    source_bytes = os.path.getsize(src_abs)
    # هم سقف بازرس، هم «دست‌کم ۱٫۵ برابر سبک‌تر از اصل» (با حاشیهٔ امن کوچک)
    budget = min(MAX_PREVIEW_BYTES, int(source_bytes / MIN_SHRINK) - 1024)
    longest = source_longest_side(src_abs)
    floor = MIN_DIM if not longest else max(MIN_DIM, int(MIN_SCALE * longest))
    dim, quality = max(MAX_DIM, floor), QUALITY
    best = None
    while True:
        if not render(src_abs, dst_abs, dim, quality):
            return None
        size = os.path.getsize(dst_abs)
        best = (size, dim, quality, size <= budget)
        if size <= budget:
            break
        if dim <= floor and quality <= MIN_QUALITY:
            break
        dim = max(floor, int(dim * 0.85))
        quality = max(MIN_QUALITY, quality - 8)
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true',
                        help='حتی اگر پیش‌نمایش تازه باشد، بازش بساز')
    args = parser.parse_args()

    made, fresh, missing, unfit = 0, 0, [], []
    for src in poster_paths():
        src_abs = os.path.join(ROOT, src)
        if not os.path.isfile(src_abs):
            missing.append(src)
            continue
        dst = preview_path(src)
        dst_abs = os.path.join(ROOT, dst)
        fresh_enough = (os.path.exists(dst_abs)
                        and os.path.getmtime(dst_abs) >= os.path.getmtime(src_abs))
        if fresh_enough and not args.force:
            fresh += 1
            continue
        result = build_preview(src_abs, dst_abs)
        if result is None:
            print(f'!! ابزار ساخت پیش‌نمایش پیدا نشد (sips/Pillow): {src}')
            continue
        size, dim, quality, ok = result
        made += 1
        mark = 'ok' if ok else 'بهترین حالت ممکن'
        print(f'preview {dst}: {size // 1024}KB ({dim}px، کیفیت {quality}) — {mark}')
        if not ok:
            unfit.append(dst)

    print(f'previews made={made} fresh={fresh} missing_sources={len(missing)} '
          f'over_budget={len(unfit)}')
    for src in missing:
        print(f'!! پوستر ارجاع‌شده پیدا نشد: {src}')
    for dst in unfit:
        print(f'!! پیش‌نمایش {dst} حتی با کوچک‌ترین اندازه و کم‌ترین کیفیت هم '
              f'سبک‌تر از شرط بازرس نشد؛ پوستر اصل بسیار فشرده است و بهتر است '
              f'پوستر تازه‌ای از برگزارکننده خواسته شود.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
