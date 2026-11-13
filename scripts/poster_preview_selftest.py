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
            problems.append(f'!! پیش‌نمایش سبک‌تر از اصل نیست: {prev}')

    with open(os.path.join(ROOT, 'assets', 'js', 'main.js'), encoding='utf-8') as fh:
        js = fh.read()
    for needle in ("const previewPath", "poster-floating-preview", "mouseenter"):
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
