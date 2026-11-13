#!/usr/bin/env python3
"""پیش‌نمایش سبک پوسترها را می‌سازد تا هنگام خرامش، پوستر بی‌درنگ ظاهر شود.

هر تصویری که در صفحات HTML با `data-poster="..."` ارجاع شده باشد، یک نسخهٔ
سبک `*-preview.jpg` (بیشینه ۱۲۰۰ پیکسل، کیفیت ۸۰) می‌گیرد که هم در پیش‌نمایش
شناور و هم در پنجرهٔ پوستر به کار می‌رود. فایل اصلی دست‌نخورده می‌ماند و
پیوند دانلود همچنان به همان پوستر کامل می‌رود.

اجرا:  python3 scripts/make_poster_previews.py [--force]
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_DIM = 1200
QUALITY = 80
PATTERN = re.compile(r'data-poster="([^"]+)"')


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


def make_preview(src_abs, dst_abs):
    """با sips (مک) یا Pillow می‌سازد؛ در نبود هر دو، False برمی‌گرداند."""
    if shutil.which('sips'):
        cmd = ['sips', '-Z', str(MAX_DIM), '-s', 'format', 'jpeg',
               '-s', 'formatOptions', str(QUALITY), src_abs, '--out', dst_abs]
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
        img.thumbnail((MAX_DIM, MAX_DIM))
        img.save(dst_abs, 'JPEG', quality=QUALITY, optimize=True)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true',
                        help='حتی اگر پیش‌نمایش تازه باشد، بازش بساز')
    args = parser.parse_args()

    made, fresh, missing = 0, 0, []
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
        if make_preview(src_abs, dst_abs):
            made += 1
        else:
            print(f'!! ابزار ساخت پیش‌نمایش پیدا نشد (sips/Pillow): {src}')

    print(f'previews made={made} fresh={fresh} missing_sources={len(missing)}')
    for src in missing:
        print(f'!! پوستر ارجاع‌شده پیدا نشد: {src}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
