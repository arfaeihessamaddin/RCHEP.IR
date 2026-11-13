#!/usr/bin/env python3
"""نگهبان پیش‌نمایش پوسترها.

هر پوستری که در صفحه‌ای با `data-poster="..."` ارجاع شده باشد باید
۱) خودش روی دیسک باشد،
۲) نسخهٔ سبک `*-preview.jpg` داشته باشد (وگرنه خرامش پوستر سنگین و کند می‌شود)،
۳) نسخهٔ سبک کوچک‌تر از اصل باشد.
همچنین مطمئن می‌شود `assets/js/main.js` مسیر پیش‌نمایش را می‌سازد.

بازگشت ۰ یعنی سالم. هر پیام `!!` یک ایراد است.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATTERN = re.compile(r'data-poster="([^"]+)"')
HTML = [f for f in sorted(os.listdir(ROOT)) if f.endswith('.html')]
# A hover preview that has to be downloaded first is only useful if it is small:
# on a slow link a 1 MB poster means the preview shows up a minute later.
MAX_PREVIEW_BYTES = 160 * 1024
MIN_SHRINK = 1.5  # the preview must be at least 1.5x smaller than the original


def referenced_posters():
    seen = []
    for name in HTML:
        with open(os.path.join(ROOT, name), encoding='utf-8') as fh:
            for match in PATTERN.findall(fh.read()):
                if match not in seen:
                    seen.append((name, match))
    return seen


def preview_path(src):
    base, _ = os.path.splitext(src)
    return f'{base}-preview.jpg'


def main():
    problems = []
    refs = referenced_posters()
    if not refs:
        problems.append('!! هیچ پوستری در صفحات ارجاع نشده است (انتظار می‌رفت حداقل یکی باشد)')

    for page, src in refs:
        src_abs = os.path.join(ROOT, src)
        if not os.path.isfile(src_abs):
            problems.append(f'!! پوستر ارجاع‌شده در {page} پیدا نشد: {src}')
            continue
        prev = preview_path(src)
        prev_abs = os.path.join(ROOT, prev)
        if not os.path.isfile(prev_abs):
            problems.append(f'!! پیش‌نمایش سبک ساخته نشده: {prev} '
                            '(اجرا کنید: python3 scripts/make_poster_previews.py)')
            continue
        if os.path.getsize(prev_abs) >= os.path.getsize(src_abs):
            problems.append(f'!! پیشنمایش سبکتر از اصل نیست: {prev}')
        elif os.path.getsize(prev_abs) > MAX_PREVIEW_BYTES:
            kb = os.path.getsize(prev_abs) / 1024
            problems.append(f'!! پیشنمایش سنگین است ({kb:.0f} KB > {MAX_PREVIEW_BYTES // 1024} KB): {prev} '
                            '— روی پیوند کند، خرامش دیر ظاهر میشود')
        if os.path.getsize(prev_abs) * MIN_SHRINK > os.path.getsize(src_abs):
            problems.append(f'!! پیشنمایش بهقدر کافی سبک نشده: {prev}')

    with open(os.path.join(ROOT, 'assets', 'js', 'main.js'), encoding='utf-8') as fh:
        js = fh.read()
    for needle in ("const previewPath", "poster-floating-preview", "mouseenter",
                   "preloadPoster(previewPath("):
        if needle not in js:
            problems.append(f'!! منطق خرامش پوستر در main.js ناقص است (نیافت: {needle})')

    print(f'checked {len(refs)} poster reference(s) across {len(HTML)} page(s)')
    if problems:
        print('\n'.join(problems))
        return 1
    print('poster preview guardrail: OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
